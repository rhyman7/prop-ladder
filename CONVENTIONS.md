# Conventions — prop-ladder

Standalone site, rhyman7.github.io/prop-ladder (GitHub Pages from `docs/`):

- `index.html` — Prop Ladder: Sport → Team → Player → Stat, the true probability
  of every rung against DraftKings and FanDuel, with a profit-boost selector.
- `plays.html` — All +EV plays: every rung and side where the true probability
  beats the book's implied probability, best edge first.

## Data

- **Source:** SportsGameOdds (SGO), key in the `SGO_API_KEY` repository secret.
  Never put the key in the page, a committed file or a log.
- **Independent of fb-value-board.** No Odds API credits; nothing here changes
  the value boards.
- **Refresh:** `.github/workflows/refresh.yml` runs `scripts/build.py`, which
  writes `docs/data.json`. Manual only until Ryan picks a schedule. Caps per run
  (events): NFL 16, NCAAF 25, NBA 15, NCAAB 20 — at most ~76 SGO objects.
- **Allowance:** free plan, 2,500 objects a month. Ask Ryan before anything that
  would use most of it (a daily schedule does: ~2,300).

## How the true probability is made

1. **Anchor:** SGO's `fairOdds` at `fairOverUnder` — the free plan's books with
   the vig removed, median across books (matches our own simple vig removal to
   ~0.3 points; `coverage/fairodds_report.md`). No `fairOdds`: our own median
   simple vig removal over books quoting both sides at one line.
   `SOURCE = "consensus"`; switch to Pinnacle's no-vig line if a paid key ever
   carries it.
2. **Curve:** a negative binomial (or Poisson) per stat, mean set so it matches
   the anchor exactly. Each stat's spread (coefficient of variation) is fitted
   each run to that day's two-sided rungs (2+ books quoting both sides, vig
   removed); with fewer than 15 such rungs it falls back to the assumed value in
   `CURVES`. Stats with no curve show only the anchor line.
3. **Pricing (browser):** implied = 10 / (10 + profit after boost); edge =
   true − implied; EV per $10 counts pushes as neither win nor loss.

Rungs away from the anchor are **untested estimates** and the pages say so. Any
change to the method follows the project's pre-set test rule once there is a
logged history to test on (nothing logged yet).

## Other

- Ryan bets only DraftKings and FanDuel, $10 units, with profit boosts.
- Coverage and fairOdds checks: `scripts/coverage_test.py`,
  `scripts/fairodds_check.py` (manual Actions, reports in `coverage/`).
- Mockup: Prop Ladder design canvas on claude.ai (Nov 24, 2026).
