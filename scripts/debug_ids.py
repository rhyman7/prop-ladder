"""Dump odd IDs matching a pattern for a couple of upcoming events, plus one full
example. Env: LEAGUE, PATTERN. Writes coverage/debug_ids.json. ~2 objects."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import build as b
from datetime import datetime, timezone
evs = b.pull(os.environ["LEAGUE"], 2, 7, datetime.now(timezone.utc))
pat = re.compile(os.environ["PATTERN"], re.I)
out = []
for ev in evs:
    odds = ev.get("odds") or {}
    ids = sorted(k for k in odds if pat.search(k))
    ex = odds[ids[0]] if ids else None
    books = {}
    for k in ids:
        for bk in (odds[k].get("byBookmaker") or {}):
            books.setdefault(k.split("-")[-2] + "-" + k.split("-")[-1], {}).setdefault(bk, 0)
            books[k.split("-")[-2] + "-" + k.split("-")[-1]][bk] += 1
    rich = max(ids, key=lambda k: len(odds[k].get("byBookmaker") or {}), default=None)
    out.append({"event": ev.get("eventID"), "n": len(ids), "ids": ids[:60], "books_by_side": books,
                "richest": odds.get(rich) if rich else None,
                "example": ex, "example_partner": odds.get((ex or {}).get("opposingOddID") or "")})
json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "coverage", "debug_ids.json"), "w"), indent=1)
print([(o["event"], o["n"]) for o in out])
