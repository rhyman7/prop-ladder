"""Build docs/data.json for the Prop Ladder pages.

1. Pull upcoming events from SportsGameOdds (SGO) for NFL, NCAAF, NBA, NCAAB,
   with alternate lines. One SGO object per event; caps per league below.
2. For each player over/under prop, find the TRUE probability at an anchor line:
   the line the most books quote on both sides, each book's vig removed, median.
3. Every rung: each book's vig (measured on its own two-sided line) is removed
   from each rung it posts, power method; true probability = median across the
   books posting that rung ("n" on each rung). The negative-binomial curve code
   below is kept for reference but not used: on Nov 24 it fit yardage badly.
4. Write the DK/FD price for every rung and side. The pages do the edge, EV and
   boost math in the browser.

Key: SGO_API_KEY. Writes docs/data.json and coverage/meta_sample.json.
"""
import json
import math
import os
import statistics as st
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://api.sportsgameodds.com/v2"
KEY = os.environ.get("SGO_API_KEY", "")
ROOT = os.path.join(os.path.dirname(__file__), "..")
SOURCE = "consensus"  # "pinnacle" once a paid key carries it

# (max events per run, days ahead). About 1 SGO object per event.
CAPS = {
    "NFL": (int(os.environ.get("CAP_NFL", 16)), 4),
    "NCAAF": (int(os.environ.get("CAP_NCAAF", 40)), 3),
    "NBA": (int(os.environ.get("CAP_NBA", 15)), 2),
    "NCAAB": (int(os.environ.get("CAP_NCAAB", 40)), 2),
}
SPORT_LABEL = {"NFL": "NFL", "NCAAF": "CFB", "NBA": "NBA", "NCAAB": "NCAAB"}
BOOKS = {"draftkings": "dk", "fanduel": "fd"}
# The consensus uses ONLY the 9 books the free plan returned (Nov 24, 2026), so
# upgrading the key (e.g. a Rookie trial with Pinnacle and 70+ more books) does
# not change this page's method. A Pinnacle version must be a separate build.
FREE_BOOKS = {"draftkings", "fanduel", "caesars", "betmgm", "bovada", "espnbet",
              "pointsbet", "unibet", "williamhill"}
# WIDE version (Rookie trial, from Nov 24, 2026): the 9 books plus sharper,
# lower-vig books and exchanges. Where 2+ SHARP books post a rung (and their
# median is within 15 points of the all-book median), its true probability =
# the sharp books' median; otherwise the median of all WIDE books. Pick'em apps (underdog, sleeper, prizepicks) excluded.
SHARP_BOOKS = {"bookmakereu", "betonline", "lowvig", "novig", "prophetexchange",
               "kalshi", "polymarket", "matchbook", "betfairexchange"}
WIDE_BOOKS = FREE_BOOKS | SHARP_BOOKS
# Exchanges / prediction markets post one-sided resting orders that can be
# stale or junk. Their price is used only at lines where they show BOTH sides
# and the two implied probabilities add to 0.98-1.15.
EXCHANGES = {"novig", "prophetexchange", "kalshi", "polymarket", "matchbook", "betfairexchange"}
TEAM_ENTITIES = {"home", "away", "all"}

