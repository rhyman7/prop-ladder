"""One-off: find Kalshi series that hold player props for NFL, college football,
NBA and college basketball, and save sample markets. Public API, no key.
Writes coverage/kalshi_discover.json."""
import json, os, time, urllib.parse, urllib.request
BASES = ["https://api.elections.kalshi.com/trade-api/v2", "https://external-api.kalshi.com/trade-api/v2"]
OUT = os.path.join(os.path.dirname(__file__), "..", "coverage", "kalshi_discover.json")


def get(path, params=None):
    err = None
    for base in BASES:
        url = f"{base}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            err = repr(e)
    return {"error": err}


out = {}
series = get("series", {"category": "Sports"})
allser = series.get("series") or []
out["series_count"] = len(allser)
out["series_error"] = series.get("error")
keys = ("NFL", "NBA", "NCAA", "COLLEGE", "CFB", "CBB", "FOOTBALL", "BASKETBALL")
words = ("YARD", "RECEPTION", "TOUCHDOWN", "TD", "POINT", "REBOUND", "ASSIST", "THREE", "3PT", "PTS", "REB", "AST", "PASS", "RUSH", "REC")
cand = []
for s in allser:
    t = (s.get("ticker", "") + " " + s.get("title", "")).upper()
    if any(k in t for k in keys):
        cand.append({"ticker": s.get("ticker"), "title": s.get("title"), "tags": s.get("tags"), "props_like": any(w in t for w in words)})
out["sports_series"] = cand
samples = {}
for s in [c for c in cand if c["props_like"]][:40]:
    m = get("markets", {"series_ticker": s["ticker"], "status": "open", "limit": 5})
    ms = m.get("markets") or []
    samples[s["ticker"]] = {"title": s["title"], "n_open_first_page": len(ms), "cursor": bool(m.get("cursor")),
                            "sample": [{k: x.get(k) for k in ("ticker", "event_ticker", "title", "subtitle", "yes_sub_title", "no_sub_title",
                                                              "floor_strike", "cap_strike", "strike_type", "custom_strike", "yes_bid", "yes_ask",
                                                              "no_bid", "no_ask", "yes_bid_dollars", "yes_ask_dollars", "last_price", "volume",
                                                              "open_interest", "close_time", "expected_expiration_time", "rules_primary")} for x in ms[:3]]}
    time.sleep(0.3)
out["samples"] = samples
json.dump(out, open(OUT, "w"), indent=1)
print(out["series_count"], "sports series;", len(cand), "football/basketball;", sum(c["props_like"] for c in cand), "prop-like")
