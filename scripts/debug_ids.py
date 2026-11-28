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
    out.append({"event": ev.get("eventID"), "n": len(ids), "ids": ids[:60],
                "example": ex, "example_partner": odds.get((ex or {}).get("opposingOddID") or "")})
json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "coverage", "debug_ids.json"), "w"), indent=1)
print([(o["event"], o["n"]) for o in out])
