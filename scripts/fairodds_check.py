"""Check SportsGameOdds' fairOdds against our own vig removal, and how much of
each prop ladder can be de-vigged straight from the books.

1. Main line: for each player prop, de-vig every book quoting both Over and Under
   at SGO's fairOverUnder (simple and power methods), take the median, and
   compare with the probability SGO's fairOdds implies.
2. Ladder: for each rung (main + altLines), count books quoting BOTH sides at
   that number. A rung with 2+ such books can get a market true probability
   without any curve.

Key from SGO_API_KEY. About one object per event; capped per league.
Writes coverage/fairodds_report.md and coverage/fairodds.json.
"""
import json
import os
import statistics as st
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

BASE = "https://api.sportsgameodds.com/v2"
KEY = os.environ.get("SGO_API_KEY", "")
OUT = os.path.join(os.path.dirname(__file__), "..", "coverage")
CAPS = {"NFL": (16, 5), "NCAAF": (20, 5), "NBA": (12, 2), "NCAAB": (15, 2)}  # (max events, days ahead)
TEAM = {"home", "away", "all"}


def get(path, params):
    url = f"{BASE}/{path}/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-Api-Key": KEY})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(10)
                continue
            return {"success": False, "error": f"{e.code} {e.read()[:300]!r}"}
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            return {"success": False, "error": repr(e)}


def imp(a):
    a = float(a)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def power(po, pu):
    lo, hi = 0.5, 10.0
    for _ in range(80):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1:
            lo = k
        else:
            hi = k
    return po ** k


def quotes(q):
    """{line: (odds, available)} for a byBookmaker entry, main + alts."""
    out = {}
    if q.get("overUnder") is not None and q.get("odds"):
        out[float(q["overUnder"])] = (q["odds"], bool(q.get("available")))
    for a in q.get("altLines") or []:
        if a.get("overUnder") is not None and a.get("odds"):
            out.setdefault(float(a["overUnder"]), (a["odds"], bool(a.get("available"))))
    return out


def main():
    if not KEY:
        sys.exit("SGO_API_KEY is not set")
    now = datetime.now(timezone.utc)
    iso = lambda d: d.isoformat(timespec="seconds").replace("+00:00", "Z")
    report = {"run_at": iso(now), "leagues": {}}
    examples = []
    for lg, (cap, days) in CAPS.items():
        events, cursor = [], None
        while len(events) < cap:
            p = {"leagueID": lg, "oddsAvailable": "true", "includeAltLines": "true",
                 "startsAfter": iso(now), "startsBefore": iso(now + timedelta(days=days)),
                 "limit": min(10, cap - len(events))}
            if cursor:
                p["cursor"] = cursor
            r = get("events", p)
            time.sleep(7)
            if "data" not in r:
                report["leagues"][lg] = {"error": r}
                break
            events += r["data"]
            cursor = r.get("nextCursor")
            if not cursor or not r["data"]:
                break

        diffs_simple, diffs_power = [], []
        props = with_fair = compared = 0
        rungs = Counter()          # rungs by number of two-sided books
        rungs_dkfd = Counter()     # rungs DK or FD quotes (Over side) and how many two-sided books
        fair_vs_dk_line = Counter()
        for ev in events:
            odds = ev.get("odds") or {}
            for oid, o in odds.items():
                ent = o.get("statEntityID") or ""
                if o.get("betTypeID") != "ou" or o.get("sideID") != "over" or ent in TEAM or not o.get("playerID"):
                    continue
                u = odds.get(o.get("opposingOddID") or "")
                if not u:
                    continue
                props += 1
                ob, ub = o.get("byBookmaker") or {}, u.get("byBookmaker") or {}
                oq = {b: quotes(q) for b, q in ob.items()}
                uq = {b: quotes(q) for b, q in ub.items()}
                # ladder: per line, books with both sides open
                lines = set()
                for b in oq:
                    lines |= set(oq[b])
                for ln in lines:
                    n = sum(1 for b in oq if ln in oq[b] and ln in uq.get(b, {})
                            and oq[b][ln][1] and uq[b][ln][1])
                    rungs[min(n, 4)] += 1
                    if any(ln in oq.get(b, {}) and oq[b][ln][1] for b in ("draftkings", "fanduel")):
                        rungs_dkfd[min(n, 4)] += 1
                # main line vs SGO fair
                if not (o.get("fairOddsAvailable") and o.get("fairOdds") and o.get("fairOverUnder")):
                    continue
                with_fair += 1
                fl = float(o["fairOverUnder"])
                dk = ob.get("draftkings", {}).get("overUnder")
                if dk is not None:
                    fair_vs_dk_line["same" if float(dk) == fl else "different"] += 1
                s, pw = [], []
                for b in oq:
                    if fl in oq[b] and fl in uq.get(b, {}) and oq[b][fl][1] and uq[b][fl][1]:
                        po, pu = imp(oq[b][fl][0]), imp(uq[b][fl][0])
                        s.append(po / (po + pu))
                        pw.append(power(po, pu))
                if len(s) >= 2:
                    compared += 1
                    sgo = imp(o["fairOdds"])
                    diffs_simple.append(sgo - st.median(s))
                    diffs_power.append(sgo - st.median(pw))
                    if len(examples) < 12 and lg in ("NFL", "NBA"):
                        examples.append({"league": lg, "market": o.get("marketName"), "line": fl,
                                         "sgo_fair": o["fairOdds"], "sgo_prob": round(sgo, 4),
                                         "ours_simple": round(st.median(s), 4), "ours_power": round(st.median(pw), 4),
                                         "books": len(s)})

        def summ(d):
            if not d:
                return None
            ad = [abs(x) for x in d]
            return {"n": len(d), "mean": round(st.mean(d) * 100, 2), "mean_abs": round(st.mean(ad) * 100, 2),
                    "median_abs": round(st.median(ad) * 100, 2),
                    "share_within_1pt": round(sum(x <= 0.01 for x in ad) / len(ad), 3),
                    "max_abs": round(max(ad) * 100, 2)}

        report["leagues"].setdefault(lg, {}).update({
            "events": len(events), "props": props, "with_fairOdds": with_fair, "compared": compared,
            "sgo_minus_ours_simple_pts": summ(diffs_simple), "sgo_minus_ours_power_pts": summ(diffs_power),
            "rungs_by_two_sided_books": dict(sorted(rungs.items())),
            "dkfd_rungs_by_two_sided_books": dict(sorted(rungs_dkfd.items())),
            "fair_line_vs_dk_line": dict(fair_vs_dk_line)})

    report["examples"] = examples
    with open(os.path.join(OUT, "fairodds.json"), "w") as f:
        json.dump(report, f, indent=1)
    L = [f"# fairOdds check — {report['run_at']}", "",
         "Differences are SGO's fair probability minus our median de-vigged probability, in percentage points.", ""]
    for lg, r in report["leagues"].items():
        L.append(f"## {lg}")
        L.append("```")
        L.append(json.dumps(r, indent=1))
        L.append("```")
    L.append("## Examples")
    for e in examples:
        L.append(f"- {e}")
    with open(os.path.join(OUT, "fairodds_report.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
