# fairOdds check — 2026-11-24T23:41:49Z

Differences are SGO's fair probability minus our median de-vigged probability, in percentage points.

## NFL
```
{
 "events": 14,
 "props": 3056,
 "with_fairOdds": 2722,
 "compared": 251,
 "sgo_minus_ours_simple_pts": {
  "n": 251,
  "mean": 0.06,
  "mean_abs": 0.34,
  "median_abs": 0.25,
  "share_within_1pt": 0.96,
  "max_abs": 1.81
 },
 "sgo_minus_ours_power_pts": {
  "n": 251,
  "mean": 0.22,
  "mean_abs": 0.63,
  "median_abs": 0.5,
  "share_within_1pt": 0.805,
  "max_abs": 3.25
 },
 "rungs_by_two_sided_books": {
  "0": 10024,
  "1": 952,
  "2": 206,
  "3": 97,
  "4": 205
 },
 "dkfd_rungs_by_two_sided_books": {
  "0": 6867,
  "1": 830,
  "2": 191,
  "3": 96,
  "4": 205
 },
 "fair_line_vs_dk_line": {
  "different": 373,
  "same": 514
 }
}
```
## NCAAF
```
{
 "events": 20,
 "props": 992,
 "with_fairOdds": 639,
 "compared": 66,
 "sgo_minus_ours_simple_pts": {
  "n": 66,
  "mean": 0.08,
  "mean_abs": 0.46,
  "median_abs": 0.22,
  "share_within_1pt": 0.879,
  "max_abs": 2.78
 },
 "sgo_minus_ours_power_pts": {
  "n": 66,
  "mean": 0.14,
  "mean_abs": 0.67,
  "median_abs": 0.34,
  "share_within_1pt": 0.758,
  "max_abs": 3.49
 },
 "rungs_by_two_sided_books": {
  "0": 4959,
  "1": 279,
  "2": 59,
  "3": 38,
  "4": 6
 },
 "dkfd_rungs_by_two_sided_books": {
  "0": 3633,
  "1": 214,
  "2": 59,
  "3": 38,
  "4": 6
 },
 "fair_line_vs_dk_line": {
  "different": 186,
  "same": 141
 }
}
```
## NBA
```
{
 "events": 12,
 "props": 1780,
 "with_fairOdds": 1521,
 "compared": 199,
 "sgo_minus_ours_simple_pts": {
  "n": 199,
  "mean": -0.14,
  "mean_abs": 0.55,
  "median_abs": 0.39,
  "share_within_1pt": 0.844,
  "max_abs": 4.91
 },
 "sgo_minus_ours_power_pts": {
  "n": 199,
  "mean": 0.16,
  "mean_abs": 0.71,
  "median_abs": 0.47,
  "share_within_1pt": 0.754,
  "max_abs": 4.85
 },
 "rungs_by_two_sided_books": {
  "0": 6710,
  "1": 789,
  "2": 125,
  "3": 51,
  "4": 214
 },
 "dkfd_rungs_by_two_sided_books": {
  "0": 4712,
  "1": 753,
  "2": 120,
  "3": 51,
  "4": 213
 },
 "fair_line_vs_dk_line": {
  "different": 162,
  "same": 233
 }
}
```
## NCAAB
```
{
 "events": 15,
 "props": 167,
 "with_fairOdds": 167,
 "compared": 4,
 "sgo_minus_ours_simple_pts": {
  "n": 4,
  "mean": 0.17,
  "mean_abs": 0.4,
  "median_abs": 0.26,
  "share_within_1pt": 1.0,
  "max_abs": 0.85
 },
 "sgo_minus_ours_power_pts": {
  "n": 4,
  "mean": 0.28,
  "mean_abs": 0.48,
  "median_abs": 0.39,
  "share_within_1pt": 0.75,
  "max_abs": 1.04
 },
 "rungs_by_two_sided_books": {
  "0": 458,
  "1": 8,
  "2": 3,
  "3": 2
 },
 "dkfd_rungs_by_two_sided_books": {
  "0": 402,
  "1": 5,
  "2": 3,
  "3": 2
 },
 "fair_line_vs_dk_line": {
  "same": 69,
  "different": 16
 }
}
```
## Examples
- {'league': 'NFL', 'market': 'Brandon McManus Field Goals Made Over/Under', 'line': 1.5, 'sgo_fair': '-133', 'sgo_prob': 0.5708, 'ours_simple': 0.5687, 'ours_power': 0.5757, 'books': 2}
- {'league': 'NFL', 'market': 'Trey Smack Field Goals Made Over/Under', 'line': 1.5, 'sgo_fair': '+104', 'sgo_prob': 0.4902, 'ours_simple': 0.4856, 'ours_power': 0.4839, 'books': 2}
- {'league': 'NFL', 'market': 'Brandon McManus Kicking Total Points Over/Under', 'line': 7.5, 'sgo_fair': '+103', 'sgo_prob': 0.4926, 'ours_simple': 0.503, 'ours_power': 0.5033, 'books': 2}
- {'league': 'NFL', 'market': 'Jordan Love Passing Attempts Over/Under', 'line': 36.5, 'sgo_fair': '+106', 'sgo_prob': 0.4854, 'ours_simple': 0.4797, 'ours_power': 0.4776, 'books': 5}
- {'league': 'NFL', 'market': 'Jordan Love Passing Completions Over/Under', 'line': 22.5, 'sgo_fair': '+103', 'sgo_prob': 0.4926, 'ours_simple': 0.4886, 'ours_power': 0.4875, 'books': 6}
- {'league': 'NFL', 'market': 'Matthew Stafford Passing Completions Over/Under', 'line': 22.5, 'sgo_fair': '+102', 'sgo_prob': 0.495, 'ours_simple': 0.4979, 'ours_power': 0.4977, 'books': 4}
- {'league': 'NFL', 'market': 'Jordan Love Interceptions Over/Under', 'line': 0.5, 'sgo_fair': '-123', 'sgo_prob': 0.5516, 'ours_simple': 0.5435, 'ours_power': 0.5481, 'books': 6}
- {'league': 'NFL', 'market': 'Matthew Stafford Interceptions Over/Under', 'line': 0.5, 'sgo_fair': '-117', 'sgo_prob': 0.5392, 'ours_simple': 0.5408, 'ours_power': 0.5447, 'books': 5}
- {'league': 'NFL', 'market': 'Jordan Love Longest Completion Over/Under', 'line': 39.5, 'sgo_fair': '+104', 'sgo_prob': 0.4902, 'ours_simple': 0.4949, 'ours_power': 0.4944, 'books': 2}
- {'league': 'NFL', 'market': 'Jordan Love Passing Touchdowns Over/Under', 'line': 1.5, 'sgo_fair': '+103', 'sgo_prob': 0.4926, 'ours_simple': 0.4928, 'ours_power': 0.4921, 'books': 6}
- {'league': 'NFL', 'market': 'Matthew Stafford Passing Touchdowns Over/Under', 'line': 1.5, 'sgo_fair': '+123', 'sgo_prob': 0.4484, 'ours_simple': 0.445, 'ours_power': 0.4396, 'books': 6}
- {'league': 'NFL', 'market': 'Blake Corum Longest Reception Over/Under', 'line': 7.5, 'sgo_fair': '+105', 'sgo_prob': 0.4878, 'ours_simple': 0.4869, 'ours_power': 0.4855, 'books': 3}
