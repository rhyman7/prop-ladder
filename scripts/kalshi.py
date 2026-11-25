"""Add Kalshi prices to docs/data.json and docs/wide/data.json.

Kalshi's public market data (no key, no account) has per-game player-prop
ladders for the NFL and NBA (no college player props, Nov 2026). Each market is
"<Player>: <N>+ <stat>" with floor_strike = N - 0.5. Buying YES = the Over at
that line; buying NO = the Under.

Price used: the ask (what you pay now as a taker) plus Kalshi's taker fee,
0.07 x P x (1 - P) per $1 contract, turned into American odds so the pages can
price it like a sportsbook. Stored on each matching rung as
  kao / kau  : American odds after the fee (Over / Under)
  kpo / kpu  : the ask in cents before the fee
Only exact line matches with our ladder are used. Quotes with no real offer
(ask >= 99c or <= 1c) are skipped.

Settlement differs from sportsbooks: on these (non-"Protected") markets a player
who does not play resolves NO, so an Over loses and an Under wins. track.py
grades Kalshi plays that way.
"""
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
BASES = ["https://api.elections.kalshi.com/trade-api/v2", "https://external-api.kalshi.com/trade-api/v2"]
TAKER_FEE = 0.07
SERIES = {  # Kalshi series -> (our sport, SGO statID)
    "KXNFLPASSYDS": ("NFL", "passing_yards"), "KXNFLPASSYDSPRECISE": ("NFL", "passing_yards"),
    "KXNFLRSHYDS": ("NFL", "rushing_yards"), "KXNFLRSHYDSPRECISE": ("NFL", "rushing_yards"),
    "KXNFLRECYDS": ("NFL", "receiving_yards"), "KXNFLRECYDSPRECISE": ("NFL", "receiving_yards"),
    "KXNFLREC": ("NFL", "receiving_receptions"), "KXNFLPASSTDS": ("NFL", "passing_touchdowns"),
    "KXNFLPASSCOMP": ("NFL", "passing_completions"), "KXNFLPASSATT": ("NFL", "passing_attempts"),
    "KXNFLRSHATT": ("NFL", "rushing_attempts"), "KXNFLPASSINT": ("NFL", "passing_interceptions"),
    "KXNFLRRYDS": ("NFL", "rushing+receiving_yards"), "KXNFLLONGREC": ("NFL", "receiving_longestReception"),
    "KXNFLLONGRSH": ("NFL", "rushing_longestRush"), "KXNFLANYTD": ("NFL", "touchdowns"),
    "KXNBAPTS": ("NBA", "points"), "KXNBAREB": ("NBA", "rebounds"), "KXNBAAST": ("NBA", "assists"),
    "KXNBA3PT": ("NBA", "threePointersMade"), "KXNBAPRA": ("NBA", "points+rebounds+assists"),
    "KXNBAPR": ("NBA", "points+rebounds"), "KXNBAPA": ("NBA", "points+assists"),
    "KXNBARA": ("NBA", "rebounds+assists"), "KXNBASTL": ("NBA", "steals"),
    "KXNBASTOCK": ("NBA", "blocks+steals"), "KXNBASTOCKS": ("NBA", "blocks+steals"),
}
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
ET = timezone(timedelta(hours=-5))


def get(path, params):
    err = None
    for base in BASES:
        url = f"{base}/{path}?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            err = repr(e)
    return {"error": err}


def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", "", s.replace("-", " "))
    words = [w for w in s.split() if w not in ("jr", "sr", "ii", "iii", "iv", "v")]
    return "".join(words)


def american(cost):
    """American odds for paying `cost` (0-1) to win $1."""
    if cost >= 0.5:
        return -round(100 * cost / (1 - cost))
    return round(100 * (1 - cost) / cost)


def after_fee(p):
    return p + TAKER_FEE * p * (1 - p)


def dollars(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch():
    """{(sport, stat, playername, YYYY-MM-DD, line): (yes_ask, no_ask)}"""
    out, n = {}, 0
    for series, (sport, stat) in SERIES.items():
        cursor = None
        for _ in range(20):
            params = {"series_ticker": series, "status": "open", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            r = get("markets", params)
            time.sleep(0.25)
            ms = r.get("markets") or []
            for m in ms:
                title, line = m.get("title") or "", m.get("floor_strike")
                if ":" not in title or line is None or m.get("strike_type") != "greater":
                    continue
                mt = re.match(r"\d\d([A-Z]{3})(\d\d)", (m.get("event_ticker") or "").split("-")[1] if "-" in (m.get("event_ticker") or "") else "")
                yy = re.match(r"(\d\d)", (m.get("event_ticker") or "").split("-")[1]) if "-" in (m.get("event_ticker") or "") else None
                if not mt or not yy or mt.group(1) not in MONTHS:
                    continue
                day = f"20{yy.group(1)}-{MONTHS[mt.group(1)]:02d}-{int(mt.group(2)):02d}"
                ya = dollars(m.get("yes_ask_dollars"))
                na = dollars(m.get("no_ask_dollars"))
                if na is None:
                    yb = dollars(m.get("yes_bid_dollars"))
                    na = 1 - yb if yb else None
                out[(sport, stat, norm(title.split(":")[0]), day, float(line))] = (ya, na)
                n += 1
            cursor = r.get("cursor")
            if not cursor or not ms:
                break
    return out, n


def attach(path, quotes):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return 0
    with open(full) as f:
        data = json.load(f)
    hits = 0
    for p in data["props"]:
        if p["sport"] not in ("NFL", "NBA") or not p.get("start"):
            continue
        day = datetime.fromisoformat(p["start"].replace("Z", "+00:00")).astimezone(ET).date().isoformat()
        key0 = (p["sport"], p["stat"], norm(p["player"]), day)
        for r in p["rungs"]:
            for k in ("kao", "kau", "kpo", "kpu"):
                r.pop(k, None)
            q = quotes.get(key0 + (float(r["l"]),))
            if not q:
                continue
            ya, na = q
            if ya and 0.01 < ya < 0.99:
                r["kao"], r["kpo"] = american(after_fee(ya)), round(ya * 100)
            if na and 0.01 < na < 0.99:
                r["kau"], r["kpu"] = american(after_fee(na)), round(na * 100)
            hits += ("kao" in r) + ("kau" in r)
    data["kalshiAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(full, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    return hits


def main():
    quotes, n = fetch()
    print(f"kalshi: {n} open player-prop markets")
    for path in ("docs/data.json", "docs/wide/data.json"):
        print(f"kalshi: {path}: {attach(path, quotes)} prices matched to ladder rungs")


if __name__ == "__main__":
    main()
