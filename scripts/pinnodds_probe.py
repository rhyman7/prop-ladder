"""One-off: what Pinnacle player props does PinnOdds carry for NFL, NCAAF, NBA,
NCAAB? Uses ~2-12 requests of the trial's 100/day. Key: PINNODDS_API_KEY.
Writes coverage/pinnodds_probe.json (summary + a few raw samples)."""
import json, os, re, time, urllib.parse, urllib.request
from collections import Counter, defaultdict
KEY = os.environ["PINNODDS_API_KEY"]
BASE = "https://pinnodds.com/kit/v1"
OUT = os.path.join(os.path.dirname(__file__), "..", "coverage", "pinnodds_probe.json")
calls = 0


def get(path, params):
    global calls
    calls += 1
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-portal-apikey": KEY, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read()[:300]!r}"}
    except Exception as e:
        return {"error": repr(e)}


out = {"sports": {}}
for sid, name in ((5, "Football"), (3, "Basketball")):
    r = get("prematch/fixtures", {"sport_id": sid, "include_specials": "nested"})
    time.sleep(3)
    if "error" in r:
        out["sports"][name] = {"error": r["error"]}
        continue
    evs = r.get("events") or []
    leagues = Counter(e.get("league_name") for e in evs)
    us = [e for e in evs if re.search(r"NFL|NCAA|NBA", e.get("league_name") or "", re.I)]
    cats, props_by_league, names, shapes = Counter(), Counter(), defaultdict(Counter), []
    with_prices = 0
    for e in us:
        for sp in e.get("specials") or []:
            cats[sp.get("special_category")] += 1
            if sp.get("special_category") != "Player Props":
                continue
            props_by_league[e.get("league_name")] += 1
            # the stat is usually in brackets or after the player name
            nm = sp.get("special") or ""
            m = re.search(r"\(([^)]+)\)", nm)
            names[e.get("league_name")][m.group(1) if m else re.sub(r"^[A-Z][\w.'-]+ [A-Z][\w.'-]+\s*", "", nm)[:40]] += 1
            if sp.get("special_markets"):
                with_prices += 1
            if len(shapes) < 6:
                shapes.append({"league": e.get("league_name"), "parent": f'{e.get("away")} @ {e.get("home")}', "starts": e.get("starts"),
                               "special": nm, "units": sp.get("special_units"), "event_id": sp.get("event_id"),
                               "special_markets": sp.get("special_markets")})
    out["sports"][name] = {"events": len(evs), "leagues_top": leagues.most_common(25), "us_events": len(us),
                           "special_categories": dict(cats), "player_props_by_league": dict(props_by_league),
                           "player_props_with_prices_inline": with_prices,
                           "prop_types_by_league": {k: v.most_common(30) for k, v in names.items()}, "samples": shapes}
# if prices weren't inline, fetch a few specials' markets
for name, s in out["sports"].items():
    if "samples" not in s:
        continue
    for smp in s["samples"][:5]:
        if not smp.get("special_markets") and smp.get("event_id"):
            smp["markets_call"] = get("prematch/markets", {"event_id": smp["event_id"]})
            time.sleep(3)
out["requests_used"] = calls
json.dump(out, open(OUT, "w"), indent=1, default=str)
print("requests used:", calls)
for name, s in out["sports"].items():
    print(name, {k: s.get(k) for k in ("events", "us_events", "special_categories", "player_props_by_league", "player_props_with_prices_inline", "error")})
