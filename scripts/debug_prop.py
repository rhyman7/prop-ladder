"""Dump every book's raw quotes for one player prop. Env: LEAGUE, PLAYER (name
substring), STAT. Writes coverage/debug_prop.json. ~1 object per event."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build as b
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
lg, who, stat = os.environ["LEAGUE"], os.environ["PLAYER"].lower(), os.environ["STAT"]
out = []
for ev in b.pull(lg, 15, 2, now):
    players = ev.get("players") or {}
    for pid, pl in players.items():
        if who not in (pl.get("name") or "").lower():
            continue
        odds = ev.get("odds") or {}
        for side in ("over", "under"):
            o = odds.get(f"{stat}-{pid}-game-ou-{side}")
            if o:
                out.append({"side": side, "oddID": o.get("oddID"), "fair": o.get("fairOdds"), "fairOU": o.get("fairOverUnder"),
                            "byBookmaker": o.get("byBookmaker")})
json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "coverage", "debug_prop.json"), "w"), indent=1)
print(len(out), "entries")