# Assumed coefficient of variation (sd / mean) per stat. STARTING VALUES, NOT
# FITTED OR TESTED: rungs far from the anchor depend on them. None = Poisson.
CURVES = {
    # basketball
    "points": 0.30, "rebounds": 0.42, "assists": 0.48, "threePointersMade": None,
    "points+rebounds": 0.27, "points+assists": 0.27, "rebounds+assists": 0.36,
    "points+rebounds+assists": 0.24, "steals": None, "blocks": None, "blocks+steals": None,
    "turnovers": None,
    # football
    "passing_yards": 0.27, "rushing_yards": 0.50, "receiving_yards": 0.62,
    "rushing+receiving_yards": 0.45, "passing+rushing_yards": 0.26,
    "receiving_receptions": 0.45, "rushing_attempts": 0.33, "passing_attempts": 0.18,
    "passing_completions": 0.20, "passing_touchdowns": None, "passing_interceptions": None,
    "touchdowns": None, "defense_sacks": None, "defense_combinedTackles": 0.45,
    "defense_soloTackles": 0.50, "fieldGoals_made": None,
}
STAT_LABEL = {
    "points": "Points", "rebounds": "Rebounds", "assists": "Assists", "threePointersMade": "Threes made",
    "points+rebounds": "Points + Rebounds", "points+assists": "Points + Assists",
    "rebounds+assists": "Rebounds + Assists", "points+rebounds+assists": "Pts + Reb + Ast",
    "steals": "Steals", "blocks": "Blocks", "blocks+steals": "Blocks + Steals", "turnovers": "Turnovers",
    "passing_yards": "Passing yards", "rushing_yards": "Rushing yards", "receiving_yards": "Receiving yards",
    "rushing+receiving_yards": "Rush + Rec yards", "passing+rushing_yards": "Pass + Rush yards",
    "receiving_receptions": "Receptions", "rushing_attempts": "Rushing attempts",
    "passing_attempts": "Pass attempts", "passing_completions": "Completions",
    "passing_touchdowns": "Passing TDs", "passing_interceptions": "Interceptions thrown",
    "touchdowns": "Touchdowns", "defense_sacks": "Sacks", "defense_combinedTackles": "Tackles + assists",
    "defense_soloTackles": "Solo tackles", "fieldGoals_made": "Field goals made",
    "receiving_longestReception": "Longest reception", "rushing_longestRush": "Longest rush",
    "passing_longestCompletion": "Longest completion", "defense_interceptions": "Interceptions (defense)",
    "kicking_totalPoints": "Kicking points", "extraPoints_kicksMade": "Extra points made",
}


# ---------------------------------------------------------------- odds math
def imp(a):
    a = float(a)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def american(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    v = -100 * p / (1 - p) if p >= 0.5 else 100 * (1 - p) / p
    return round(v)


def pmf_list(mean, cv, kmax):
    """P(X=k), k=0..kmax, for a negative binomial with this mean and CV
    (Poisson when cv is None or the CV is below the Poisson floor)."""
    if cv is None or cv * cv <= 1.0 / mean + 1e-9:
        out, p = [], math.exp(-mean)
        for k in range(kmax + 1):
            out.append(p)
            p *= mean / (k + 1)
        return out
    r = 1.0 / (cv * cv - 1.0 / mean)
    q = r / (r + mean)
    out = [math.exp(r * math.log(q))]
    for k in range(1, kmax + 1):
        out.append(out[-1] * (k - 1 + r) / k * (1 - q))
    return out


def tail_over(pm, line):
    """P(X > line), P(X == line)."""
    k0 = math.floor(line) + 1
    over = 1.0 - sum(pm[:k0])
    push = pm[int(line)] if float(line).is_integer() and int(line) < len(pm) else 0.0
    return max(over, 0.0), push


def fit_mean(anchor_line, p_over, cv, iters=70):
    """Mean whose curve gives P(X > anchor_line) = p_over (bisection)."""
    lo, hi = 1e-3, max(5.0, anchor_line * 4 + 10)
    for _ in range(iters):
        m = (lo + hi) / 2
        pm = pmf_list(m, cv, int(m * 4 + 40 + anchor_line))
        if tail_over(pm, anchor_line)[0] < p_over:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


# ---------------------------------------------------------------- SGO
def get(path, params):
    url = f"{BASE}/{path}/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-Api-Key": KEY})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(12)
                continue
            return {"success": False, "error": f"HTTP {e.code}: {e.read()[:300]!r}"}
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            return {"success": False, "error": repr(e)}


