# Conventions — prop-ladder

Standalone site, rhyman7.github.io/prop-ladder (GitHub Pages from `docs/`):

- `index.html` — Prop Ladder: Sport → Team → Player → Stat, the true probability
  of every rung against DraftKings and FanDuel, with a profit-boost selector.
- `plays.html` — All +EV plays: every rung and side where the true probability
  beats the book's implied probability, best edge first.
- `results.html` — Results: how the logged All +EV plays did. Separate page:
  Ryan does NOT want the Prop Ladder pages to link to it (no nav link either way).

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

1. **Anchor:** the line the most books quote on both sides (ties: nearest 50%);
   each book's simple vig removal, median. A one-book anchor is flagged on the
   pages. SGO's own `fairOdds` is NOT used: where books' main lines differ it can
   be far off (Nov 24: 33.6% at 275.5 pass yds with DK at 50% on 270.5).
   `SOURCE = "consensus"`; switch to Pinnacle's no-vig line if a paid key ever
   carries it.
2. **Every rung (market ladder):** each book's vig is measured on its own
   two-sided line nearest 50% (power method exponent k); every rung that book
   posts is de-vigged with its k (books with no two-sided line use the median
   k); a rung's true probability = median across the books posting it (`n`).
   The negative-binomial curve in `build.py` is not used: on Nov 24 it fit
   yardage badly (implied negative vig).
3. **Pricing (browser):** implied = 10 / (10 + profit after boost); edge =
   true − implied; EV per $10 counts pushes as neither win nor loss.

The true probabilities are **untested** and the pages say so. Any
change to the method follows the project's pre-set test rule once there is a
logged history to test on (nothing logged yet).

## Results tracking

- `scripts/track.py` runs after `build.py` in the refresh. It logs every rung +
  side + book (DK/FD) with edge > 0 and 2+ books, for games not yet started, at
  its first sighting (`first_*`), and updates `last_*` (price and market true
  probability) on every later refresh before kickoff.
- Grading: SGO `score` on the prop's over odd once the game is final; null score
  = void (did not play). $10 flat at the first price, no boost. About 1 SGO
  object per finished game, at most 40 a run.
- Log `data/plays_log.json` (never edited by hand); summary `docs/results.json`
  for `results.html`: record, profit, ROI ± 1 SE, actual vs expected win rate,
  CLV (last true prob − first price's implied), by edge, books, sport, book,
  side and price.

## Other

- Ryan bets only DraftKings and FanDuel, $10 units, with profit boosts.
- Coverage and fairOdds checks: `scripts/coverage_test.py`,
  `scripts/fairodds_check.py` (manual Actions, reports in `coverage/`).
- Mockup: Prop Ladder design canvas on claude.ai (Nov 24, 2026).
