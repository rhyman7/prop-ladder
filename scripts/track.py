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
Log: data/plays_log.json (not served). Summary: docs/results.json, plus
docs/results_plays.json (one short row per graded play, for the page's filters).
"""
import json
import math
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


def log_plays(log, data, only=None):
    now = parse(data["pulledAt"])
    added = updated = 0
    for p in data["props"]:
        if not p.get("start") or parse(p["start"]) <= now:
            continue
        if only == "pin" and not p.get("pin"):
            continue   # Pinnacle log: only props Pinnacle actually prices
        for r in p["rungs"]:
            for side in ("o", "u"):
                pw = r["po"] if side == "o" else r["pu"]
                for bk in ("dk", "fd", "ka"):
                    key = f'{p["game"]}|{p["pid"]}|{p["stat"]}|{r["l"]}|{side}|{bk}'
                    odds = r.get(bk + side)
                    row = log.get(key)
                    if row and row["status"] == "pending":
                        # refresh the "last before kickoff" view, flagged or not,
                        # but only from a newer pull than the one already recorded
                        if p.get("asOf", data["pulledAt"]) <= row["last_seen"]:
                            continue
                        row["last_true"] = pw
                        row["last_books"] = r["n"]
                        row["last_seen"] = p.get("asOf", data["pulledAt"])
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
                        "first_seen": p.get("asOf", data["pulledAt"]), "first_odds": odds, "first_true": round(pw, 4),
                        "first_edge": round(edge, 4), "first_books": r["n"],
                        "last_seen": p.get("asOf", data["pulledAt"]), "last_odds": odds, "last_true": round(pw, 4), "last_books": r["n"],
                    }
                    added += 1
    return added, updated


def due_games(logs, compare, now):
    cut = now - timedelta(hours=GRADE_AFTER_H)
    games = {row["game"] for log in logs for row in log.values()
             if row["status"] == "pending" and parse(row["start"]) < cut}
    games |= {k.split("|")[0] for k, c in compare.items() if c.get("r") is None and parse(c["s"]) < cut}
    return sorted(games)[:MAX_GRADE]


def fetch_events(games):
    evs = {}
    for i in range(0, len(games), 10):
        chunk = games[i:i + 10]
        resp = get({"eventIDs": ",".join(chunk), "limit": len(chunk)})
        time.sleep(3)
        if "data" not in resp:
            print("grade fetch:", resp.get("error"), file=sys.stderr)
            continue
        for ev in resp["data"]:
            evs[ev.get("eventID")] = ev
    return evs


def final_score(ev, pid, stat):
    """('final'|'void'|'wait', score)."""
    stt = ev.get("status") or {}
    if stt.get("cancelled"):
        return "void", None
    if not (stt.get("finalized") or stt.get("ended") or stt.get("completed")):
        return "wait", None
    odds = ev.get("odds") or {}
    o = odds.get(f"{stat}-{pid}-game-ou-over") or {}
    if o.get("score") is None and stat == "touchdowns":
        o = odds.get(f"touchdowns-{pid}-game-yn-yes") or o   # anytime TD only listed as Yes/No
    if o.get("score") is None:
        return ("dnp", None) if stt.get("finalized") else ("wait", None)
    return "final", float(o["score"])


def grade(log, evs, now):
    graded = 0
    for row in log.values():
        if row["status"] != "pending" or row["game"] not in evs:
            continue
        state, score = final_score(evs[row["game"]], row["pid"], row["stat"])
        if state == "wait":
            continue
        if state == "void" or (state == "dnp" and row["book"] != "ka"):
            row.update(status="void", result="void", actual=None, graded_at=now.isoformat(timespec="seconds"))
            graded += 1
            continue
        ln = float(row["line"])
        if state == "dnp":
            # Kalshi (non-Protected): a player who doesn't play resolves NO
            res = "loss" if row["side"] == "o" else "win"
        else:
            res = "push" if score == ln else "win" if (score > ln) == (row["side"] == "o") else "loss"
        pr = profit10(row["first_odds"])
        row.update(status="graded", result=res, actual=score, graded_at=now.isoformat(timespec="seconds"),
                   profit=round(pr if res == "win" else -10.0 if res == "loss" else 0.0, 2))
        graded += 1
    return graded


def log_compare(compare, cons, wide, use=lambda p, r: r.get("sf")):
    """Every rung both versions price where the other version differs (Wide: 2+
    sharp books; Pinnacle: Pinnacle prices the prop): first and last
    pre-kickoff P(over) from each (c = 9-book, w = the other version)."""
    now = parse(wide["pulledAt"])
    cmap = {}
    for p in cons["props"]:
        for r in p["rungs"]:
            cmap[f'{p["game"]}|{p["pid"]}|{p["stat"]}|{r["l"]}'] = r["po"]
    n = 0
    for p in wide["props"]:
        if not p.get("start") or parse(p["start"]) <= now:
            continue
        for r in p["rungs"]:
            if not use(p, r) or float(r["l"]).is_integer():
                continue
            key = f'{p["game"]}|{p["pid"]}|{p["stat"]}|{r["l"]}'
            if key not in cmap:
                continue
            c = compare.get(key)
            if c is None:
                compare[key] = {"s": p["start"], "sp": p["sport"], "c1": cmap[key], "w1": r["po"],
                                "c": cmap[key], "w": r["po"], "ns": r.get("ns"), "r": None}
            elif c.get("r") is None:
                c.update(c=cmap[key], w=r["po"], ns=r.get("ns"))
            n += 1
    return n


def grade_compare(compare, evs):
    n = 0
    for key, c in compare.items():
        if c.get("r") is not None:
            continue
        game, pid, stat, line = key.split("|")
        if game not in evs:
            continue
        state, score = final_score(evs[game], pid, stat)
        if state == "wait":
            continue
        c["r"] = "v" if state in ("void", "dnp") else (1 if score > float(line) else 0)
        n += 1
    return n


def compare_summary(compare, now):
    rows = [(k, c) for k, c in compare.items() if c.get("r") in (0, 1)]

    def stats(sub, a, b):
        if not sub:
            return None
        bs = lambda p, y: (p - y) ** 2
        ll = lambda p, y: -math.log(min(max(p if y else 1 - p, 1e-4), 1))
        # cluster by prop (game|player|stat): rungs of one prop are not independent
        by = {}
        for k, c in sub:
            by.setdefault(k.rsplit("|", 1)[0], []).append(bs(c[b], c["r"]) - bs(c[a], c["r"]))
        d = [sum(v) / len(v) for v in by.values()]
        mu = sum(d) / len(d)
        se = (sum((x - mu) ** 2 for x in d) / (len(d) - 1)) ** .5 / len(d) ** .5 if len(d) > 1 else None
        return {"rungs": len(sub), "props": len(by),
                "brier9": round(sum(bs(c[a], c["r"]) for _, c in sub) / len(sub), 5),
                "brierWide": round(sum(bs(c[b], c["r"]) for _, c in sub) / len(sub), 5),
                "logloss9": round(sum(ll(c[a], c["r"]) for _, c in sub) / len(sub), 4),
                "loglossWide": round(sum(ll(c[b], c["r"]) for _, c in sub) / len(sub), 4),
                "diff": round(mu, 5), "diffSE": round(se, 5) if se else None,
                "meanGap": round(sum(abs(c[b] - c[a]) for _, c in sub) / len(sub), 4)}

    out = {"updatedAt": now.isoformat(timespec="seconds"),
           "tracked": len(compare), "pending": sum(c.get("r") is None for c in compare.values()),
           "last": stats(rows, "c", "w"), "first": stats(rows, "c1", "w1"), "bySport": []}
    for sp in ("NFL", "CFB", "NBA", "NCAAB"):
        sub = [(k, c) for k, c in rows if c["sp"] == sp]
        if sub:
            out["bySport"].append({"sport": sp, **stats(sub, "c", "w")})
    return out


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
    # SE of ROI clustered by prop (game|player|stat): rungs of one prop win or
    # lose together, so treating them as independent overstates certainty.
    by = {}
    for r in rows:
        if r["result"] in ("win", "loss"):
            k = (r["game"], r["pid"], r["stat"])
            t = by.setdefault(k, [0.0, 0.0])
            t[0] += r["profit"]
            t[1] += 10.0
    se = None
    if len(by) > 1 and staked:
        roi = profit / staked
        resid = [pf - roi * stk for pf, stk in by.values()]
        se = round((len(by) / (len(by) - 1) * sum(x * x for x in resid)) ** 0.5 / staked, 4)
    return {"n": n, "w": w, "l": l, "p": pu, "profit": round(profit, 2), "roi": round(profit / staked, 4) if staked else None, "roiSE": se,
            "winRate": round(w / (w + l), 4) if w + l else None, "expWinRate": round(exp_w / (w + l), 4) if w + l else None,
            "expProfit": round(exp_profit, 2), "clv": round(sum(clv) / n, 4),
            "beatClose": round(sum(c > 0 for c in clv) / n, 4)}


BOOK_NAMES = {"dk": "DraftKings", "fd": "FanDuel", "ka": "Kalshi"}
# The Results breakdowns, in page order: (name, play -> label, every label in order).
# The same list drives the filter buttons on the Results page (results_plays.json).
DIMS = [
    ("Edge when first flagged", lambda r: bucket_edge(r["first_edge"]), ["0–1%", "1–2%", "2–3%", "3–5%", "5%+"]),
    ("Books behind true prob", lambda r: str(r["first_books"]) if r["first_books"] < 4 else "4+", ["2", "3", "4+"]),
    ("Sport", lambda r: r["sport"], ["NFL", "CFB", "NBA", "NCAAB"]),
    ("Book", lambda r: BOOK_NAMES[r["book"]], ["DraftKings", "FanDuel", "Kalshi"]),
    ("Side", lambda r: "Over" if r["side"] == "o" else "Under", ["Over", "Under"]),
    ("Price", lambda r: bucket_price(r["first_odds"]), ["−300 or less", "−299 to −151", "−150 to −101", "+100 to +199", "+200 or more"]),
]


# The Price filter buttons on Results use the All +EV plays page's ranges
# (PRICES in docs/plays.html; keep the two the same). The Price table keeps
# bucket_price's five rows.
PRICE_FILTER = [("−700 or less", lambda a: a <= -700), ("−500 to −699", lambda a: -700 < a <= -500),
                ("−300 to −499", lambda a: -500 < a <= -300), ("−100 to −299", lambda a: -300 < a <= -100),
                ("+100", lambda a: a == 100), ("+101 to +299", lambda a: 100 < a < 300), ("+300 or more", lambda a: a >= 300)]


# True prob buttons (Ryan, Nov 27): the true probability when first flagged, in
# tens, highest first. Buttons only; there is no True prob table.
TRUE_FILTER = ["90–100%", "80–89%", "70–79%", "60–69%", "50–59%", "40–49%", "30–39%", "20–29%", "10–19%", "0–9%"]


def true_filter_idx(p):
    return 9 - min(int(p * 10 + 1e-9), 9)


def price_filter_idx(a):
    return next(i for i, (_, f) in enumerate(PRICE_FILTER) if f(a))


def game_day(r):
    return parse(r["start"]).astimezone(timezone(timedelta(hours=-5))).date().isoformat()


def dim_idx(r):
    return [labels.index(fn(r)) for _, fn, labels in DIMS]


def build_results(log, now):
    rows = [r for r in log.values() if r["status"] == "graded"]
    out_groups = []
    for name, fn, labels in DIMS:
        by = {}
        for r in rows:
            by.setdefault(fn(r), []).append(r)
        out_groups.append({"name": name, "rows": [{"label": k, **summarize(by[k])} for k in labels if k in by]})
    daily = {}
    for r in sorted(rows, key=lambda r: r["start"]):
        d = game_day(r)
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
            "recent": [{**{k: r.get(k) for k in keep}, "b": dim_idx(r)} for r in recent]}


def build_plays(log, now):
    """Every graded or void play, one short row each, so the Results page can
    redo its numbers and its list of plays for any combination of the filter
    buttons. Row: the six DIMS label indexes, first price, first true prob x
    1e4, last true prob x 1e6, result (0 loss, 1 win, 2 push, 3 void), game-day
    index, prop index (game|player|stat, for the clustered standard error),
    then for the list: player, team and stat indexes, line, first edge x 1e4,
    first books, last price, actual, kickoff index, Price-button index,
    True-prob-button index.
    `filters` lists the button groups: name, labels and the row column each
    reads (the tables' own columns, except Price). `updatedAt` must equal
    results.json's: the page ignores this file when they differ."""
    rows = sorted((r for r in log.values() if r["status"] in ("graded", "void")), key=lambda r: r["start"])
    days, props, players, teams, stats, starts, out = {}, {}, {}, {}, {}, {}, []
    ix = lambda table, v: table.setdefault(v, len(table))
    for r in rows:
        out.append(dim_idx(r) + [
            r["first_odds"], round(r["first_true"] * 1e4), round(r["last_true"] * 1e6),
            {"loss": 0, "win": 1, "push": 2, "void": 3}[r["result"]], ix(days, game_day(r)),
            ix(props, (r["game"], r["pid"], r["stat"])),
            ix(players, r["player"]), ix(teams, r.get("team") or ""), ix(stats, r["statLabel"]), r["line"],
            round(r["first_edge"] * 1e4), r["first_books"], r.get("last_odds"), r.get("actual"), ix(starts, r["start"]),
            price_filter_idx(r["first_odds"]), true_filter_idx(r["first_true"])])
    filters = [{"name": n, "labels": l, "col": i} for i, (n, _, l) in enumerate(DIMS)]
    filters[-1] = {"name": "Price", "labels": [l for l, _ in PRICE_FILTER], "col": 21}
    filters.append({"name": "True prob when first flagged", "labels": TRUE_FILTER, "col": 22})
    return {"updatedAt": now.isoformat(timespec="seconds"), "dims": [{"name": n, "labels": l} for n, _, l in DIMS],
            "filters": filters, "days": list(days), "players": list(players), "teams": list(teams), "stats": list(stats), "starts": list(starts),
            "rows": out}


VERSIONS = [
    ("9-book", "docs/data.json", "data/plays_log.json", "docs/results.json"),
    ("wide", "docs/wide/data.json", "data/wide_plays_log.json", "docs/wide/results.json"),
    ("pinnacle", "docs/pinnacle/data.json", "data/pin_plays_log.json", "docs/pinnacle/results.json"),
]
COMPARES = [  # (other version, log, summary, which rungs)
    ("wide", "data/compare_log.json", "docs/compare.json", lambda p, r: r.get("sf")),
    ("pinnacle", "data/compare_pin_log.json", "docs/compare_pin.json", lambda p, r: p.get("pin")),
]


def load(path, default):
    path = os.path.join(ROOT, path) if not os.path.isabs(path) else path
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save(path, obj):
    path = os.path.join(ROOT, path) if not os.path.isabs(path) else path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, separators=(",", ":"))


def main():
    now = datetime.now(timezone.utc)
    vers = []
    for name, data_p, log_p, out_p in VERSIONS:
        data = load(data_p, None)
        if data is None:
            continue
        log = load(log_p, {})
        added, updated = log_plays(log, data, only="pin" if name == "pinnacle" else None)
        vers.append((name, data, log, log_p, out_p))
        print(f"{name}: logged {added} new plays, updated {updated}")
    d = {v[0]: v[1] for v in vers}
    comps = []
    for other, log_p, out_p, use in COMPARES:
        comp = load(log_p, {})
        if "9-book" in d and other in d:
            print(f"compare {other}: {log_compare(comp, d['9-book'], d[other], use)} rungs updated, {len(comp)} tracked")
        comps.append((other, comp, log_p, out_p))
    if KEY:
        games = due_games([v[2] for v in vers], {k: v for _, c, _, _ in comps for k, v in c.items()}, now)
        evs = fetch_events(games) if games else {}
        for name, data, log, log_p, out_p in vers:
            print(f"{name}: graded {grade(log, evs, now)}")
        for other, comp, _, _ in comps:
            print(f"compare {other}: graded {grade_compare(comp, evs)} rungs")
        print(f"{len(evs)} SGO objects for grading")
    for name, data, log, log_p, out_p in vers:
        save(log_p, log)
        save(out_p, build_results(log, now))
        save(out_p.replace("results.json", "results_plays.json"), build_plays(log, now))
    for other, comp, log_p, out_p in comps:
        save(log_p, comp)
        save(out_p, compare_summary(comp, now))


if __name__ == "__main__":
    main()
