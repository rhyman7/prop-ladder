"""Build docs/pinnacle/data.json: the Pinnacle version of the Prop Ladder.

Source: PinnOdds (Pinnacle prices; unofficial, "not affiliated with Pinnacle"),
key PINNODDS_API_KEY. One call per sport (Football 5, Basketball 3) with
include_specials=nested returns every game's player props with prices: 2
requests a run.

Method, per prop that Pinnacle prices:
  1. Pinnacle posts ONE line, both sides. Remove its vig (power method) ->
     Pinnacle's true P(over) at that line.
  2. Take the 9-book market ladder for the same prop (docs/data.json), read its
     P(over) at Pinnacle's line (interpolated in log-odds between rungs if
     needed), and shift EVERY rung by the same log-odds amount so the ladder
     matches Pinnacle exactly at Pinnacle's line.
Props Pinnacle doesn't price keep the 9-book numbers and are flagged (pin=null).
Kalshi and DK/FD prices are carried over unchanged.
"""
import copy
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from kalshi import norm  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
KEY = os.environ.get("PINNODDS_API_KEY", "")
BASE = "https://pinnodds.com/kit/v1"
ET = timezone(timedelta(hours=-5))
STAT = {  # Pinnacle "Total ..." -> SGO statID
    "Receptions": "receiving_receptions", "Receiving Yards": "receiving_yards",
    "Rushing Yards": "rushing_yards", "Rush Attempts": "rushing_attempts",
    "Pass Completions": "passing_completions", "Passing Yards": "passing_yards",
    "Pass Attempts": "passing_attempts", "Touchdown Passes": "passing_touchdowns",
    "Interceptions": "passing_interceptions", "Touchdowns": "touchdowns",
    "Points": "points", "Threes Made": "threePointersMade", "Rebounds": "rebounds",
    "Assists": "assists", "Pts & Rebs & Asts": "points+rebounds+assists",
    "Pts & Rebs": "points+rebounds", "Pts & Asts": "points+assists", "Rebs & Asts": "rebounds+assists",
}
SPORT = {"NFL": "NFL", "NBA": "NBA"}   # NCAA football/basketball: too few Pinnacle props (Nov 2026)


def get(path, params):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-portal-apikey": KEY, "Accept": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            err = repr(e)
            time.sleep(5)
    return {"error": err}


def power_fair(dec_over, dec_under):
    po, pu = 1 / dec_over, 1 / dec_under
    lo, hi = 0.5, 5.0
    for _ in range(60):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1:
            lo = k
        else:
            hi = k
    return po ** ((lo + hi) / 2)


def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def sig(x):
    return 1 / (1 + math.exp(-x))


def american(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def fetch():
    """{(sport, stat, name, ET date): (line, p_over_fair, max_risk)}"""
    quotes, info = {}, {}
    for sid in (5, 3):
        r = get("prematch/fixtures", {"sport_id": sid, "include_specials": "nested"})
        time.sleep(3)
        if "error" in r:
            info[sid] = r["error"]
            continue
        n = 0
        for e in r.get("events") or []:
            sport = SPORT.get(e.get("league_name"))
            if not sport:
                continue
            for sp in e.get("specials") or []:
                if sp.get("special_category") != "Player Props":
                    continue
                name, _, stat = (sp.get("special") or "").partition(" Total ")
                stat = STAT.get(stat.strip())
                mk = ((sp.get("special_markets") or {}).get("num_0") or [])
                if not stat or not mk:
                    continue
                prices = {x.get("name"): x for x in mk[0].get("prices") or []}
                o, u = prices.get("Over"), prices.get("Under")
                if not o or not u or o.get("points") != u.get("points") or not o.get("price") or not u.get("price"):
                    continue
                start = sp.get("starts") or e.get("starts")
                day = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(ET).date().isoformat() if start else None
                quotes[(sport, stat, norm(name), day)] = (float(o["points"]), power_fair(float(o["price"]), float(u["price"])), mk[0].get("max_risk"))
                n += 1
        info[sid] = n
    return quotes, info


def at_line(rungs, line):
    """Market P(over) at `line`, log-odds interpolated between rungs."""
    rs = sorted(rungs, key=lambda r: r["l"])
    for r in rs:
        if r["l"] == line:
            return r["po"]
    lo = [r for r in rs if r["l"] < line]
    hi = [r for r in rs if r["l"] > line]
    if lo and hi:
        a, b = lo[-1], hi[0]
        t = (line - a["l"]) / (b["l"] - a["l"])
        return sig(logit(a["po"]) + t * (logit(b["po"]) - logit(a["po"])))
    if not lo and not hi:
        return None
    near = (hi or lo)[0] if not lo else lo[-1]
    if abs(near["l"] - line) > 3:   # too far outside the ladder to extrapolate
        return None
    return near["po"]


def main():
    if not KEY:
        sys.exit("PINNODDS_API_KEY is not set")
    with open(os.path.join(ROOT, "docs", "data.json")) as f:
        base = json.load(f)
    quotes, info = fetch()
    out = copy.deepcopy(base)
    out["source"] = "pinnacle"
    out["method"] = "Pinnacle no-vig line; market ladder shifted to match it (9-book fallback where Pinnacle has no prop)"
    out["pinnacleAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    hits = 0
    for p in out["props"]:
        p["pin"] = None
        if p["sport"] not in ("NFL", "NBA") or not p.get("start"):
            continue
        day = datetime.fromisoformat(p["start"].replace("Z", "+00:00")).astimezone(ET).date().isoformat()
        q = quotes.get((p["sport"], p["stat"], norm(p["player"]), day))
        if not q:
            continue
        line, ppin, risk = q
        pm = at_line(p["rungs"], line)
        if pm is None:
            continue
        shift = logit(ppin) - logit(pm)
        for r in p["rungs"]:
            po = sig(logit(r["po"]) + shift)
            r["po"], r["pu"] = round(po, 4), round(1 - po, 4)
            r.pop("pp", None)
        p["pin"] = {"l": line, "p": round(ppin, 4), "fair": american(ppin), "risk": risk, "shift": round(shift, 3)}
        p["anchor"] = {"l": line, "p": round(ppin, 4), "fair": american(ppin), "n": 9}
        hits += 1
    os.makedirs(os.path.join(ROOT, "docs", "pinnacle"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "pinnacle", "data.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"pinnacle: fetched {info}; {len(quotes)} Pinnacle props; anchored {hits} of {len(out['props'])} props")


if __name__ == "__main__":
    main()
