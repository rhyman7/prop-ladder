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
  writes `docs/data.json` (and `docs/wide/data.json`), then `scripts/track.py`.
  Hourly and self-chaining (GitHub's cron proved unreliable, Nov 25): each run
  waits ~50 min and dispatches the next; repo variable `REFRESH_CHAIN=off`
  stops it; a 3-hourly cron revives it. FULL run (NFL 7 days, NCAAF 5 days,
  NBA/NCAAB 2 days; caps 20/90/30/80) every 6 hours; NEAR runs in between pull
  only the next 30 hours and keep farther games from the last full run (each
  game and prop carries `asOf`, its own pull time). Free-plan settings are in
  the workflow header.
- **Allowance:** free plan, 2,500 objects a month. Ask Ryan before anything that
  would use most of it (a daily schedule does: ~2,300).

## How the true probability is made

**Locked to the free plan's 9 books** (`FREE_BOOKS` in `build.py`: DraftKings,
FanDuel, Caesars, BetMGM, Bovada, ESPN BET, PointsBet, Unibet, William Hill),
whatever plan the key is on. A Pinnacle / paid-plan version must be a separate
build with its own pages and its own play log, so the two stay comparable.

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

## Wide version (Rookie trial, Nov 24 - Dec 1, 2026)

- Pinnacle is NOT on Rookie (Pro only, $299/mo; checked Nov 24). The trial
  instead tests a wider, sharper consensus: `docs/wide/` (index, plays), built
  from the same pull by `build.py`: the 9 books + SHARP_BOOKS (BookMaker,
  BetOnline, LowVig, Novig, Prophet Exchange, Kalshi, Polymarket, Matchbook,
  Betfair Exchange). Where 2+ sharp books post a rung and their median is within
  15 points of the all-book median, true probability = the sharp median (`sf`=1,
  `ns` = sharp books); otherwise the wide median.
- Both versions drop quotes that break their own book's ladder order
  (`monotone()` in build.py): Nov 24 a junk Novig quote (LaMelo Ball PRA 49.5
  at -223 after 44.5 at +900) made 50+ look 66% likely at FanDuel +2200.
  Exchanges (`EXCHANGES`) count only at lines where they quote both sides and
  the two implied probabilities sum to 0.98-1.15 (one-sided exchange orders
  produced 15-30% fake edges on 2-book rungs).
  Logs restarted Nov 24 ~8:00 PM ET after these fixes.
- Pages are generated: edit `docs/index.html` / `docs/plays.html`, then run
  `python scripts/make_wide_pages.py`. Never edit `docs/wide/*.html` by hand.
- Own play log `data/wide_plays_log.json`, summary `docs/wide/results.json`.
- Head-to-head `data/compare_log.json` -> `docs/compare.json`: every rung both
  price where wide used sharp books; P(over) first and last before kickoff from
  each; Brier and log loss once graded; difference with an SE clustered by prop.
- Refresh is hourly during the trial. If Ryan cancels: see the header of
  `.github/workflows/refresh.yml` (every 2 days, caps 25/20, BUILD_WIDE=0).
- Decision at day 6 (Nov 30 - Dec 1) from the head-to-head; profit after a week
  is noise and is not the yardstick.

## Pinnacle version (added Nov 25, 2026)

- Pages `docs/pinnacle/` (generated with the wide pages by
  `scripts/make_wide_pages.py`), data `docs/pinnacle/data.json` from
  `scripts/pinnacle.py`: PinnOdds (unofficial Pinnacle feed, "not affiliated
  with Pinnacle"), key `PINNODDS_API_KEY`, 2 requests a run (Football and
  Basketball fixtures with `include_specials=nested`; prices come inline).
- Pinnacle posts ONE line per prop (both sides). Its vig is removed (power
  method) and the 9-book market ladder is shifted in log-odds so it matches
  Pinnacle exactly at Pinnacle's line (`pin.shift`). All four sports, but
  Pinnacle posts few college props (13 NCAA football, 0 basketball on Nov 25). Props Pinnacle doesn't
  price keep the 9-book numbers with `pin: null` and are flagged.
- Own play log `data/pin_plays_log.json` (Pinnacle-priced props only) ->
  `docs/pinnacle/results.json`; head-to-head vs 9-book `data/compare_pin_log.json`
  -> `docs/compare_pin.json`; Results page `?v=pin`.
- Pinnacle's NBA prop limits are low (~$250) vs NFL ($3,000-7,500).

## Kalshi (added Nov 25, 2026)

- `scripts/kalshi.py` runs after `build.py`: Kalshi's public API (no key, works
  on any SGO plan) for NFL and NBA player-prop ladders (no college player props
  on Kalshi). Matched to our rungs by sport, stat (`SERIES` map), normalized
  player name, game date (ET) and exact line. Stored per rung: `kao`/`kau`
  American odds AFTER the taker fee (0.07 x P x (1-P)), `kpo`/`kpu` the ask in
  cents. Kalshi is a place to bet here, not a true-probability source (the Wide
  version still uses SGO's two-sided Kalshi quotes as a sharp source).
- No profit boosts on Kalshi. Settlement: on non-Protected markets a player who
  doesn't play resolves NO (Over loses, Under wins); track.py grades `ka` plays
  that way, while DK/FD bets on a DNP are void.

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

- Ryan bets DraftKings and FanDuel ($10 units, with profit boosts) and, from
  Nov 25, 2026, Kalshi (asked for; check it is available in his state).
- Coverage and fairOdds checks: `scripts/coverage_test.py`,
  `scripts/fairodds_check.py` (manual Actions, reports in `coverage/`).
- Mockup: Prop Ladder design canvas on claude.ai (Nov 24, 2026).

## Site bar (Nov 26, 2026)

Every page (`index.html`, `plays.html`, `results.html`, and the generated wide and Pinnacle pages)
loads the Weekly Gridiron Board's site bar as the first thing in `<body>`:
`<script src="/site-bar.js" data-shell="2"></script>`. The script lives in rhyman7/rhyman7.github.io;
change the bar there. It gives the pages the Back arrow inside the home-screen app. The bar lists
Prop Ladder under Tools and has no link to Results. The page tabs are styled as
`nav[aria-label=Pages]` in `style.css`, not bare `nav`, so those styles don't reach the bar.

## Phones (Nov 26, 2026; 760px and under)

The ladder table, the All +EV plays table and Results' summary tables show one card per row.
The rules are the last block of `docs/style.css`; the tables carry `m-ladder` and `m-plays`
(set in `docs/index.html` and `docs/plays.html`, so the generated wide and Pinnacle pages get
them too). Each number's label is written in that block by column position, so **a column
added, removed or reordered in one of those tables means updating its labels there**. A book
that doesn't offer a rung is left off that rung's card. All +EV plays shows the first 25 with
a "Show all plays" button. Column sorting is desktop-only; a phone keeps the default order.
Results' list of graded plays stays a table that scrolls sideways. Wider screens and print
must stay pixel-identical.
