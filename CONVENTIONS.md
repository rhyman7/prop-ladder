# Conventions — prop-ladder

Standalone page (planned: rhyman7.github.io/prop-ladder) that shows the true
probability of every rung of a player's stat ladder, from Pinnacle's no-vig
price, against DraftKings' and FanDuel's prices.

- **Data source:** SportsGameOdds (SGO), key in the `SGO_API_KEY` repository
  secret. Never put the key in the page, a committed file or a log.
- **Independent of fb-value-board.** This repo does not use The Odds API or its
  credits, and nothing here changes the value boards.
- **Allowance:** SGO counts one object per event returned. Every workflow caps
  events per run and says so in its header. Ask Ryan before anything that would
  use most of the month's allowance.
- **Books:** Pinnacle is the reference; Ryan bets only DraftKings and FanDuel,
  $10 units, with profit boosts.
- **Status:** coverage test only (Nov 24, 2026). Page not built yet; a mockup
  comes before anything goes live.