def pull(league, cap, days, now):
    iso = lambda d: d.isoformat(timespec="seconds").replace("+00:00", "Z")
    events, cursor = [], None
    while len(events) < cap:
        p = {"leagueID": league, "oddsAvailable": "true", "includeAltLines": "true",
             "startsAfter": iso(now), "startsBefore": iso(now + timedelta(days=days)),
             "limit": min(10, cap - len(events))}
        if cursor:
            p["cursor"] = cursor
        r = get("events", p)
        time.sleep(7)  # free plan: 10 requests a minute
        if "data" not in r:
            print(f"{league}: {r.get('error')}", file=sys.stderr)
            break
        events += r["data"]
        cursor = r.get("nextCursor")
        if not cursor or not r["data"]:
            break
    return events


def quotes(q):
    """{line: odds} for a byBookmaker entry, main line + alts, open only."""
    out = {}
    if q.get("overUnder") is not None and q.get("odds") and q.get("available"):
        out[float(q["overUnder"])] = int(float(q["odds"]))
    for a in q.get("altLines") or []:
        if a.get("overUnder") is not None and a.get("odds") and a.get("available"):
            out.setdefault(float(a["overUnder"]), int(float(a["odds"])))
    return out


def monotone(q, side):
    """Drop quotes that break the book's own ladder order: P(over) must fall as
    the line rises (P(under) must rise), within 2 points. Guards against stale or
    junk exchange quotes (Nov 24: Novig LaMelo Ball PRA 44.5 +900 but 49.5 -223)."""
    keep, last = {}, None
    for ln in sorted(q):
        p = imp(q[ln])
        if last is not None and ((side == "o" and p > last + 0.02) or (side == "u" and p < last - 0.02)):
            continue
        keep[ln] = q[ln]
        last = p
    return keep


def team_info(t):
    n = t.get("names") or {}
    return {"id": t.get("teamID"), "name": n.get("long") or n.get("medium") or t.get("teamID"),
            "abbr": n.get("short") or n.get("medium") or (t.get("teamID") or "")[:3]}


def anchor(o, oq_all, uq_all):
    """(line, p_over, n_books, how): the line the most books quote on BOTH sides
    (ties: the one nearest 50%), each book's simple vig removal, median.
    SGO's own fairOdds is not used: when books' main lines differ it can be far
    off (e.g. 33.6% at 275.5 pass yds with DK at 50% on 270.5)."""
    lines = {}
    for b in oq_all:
        for ln in oq_all[b]:
            if ln in uq_all.get(b, {}):
                po, pu = imp(oq_all[b][ln]), imp(uq_all[b][ln])
                lines.setdefault(ln, []).append(po / (po + pu))
    if not lines:
        return None
    ln, ps = max(lines.items(), key=lambda kv: (len(kv[1]), -abs(st.median(kv[1]) - 0.5)))
    return ln, st.median(ps), len(ps), "consensus" if len(ps) >= 2 else "one book"


def two_sided_points(o, u):
    """(anchor_line, p_anchor, [(line, consensus p_over)]) at non-anchor lines
    where 2+ books quote both sides; used to fit each stat's spread."""
    oq_all = {b: quotes(q) for b, q in (o.get("byBookmaker") or {}).items()}
    uq_all = {b: quotes(q) for b, q in (u.get("byBookmaker") or {}).items()}
    a = anchor(o, oq_all, uq_all)
    if not a or not (0.02 < a[1] < 0.98):
        return None
    pts = {}
    for b in oq_all:
        for ln, oo in oq_all[b].items():
            if ln != a[0] and ln in uq_all.get(b, {}):
                po, pu = imp(oo), imp(uq_all[b][ln])
                pts.setdefault(ln, []).append(po / (po + pu))
    pts = [(ln, st.median(v)) for ln, v in pts.items() if len(v) >= 2 and not float(ln).is_integer()]
    return (a[0], a[1], pts) if pts else None


def fit_cv(samples, default):
    """Pick the CV (or Poisson) that best matches the two-sided consensus rungs."""
    grid = [None] + [round(0.12 + 0.03 * i, 2) for i in range(40)]
    best, best_err = default, None
    for cv in grid:
        err = 0.0
        for aline, ap, pts in samples:
            m = fit_mean(aline, ap, cv, iters=40)
            pm = pmf_list(m, cv, int(m * 5 + 60 + max(l for l, _ in pts) * 1.5))
            for ln, p in pts:
                err += (tail_over(pm, ln)[0] - p) ** 2
        if best_err is None or err < best_err:
            best, best_err = cv, err
    n = sum(len(s[2]) for s in samples)
    return best, round(math.sqrt(best_err / n) * 100, 2) if n else None


