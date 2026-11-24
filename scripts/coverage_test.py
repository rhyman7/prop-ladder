"""One-off coverage test for SportsGameOdds (SGO).

Answers: for NFL, college football, NBA and college basketball, how many player
props does Pinnacle actually post, does it post alternate lines, and how deep are
DraftKings' and FanDuel's ladders?

Reads the key from the SGO_API_KEY environment variable (a GitHub secret).
Writes coverage/report.md, coverage/summary.json and trimmed raw samples under
coverage/samples/. Stdlib only. Costs one object per event returned (free plan:
2,500 objects a month); capped by MAX_EVENTS per league.
"""
import json
import os
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
BOOKS = ["pinnacle", "draftkings", "fanduel"]
MAX_EVENTS = int(os.environ.get("MAX_EVENTS", "25"))  # per league
# League IDs we expect; checked against /leagues before use.
LEAGUES = {"NFL": 5, "NCAAF": 5, "NBA": 2, "NCAAB": 2}  # value = days ahead
TEAM_ENTITIES = {"home", "away", "all"}


def get(path, params=None):
    url = f"{BASE}/{path.strip('/')}/"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-Api-Key": KEY, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            if e.code == 429 and attempt < 2:
                time.sleep(10)
                continue
            return {"success": False, "http": e.code, "error": body}
        except Exception as e:  # network
            if attempt < 2:
                time.sleep(5)
                continue
            return {"success": False, "error": repr(e)}
    time.sleep(7)  # stay under 10 requests a minute


def is_player_prop(odd):
    ent = odd.get("statEntityID") or ""
    return bool(odd.get("playerID")) or (ent and ent not in TEAM_ENTITIES)


def main():
    if not KEY:
        sys.exit("SGO_API_KEY is not set")
    os.makedirs(os.path.join(OUT, "samples"), exist_ok=True)
    now = datetime.now(timezone.utc)
    summary = {"run_at": now.isoformat(timespec="seconds"), "leagues": {}}

    summary["usage_before"] = get("account/usage")
    time.sleep(7)
    leagues_resp = get("leagues")
    known = {l.get("leagueID") for l in (leagues_resp.get("data") or [])} if isinstance(leagues_resp, dict) else set()
    summary["leagues_available"] = sorted(x for x in known if x)
    time.sleep(7)

    for league, days in LEAGUES.items():
        res = {"requested": True}
        summary["leagues"][league] = res
        if known and league not in known:
            res["error"] = "league ID not in /leagues for this key"
            continue
        events, cursor = [], None
        while len(events) < MAX_EVENTS:
            params = {
                "leagueID": league,
                "oddsAvailable": "true",
                "includeAltLines": "true",
                "startsAfter": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "startsBefore": (now + timedelta(days=days)).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "limit": min(10, MAX_EVENTS - len(events)),
            }
            if cursor:
                params["cursor"] = cursor
            resp = get("events", params)
            time.sleep(7)
            if not resp.get("success", True) or "data" not in resp:
                res["error"] = resp
                break
            events += resp["data"]
            cursor = resp.get("nextCursor")
            if not cursor or not resp["data"]:
                break
        res["events"] = len(events)

        books_seen = Counter()
        props = {b: 0 for b in BOOKS}            # over/under player-prop sides quoted
        props_avail = {b: 0 for b in BOOKS}
        markets = {b: Counter() for b in BOOKS}  # statID -> count of player-prop markets
        alt = {b: {"markets_with_alts": 0, "alt_rungs": 0} for b in BOOKS}
        players_pin = set()
        bm_keys = defaultdict(Counter)           # field names seen inside byBookmaker entries
        sample = None

        for ev in events:
            for oid, odd in (ev.get("odds") or {}).items():
                bb = odd.get("byBookmaker") or {}
                for b in bb:
                    books_seen[b] += 1
                if not is_player_prop(odd) or odd.get("betTypeID") != "ou" or odd.get("sideID") != "over":
                    continue
                for b in BOOKS:
                    q = bb.get(b)
                    if not q:
                        continue
                    for k in q:
                        bm_keys[b][k] += 1
                    props[b] += 1
                    props_avail[b] += bool(q.get("available"))
                    markets[b][odd.get("statID")] += 1
                    if b == "pinnacle":
                        players_pin.add(odd.get("playerID") or odd.get("statEntityID"))
                    alts = q.get("altLines") or q.get("altlines") or []
                    if alts:
                        alt[b]["markets_with_alts"] += 1
                        alt[b]["alt_rungs"] += len(alts)
                if sample is None and "pinnacle" in bb:
                    sample = {"eventID": ev.get("eventID"), "oddID": oid, "odd": odd}

        res.update({
            "bookmakers_seen_any_market": dict(books_seen.most_common()),
            "player_prop_markets": props,
            "player_prop_markets_open": props_avail,
            "pinnacle_players": len(players_pin),
            "stats_by_book": {b: dict(markets[b].most_common()) for b in BOOKS},
            "alt_lines": alt,
            "byBookmaker_fields": {b: dict(bm_keys[b]) for b in BOOKS},
        })
        if sample:
            with open(os.path.join(OUT, "samples", f"{league}.json"), "w") as f:
                json.dump(sample, f, indent=1)
        # one DK/FD prop sample too, to see how their ladders look
        for b in ("draftkings", "fanduel"):
            for ev in events:
                hit = next((o for o in (ev.get("odds") or {}).values()
                            if is_player_prop(o) and (o.get("byBookmaker") or {}).get(b, {}).get("altLines")), None)
                if hit:
                    with open(os.path.join(OUT, "samples", f"{league}_{b}_alt.json"), "w") as f:
                        json.dump(hit, f, indent=1)
                    break

    summary["usage_after"] = get("account/usage")
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)

    lines = [f"# SportsGameOdds coverage test — {summary['run_at']}", ""]
    lines.append(f"Leagues on this key: {', '.join(summary['leagues_available']) or 'unknown'}")
    lines.append("")
    lines.append("| League | Events | Pinnacle props (open) | Pinnacle players | Pinnacle alt rungs | DK props | DK alt rungs | FD props | FD alt rungs |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for lg, r in summary["leagues"].items():
        if "error" in r and not r.get("events"):
            lines.append(f"| {lg} | error: {str(r['error'])[:120]} |||||||| ")
            continue
        p, a = r["player_prop_markets"], r["alt_lines"]
        lines.append(
            f"| {lg} | {r['events']} | {p['pinnacle']} ({r['player_prop_markets_open']['pinnacle']}) | {r['pinnacle_players']} "
            f"| {a['pinnacle']['alt_rungs']} | {p['draftkings']} | {a['draftkings']['alt_rungs']} | {p['fanduel']} | {a['fanduel']['alt_rungs']} |")
    lines.append("")
    for lg, r in summary["leagues"].items():
        if r.get("events"):
            lines.append(f"## {lg}")
            lines.append(f"- Books seen on any market: {r['bookmakers_seen_any_market']}")
            for b in BOOKS:
                lines.append(f"- {b} stats: {r['stats_by_book'][b]}")
            lines.append("")
    with open(os.path.join(OUT, "report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
