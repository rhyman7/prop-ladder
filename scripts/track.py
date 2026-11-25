"""Log the All +EV plays, keep their last pre-kickoff price, grade them, and
write docs/results.json for the Results page.

Run after build.py (same workflow). Uses docs/data.json as the current market.
- Logged: every rung + side + book (DK/FD) with edge > 0 and 2+ books behind
  the true probability, for a game not yet started. First sighting is kept
  (first_*); every later refresh before kickoff updates last_* (that book's
  price if still posted, and the market's true probability).
- Graded: when the game is final, from SGO's `score` on the prop's odd
  (null score = player did not play = void). $10 flat at the first price,
  no boost. Costs about 1 SGO object per finished game (MAX_GRADE per run).
Log: data/plays_log.json (not served). Summary: docs/results.json.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
LOG = os.path.join(ROOT, "data", "plays_log.json")
OUT = os.path.join(ROOT, "docs", "results.json")
BASE = "https://api.sportsgameodds.com/v2"
KEY = os.environ.get("SGO_API_KEY", "")
MIN_BOOKS = 2
MAX_GRADE = int(os.environ.get("MAX_GRADE", 40))   # finished games fetched per run
GRADE_AFTER_H = 4                                   # hours after kickoff before trying


def imp(a):
    a = float(a)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def profit10(a):
    return a / 10 if a > 0 else 1000 / -a


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def get(params):
    url = f"{BASE}/events/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-Api-Key": KEY})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(12)
                continue
            return {"error": f"HTTP {e.code}"}
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            return {"error": repr(e)}


def log_plays(log, data):
    now = parse(data["pulledAt"])
    added = updated = 0
    for p in data["props"]:
        if not p.get("start") or parse(p["start"]) <= now:
            continue
        for r in p["rungs"]:
            for side in ("o", "u"):
                pw = r["po"] if side == "o" else r["pu"]
                for bk in ("dk", "fd"):
                    key = f'{p["game"]}|{p["pid"]}|{p["stat"]}|{r["l"]}|{side}|{bk}'
                    odds = r.get(bk + side)
                    row = log.get(key)
                    if row and row["status"] == "pending":
                        # refresh the "last before kickoff" view, flagged or not
                        row["last_true"] = pw
                        row["last_books"] = r["n"]
                        row["last_seen"] = data["pulledAt"]
                        if odds is not None:
                            row["last_odds"] = odds
                        updated += 1
                        continue
                    if row or odds is None or r["n"] < MIN_BOOKS:
                        continue
                    edge = pw - imp(odds)
                    if edge <= 0:
                        continue
                    log[key] = {
                        "key": key, "status": "pending", "sport": p["sport"], "game": p["game"], "start": p["start"],
                        "player": p["player"], "pid": p["pid"], "team": p.get("team"), "stat": p["stat"],
                        "statLabel": p["statLabel"], "line": r["l"], "side": side, "book": bk, "anchor": r["a"],
                        "first_seen": data["pulledAt"], "first_odds": odds, "first_true": round(pw, 4),
                        "first_edge": round(edge, 4), "first_books": r["n"],
                        "last_seen": data["pulledAt"], "last_odds": odds, "last_true": round(pw, 4), "last_books": r["n"],
                    }
                    added += 1
    return added, updated


def grade(log, now):
    due = sorted({row["game"] for row in log.values()
                  if row["status"] == "pending" and parse(row["start"]) < now - timedelta(hours=GRADE_AFTER_H)})
    due = due[:MAX_GRADE]
    graded = fetched = 0
    for i in range(0, len(due), 10):
        chunk = due[i:i + 10]
        resp = get({"eventIDs": ",".join(chunk), "limit": len(chunk)})
        time.sleep(7)
        if "data" not in resp:
            print("grade fetch:", resp.get("error"), file=sys.stderr)
            continue
        fetched += len(resp["data"])
        for ev in resp["data"]:
            stt = ev.get("status") or {}
            if not (stt.get("finalized") or stt.get("ended") or stt.get("completed")):
                continue
            cancelled = stt.get("cancelled")
            odds = ev.get("odds") or {}
            for row in log.values():
                if row["game"] != ev.get("eventID") or row["status"] != "pending":
                    continue
                o = odds.get(f'{row["stat"]}-{row["pid"]}-game-ou-over') or {}
                score = o.get("score")
                if cancelled or score is None:
                    if stt.get("finalized") or cancelled:
                        row.update(status="void", result="void", actual=None, graded_at=now.isoformat(timespec="seconds"))
                        graded += 1
                    continue
                score = float(score)
                ln = float(row["line"])
                if score == ln:
                    res = "push"
                elif (score > ln) == (row["side"] == "o"):
                    res = "win"
                else:
                    res = "loss"
                pr = profit10(row["first_odds"])
                row.update(status="graded", result=res, actual=score, graded_at=now.isoformat(timespec="seconds"),
                           profit=round(pr if res == "win" else -10.0 if res == "loss" else 0.0, 2))
                graded += 1
    return graded, fetched


def bucket_edge(e):
    for lo, hi, lab in ((0, .01, "0–1%"), (.01, .02, "1–2%"), (.02, .03, "2–3%"), (.03, .05, "3–5%")):
        if lo <= e < hi:
            return lab
    return "5%+"


def bucket_price(a):
    if a <= -300:
        return "−300 or less"
    if a < -150:
        return "−299 to −151"
    if a < 100:
        return "−150 to −101"
    if a < 200:
        return "+100 to +199"
    return "+200 or more"


def summarize(rows):
    n = len(rows)
    if not n:
        return None
    w = sum(r["result"] == "win" for r in rows)
    l = sum(r["result"] == "loss" for r in rows)
    pu = sum(r["result"] == "push" for r in rows)
    staked = 10.0 * (w + l)
    profit = sum(r["profit"] for r in rows)
    exp_w = sum(r["first_true"] for r in rows if r["result"] in ("win", "loss"))
    exp_profit = sum(r["first_true"] * profit10(r["first_odds"]) - (1 - r["first_true"]) * 10
                     for r in rows if r["result"] in ("win", "loss"))
    clv = [r["last_true"] - imp(r["first_odds"]) for r in rows]
    pf = [r["profit"] for r in rows if r["result"] in ("win", "loss")]
    se = None
    if len(pf) > 1:
        mu = sum(pf) / len(pf)
        se = round((sum((x - mu) ** 2 for x in pf) / (len(pf) - 1)) ** 0.5 / len(pf) ** 0.5 / 10, 4)
    return {"n": n, "w": w, "l": l, "p": pu, "profit": round(profit, 2), "roi": round(profit / staked, 4) if staked else None, "roiSE": se,
            "winRate": round(w / (w + l), 4) if w + l else None, "expWinRate": round(exp_w / (w + l), 4) if w + l else None,
            "expProfit": round(exp_profit, 2), "clv": round(sum(clv) / n, 4),
            "beatClose": round(sum(c > 0 for c in clv) / n, 4)}


def build_results(log, now):
    rows = [r for r in log.values() if r["status"] == "graded"]
    groups = {
        "Edge when first flagged": lambda r: bucket_edge(r["first_edge"]),
        "Books behind true prob": lambda r: str(r["first_books"]) if r["first_books"] < 4 else "4+",
        "Sport": lambda r: r["sport"],
        "Book": lambda r: "DraftKings" if r["book"] == "dk" else "FanDuel",
        "Side": lambda r: "Over" if r["side"] == "o" else "Under",
        "Price": lambda r: bucket_price(r["first_odds"]),
    }
    order = {"Edge when first flagged": ["0–1%", "1–2%", "2–3%", "3–5%", "5%+"],
             "Books behind true prob": ["2", "3", "4+"], "Sport": ["NFL", "CFB", "NBA", "NCAAB"],
             "Price": ["−300 or less", "−299 to −151", "−150 to −101", "+100 to +199", "+200 or more"]}
    out_groups = []
    for name, fn in groups.items():
        by = {}
        for r in rows:
            by.setdefault(fn(r), []).append(r)
        keys = [k for k in order.get(name, sorted(by)) if k in by]
        out_groups.append({"name": name, "rows": [{"label": k, **summarize(by[k])} for k in keys]})
    daily = {}
    for r in sorted(rows, key=lambda r: r["start"]):
        d = parse(r["start"]).astimezone(timezone(timedelta(hours=-5))).date().isoformat()
        daily[d] = daily.get(d, 0) + r["profit"]
    run, curve = 0.0, []
    for d, pf in daily.items():
        run += pf
        curve.append({"date": d, "profit": round(run, 2)})
    recent = sorted([r for r in log.values() if r["status"] in ("graded", "void")],
                    key=lambda r: r["start"], reverse=True)[:400]
    keep = ("sport", "player", "team", "statLabel", "line", "side", "book", "first_odds", "first_true", "first_edge",
            "first_books", "last_odds", "last_true", "result", "actual", "profit", "start", "first_seen")
    return {"updatedAt": now.isoformat(timespec="seconds"), "since": min((r["first_seen"] for r in log.values()), default=None),
            "pending": sum(r["status"] == "pending" for r in log.values()),
            "voids": sum(r["status"] == "void" for r in log.values()),
            "overall": summarize(rows), "groups": out_groups, "curve": curve,
            "recent": [{k: r.get(k) for k in keep} for r in recent]}


def main():
    with open(os.path.join(ROOT, "docs", "data.json")) as f:
        data = json.load(f)
    log = {}
    if os.path.exists(LOG):
        with open(LOG) as f:
            log = json.load(f)
    now = datetime.now(timezone.utc)
    added, updated = log_plays(log, data)
    graded, fetched = (0, 0)
    if KEY:
        graded, fetched = grade(log, now)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w") as f:
        json.dump(log, f, separators=(",", ":"))
    with open(OUT, "w") as f:
        json.dump(build_results(log, now), f, separators=(",", ":"))
    print(f"logged {added} new plays, updated {updated}, graded {graded} ({fetched} SGO objects); "
          f"{sum(r['status'] == 'pending' for r in log.values())} pending")


if __name__ == "__main__":
    main()