def power_k(po, pu):
    """Exponent k with po**k + pu**k = 1 (power vig removal)."""
    lo, hi = 0.5, 5.0
    for _ in range(60):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1:
            lo = k
        else:
            hi = k
    return (lo + hi) / 2


def build_prop(o, u, books=None, sharp=None):
    """Market ladder: each book's vig, measured on its own two-sided line(s), is
    removed from every rung it posts (power method); a rung's true probability
    is the median across the books posting it."""
    ob, ub = o.get("byBookmaker") or {}, u.get("byBookmaker") or {}
    books = books or FREE_BOOKS
    oq_all = {b: monotone(quotes(q), "o") for b, q in ob.items() if b in books}
    uq_all = {b: monotone(quotes(q), "u") for b, q in ub.items() if b in books}
    for b in EXCHANGES & set(oq_all) | EXCHANGES & set(uq_all):
        oq, uq = oq_all.get(b, {}), uq_all.get(b, {})
        ok = {ln for ln in oq if ln in uq and 0.98 <= imp(oq[ln]) + imp(uq[ln]) <= 1.15}
        oq_all[b] = {ln: v for ln, v in oq.items() if ln in ok}
        uq_all[b] = {ln: v for ln, v in uq.items() if ln in ok}
    if not any(oq_all.get(b) or uq_all.get(b) for b in BOOKS):
        return None
    a = anchor(o, oq_all, uq_all)
    if not a:
        return None
    aline, ap, an, how = a
    # each book's vig exponent from its two-sided line nearest 50%
    ks = {}
    for b in set(oq_all) | set(uq_all):
        two = [(ln, imp(oq_all[b][ln]), imp(uq_all[b][ln])) for ln in oq_all.get(b, {}) if ln in uq_all.get(b, {})]
        if two:
            ln, po, pu = min(two, key=lambda t: abs(t[1] / (t[1] + t[2]) - 0.5))
            if po + pu > 1:
                ks[b] = power_k(po, pu)
    if not ks:
        return None
    k_default = st.median(ks.values())
    fair = {}   # line -> [fair p_over from each book]
    for b in set(oq_all) | set(uq_all):
        k = ks.get(b, k_default)
        for ln, odds in oq_all.get(b, {}).items():
            fair.setdefault(ln, {}).setdefault(b, []).append(imp(odds) ** k)
        for ln, odds in uq_all.get(b, {}).items():
            fair.setdefault(ln, {}).setdefault(b, []).append(1 - imp(odds) ** k)
    rungs = []
    for ln in sorted(fair):
        per_book = {b: st.mean(v) for b, v in fair[ln].items()}
        sharp_p = [v for b, v in per_book.items() if sharp and b in sharp]
        all_med = st.median(per_book.values())
        po = all_med
        # sharp-first only when 2+ sharp books post the rung and they are within
        # 15 points of the all-book median (else one bad quote can set it)
        if len(sharp_p) >= 2 and abs(st.median(sharp_p) - all_med) <= 0.15:
            po = st.median(sharp_p)
        po = min(max(po, 0.001), 0.999)
        r = {"l": ln, "po": round(po, 4), "pu": round(1 - po, 4), "n": len(per_book), "a": ln == aline}
        if sharp:
            r["ns"] = len(sharp_p)
            r["sf"] = int(po != min(max(all_med, 0.001), 0.999))
        for b, key in BOOKS.items():
            if ln in oq_all.get(b, {}):
                r[key + "o"] = oq_all[b][ln]
            if ln in uq_all.get(b, {}):
                r[key + "u"] = uq_all[b][ln]
        if any(x in r for x in ("dko", "dku", "fdo", "fdu")):
            rungs.append(r)
    if not rungs:
        return None
    stat = o.get("statID")
    return {"stat": stat, "statLabel": STAT_LABEL.get(stat, stat.replace("_", " ").replace("+", " + ")),
            "anchor": {"l": aline, "p": round(ap, 4), "fair": american(ap), "n": an},
            "books": len(ks), "rungs": rungs}


