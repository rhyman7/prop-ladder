"""Sweet-spot report: every upcoming logged play that fits one Results-page
selection, as Markdown on stdout. Read-only: reads data/plays_log.json (the
9-book log) and changes nothing. Run by Ryan's hourly Claude scheduled task
"Prop Ladder sweet-spot report", which sends the output to his phone.

The selection (Ryan, Nov 27, 2026), judged like the Results page does, on the
play when it was FIRST flagged: edge 3-5%, price -100 to -499, any sport,
book, side and number of books. Change it here and in the task's wording.

    python scripts/report.py [--new-min 60]
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
import track  # noqa: E402

EDGE_LO, EDGE_HI = 0.03, 0.05          # first_edge, lo <= e < hi (the "3-5%" button)
PRICE_LO, PRICE_HI = -500, -100        # first_odds, lo < a <= hi (-300 to -499 and -100 to -299)
ET = ZoneInfo("America/New_York")
BOOK = {"dk": "DraftKings", "fd": "FanDuel", "ka": "Kalshi"}


def fits(r):
    return EDGE_LO <= r["first_edge"] < EDGE_HI and PRICE_LO < r["first_odds"] <= PRICE_HI


def odds(a):
    return "—" if a is None else ("+" if a > 0 else "−") + str(abs(a))


def pct(x, signed=False):
    s = f"{abs(x) * 100:.1f}%"
    return (("+" if x > 0 else "−" if x < 0 else "") + s) if signed else s


def when(ts, fmt="%a %-I:%M %p"):
    return track.parse(ts).astimezone(ET).strftime(fmt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-min", type=int, default=60, help="a play first flagged within this many minutes is NEW")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    log = track.load("data/plays_log.json", {})
    data = track.load("docs/data.json", {})
    rows = [r for r in log.values() if fits(r)]
    up = sorted((r for r in rows if r["status"] == "pending" and track.parse(r["start"]) > now),
                key=lambda r: (r["start"], r["sport"], r["player"], r["statLabel"], r["line"], r["book"]))
    cut = now - timedelta(minutes=a.new_min)
    new = [r for r in up if track.parse(r["first_seen"]) > cut]
    done = track.summarize([r for r in rows if r["status"] == "graded"])

    pulled = data.get("pulledAt")
    out = [f"**Prop Ladder sweet spot: {len(up)} upcoming plays, {len(new)} new**", ""]
    out.append(f"Board rebuilt {when(pulled, '%b %-d, %-I:%M %p') + ' ET' if pulled else 'unknown'} · 9-book version · "
               f"edge 3–5% and price −100 to −499 when first flagged · all sports, books and sides")
    if done:
        se = f" ± {done['roiSE'] * 100:.1f}%" if done["roiSE"] is not None else ""
        out.append(f"This selection so far: {done['w']}-{done['l']}{'-' + str(done['p']) if done['p'] else ''}, "
                   f"{'+' if done['profit'] >= 0 else '−'}${abs(done['profit']):.2f} at $10 a play, ROI {pct(done['roi'], True)}{se} ({done['n']} graded)")
    out.append("")

    def table(plays, title):
        out.append(f"### {title} ({len(plays)})")
        if not plays:
            out.extend(["None.", ""])
            return
        out.append("| Kickoff (ET) | Sport | Player | Bet | Book | First price | True prob | Edge | Books | Price now | Edge now | First flagged |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in plays:
            bet = f"{'Over' if r['side'] == 'o' else 'Under'} {r['line']} {r['statLabel'].lower()}"
            edge_now = r["last_true"] - track.imp(r["last_odds"]) if r.get("last_odds") is not None else None
            out.append(f"| {when(r['start'])} | {r['sport']} | {r['player']} ({r.get('team') or ''}) | {bet} | {BOOK[r['book']]} | "
                       f"{odds(r['first_odds'])} | {pct(r['first_true'])} | {pct(r['first_edge'], True)} | {r['first_books']} | "
                       f"{odds(r.get('last_odds'))} | {pct(edge_now, True) if edge_now is not None else '—'} | {when(r['first_seen'], '%a %-I:%M %p')} |")
        out.append("")

    table(new, f"New in the last {a.new_min} minutes")
    table(up, "Every upcoming play that fits")
    out.append("Price now and Edge now are from the latest refresh before this report; a negative Edge now means the price or the market has moved "
               "and the play no longer clears. No boost applied. Kalshi: if the player doesn't play, Overs lose.")
    print("\n".join(out))


if __name__ == "__main__":
    main()