def main():
    if not KEY:
        sys.exit("SGO_API_KEY is not set")
    now = datetime.now(timezone.utc)
    out = {"pulledAt": now.isoformat(timespec="seconds"), "source": SOURCE, "games": [], "props": [],
           "method": "market-ladder", "books": sorted(FREE_BOOKS)}
    meta_sample = None
    used = 0
    raw = []
    for lg, (cap, days) in CAPS.items():
        events = pull(lg, cap, days, now)
        used += len(events)
        for ev in events:
            teams = ev.get("teams") or {}
            home, away = team_info(teams.get("home") or {}), team_info(teams.get("away") or {})
            gid = ev.get("eventID")
            start = (ev.get("status") or {}).get("startsAt")
            out["games"].append({"id": gid, "sport": SPORT_LABEL[lg], "start": start, "home": home, "away": away})
            players = ev.get("players") or {}
            if meta_sample is None:
                meta_sample = {"teams": teams, "status": ev.get("status"),
                               "players_first3": dict(list(players.items())[:3])}
            odds = ev.get("odds") or {}
            for oid, o in odds.items():
                if o.get("betTypeID") != "ou" or o.get("sideID") != "over" or o.get("periodID") != "game":
                    continue
                pid = o.get("playerID")
                if not pid or (o.get("statEntityID") or "") in TEAM_ENTITIES:
                    continue
                u = odds.get(o.get("opposingOddID") or "") or {}
                raw.append((lg, ev, home, away, gid, start, players, o, u))

    wide = {"pulledAt": out["pulledAt"], "source": "wide", "games": out["games"], "props": [],
            "method": "market-ladder, sharp books first", "books": sorted(WIDE_BOOKS), "sharp": sorted(SHARP_BOOKS)}
    for lg, ev, home, away, gid, start, players, o, u in raw:
        pid = o.get("playerID")
        for target, kw in ((out, {}), (wide, {"books": WIDE_BOOKS, "sharp": SHARP_BOOKS})):
            prop = build_prop(o, u, **kw)
            if not prop:
                continue
            pl = players.get(pid) or {}
            tid = pl.get("teamID")
            team = home if tid == home["id"] else away if tid == away["id"] else {"id": tid, "name": tid, "abbr": tid}
            opp = away if team is home else home if team is away else None
            prop.update({"sport": SPORT_LABEL[lg], "game": gid, "start": start,
                         "player": pl.get("name") or (pl.get("firstName", "") + " " + pl.get("lastName", "")).strip() or pid,
                         "pid": pid, "team": team.get("abbr"), "teamName": team.get("name"),
                         "opp": opp.get("abbr") if opp else None})
            target["props"].append(prop)
    out["objectsUsed"] = used
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "data.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    if os.environ.get("BUILD_WIDE", "1") == "1":
        wide["objectsUsed"] = used
        os.makedirs(os.path.join(ROOT, "docs", "wide"), exist_ok=True)
        with open(os.path.join(ROOT, "docs", "wide", "data.json"), "w") as f:
            json.dump(wide, f, separators=(",", ":"))
        print(f"wide: {len(wide['props'])} props, "
              f"{sum(1 for p in wide['props'] for r in p['rungs'] if r.get('ns'))} rungs priced by sharp books")
    os.makedirs(os.path.join(ROOT, "coverage"), exist_ok=True)
    with open(os.path.join(ROOT, "coverage", "meta_sample.json"), "w") as f:
        json.dump(meta_sample, f, indent=1)
    print(f"{len(out['games'])} games, {len(out['props'])} props, "
          f"{sum(len(p['rungs']) for p in out['props'])} rungs, {used} SGO objects")


if __name__ == "__main__":
    main()
