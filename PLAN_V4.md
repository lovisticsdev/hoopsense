# HoopSense v4 — Complete Refinement Plan

## Overview

Upgrade the prediction model from v3 (SRS-dominant with basic adjustments) to v4
(multi-signal power score with matchup-aware contextual adjustments). Zero changes
to the Kotlin frontend — all improvements happen in the Python pipeline.

---

## 1. DATA SOURCES

### Page 1 — Advanced Stats
**URL:** `basketball-reference.com/leagues/NBA_{year}.html`
**Table:** `Advanced Stats` (already fetched in v3)

Extract these columns (✅ = already extracted, 🆕 = new):

| Column | Variable | Purpose |
|--------|----------|---------|
| ✅ SRS | `srs` | Primary team strength metric |
| ✅ ORtg | `off_rating` | Offensive efficiency per 100 poss |
| ✅ DRtg | `def_rating` | Defensive efficiency per 100 poss |
| ✅ Pace | `pace` | Possessions per game |
| ✅ Off eFG% | `efg_pct` | Offensive effective FG% |
| ✅ Off TOV% | `tov_pct` | Offensive turnover rate |
| ✅ Off ORB% | `orb_pct` | Offensive rebound rate |
| ✅ Off FT/FGA | `ft_rate` | Offensive free throw rate |
| ✅ Def eFG% | `opp_efg_pct` | Opponent effective FG% |
| ✅ Def TOV% | `opp_tov_pct` | Opponent turnover rate |
| ✅ Def DRB% | `drb_pct` | Defensive rebound rate |
| ✅ Def FT/FGA | `opp_ft_rate` | Opponent free throw rate |
| 🆕 PW | `pyth_wins` | Pythagorean (expected) wins |
| 🆕 PL | `pyth_losses` | Pythagorean (expected) losses |
| 🆕 MOV | `mov` | Margin of victory |
| 🆕 SOS | `sos` | Strength of schedule |
| 🆕 NRtg | `nrtg` | Net rating (ORtg - DRtg) |
| 🆕 TS% | `ts_pct` | True shooting percentage |
| 🆕 W | `wins` | Actual wins (for Pyth comparison) |
| 🆕 L | `losses` | Actual losses |

### Page 2 — Standings (3 tables from 1 page fetch)
**URL:** `basketball-reference.com/leagues/NBA_{year}_standings.html`

#### Table A: Expanded Standings (already fetched in v3, parsing expanded)

| Column | Variable | Purpose |
|--------|----------|---------|
| ✅ Overall | `overall` | Full season W-L |
| ✅ Home | `home` | Home record |
| ✅ Road | `away` | Away record |
| ✅ Margin ≤3 | `close_games` | Record in games decided by ≤3 pts |
| ✅ Margin ≥10 | `blowouts` | Record in blowout games |
| 🆕 Conf E | `vs_east` | Record vs Eastern Conference |
| 🆕 Conf W | `vs_west` | Record vs Western Conference |
| 🆕 Conf A | `vs_atlantic` | Record vs Atlantic Division |
| 🆕 Conf C | `vs_central` | Record vs Central Division |
| 🆕 Div SE | `vs_southeast` | Record vs Southeast Division |
| 🆕 Div NW | `vs_northwest` | Record vs Northwest Division |
| 🆕 Div P | `vs_pacific` | Record vs Pacific Division |
| 🆕 Div SW | `vs_southwest` | Record vs Southwest Division |
| 🆕 AS Pre | `pre_allstar` | Record before All-Star break |
| 🆕 AS Post | `post_allstar` | Record after All-Star break |
| 🆕 Mo Oct–Apr | `monthly.*` | Record for each month (all 7 columns) |

Division column mapping verified against OKC's row:
- A(6-1) + C(5-3) + SE(7-2) = E(18-6) ✓
- NW(11-3) + P(14-1) + SW(12-5) = W(37-9) ✓
- E(18-6) + W(37-9) = Overall(55-15) ✓

#### Table B: Team vs. Team (🆕 — new table, same page)

The 30×30 head-to-head matrix. Columns are team abbreviations (ATL, BOS, BRK, ..., WAS).
Each cell contains a record like "2-1" or "1-0".

Parse into: `h2h_matrix[team_abbr][opponent_abbr] = "W-L"`

Note: B-Ref uses "BRK" for Brooklyn, not "BKN". Map accordingly.

### API — balldontlie.io (unchanged HTTP calls)

| Endpoint | Purpose |
|----------|---------|
| `/nba/v1/games?dates[]=today&dates[]=yesterday` | Today's schedule + B2B detection |
| `/nba/v1/games?dates[]=DATE` | Historical game results for grading |

🆕 **New API call:** Fetch each team's last 10 games for rolling form calculation.
Endpoint: `/nba/v1/games?team_ids[]=ID&per_page=10` (sorted by date desc).
This runs once per team in today's games (max ~20 calls), not all 30 teams.

### Total HTTP Requests

| Target | v3 | v4 | Notes |
|--------|-----|-----|-------|
| B-Ref main page | 1 | 1 | No change |
| B-Ref standings page | 1 | 1 | Parse 1 extra table from same HTML |
| BDL schedule (today+yesterday) | 1 | 1 | No change |
| BDL recent games per team | 0 | ~10-12 | New: last-10 for teams in today's slate |
| **Total** | **3** | **~14** | Modest increase, all rate-limit-safe |

---

## 2. CONFIGURATION CHANGES (config.py)

### New: Division Registry

```python
TEAM_DIVISIONS = {
    # Atlantic (East)
    "BOS": {"conference": "EAST", "division": "ATL_DIV"},
    "BKN": {"conference": "EAST", "division": "ATL_DIV"},
    "NYK": {"conference": "EAST", "division": "ATL_DIV"},
    "PHI": {"conference": "EAST", "division": "ATL_DIV"},
    "TOR": {"conference": "EAST", "division": "ATL_DIV"},
    # Central (East)
    "CHI": {"conference": "EAST", "division": "CEN_DIV"},
    "CLE": {"conference": "EAST", "division": "CEN_DIV"},
    "DET": {"conference": "EAST", "division": "CEN_DIV"},
    "IND": {"conference": "EAST", "division": "CEN_DIV"},
    "MIL": {"conference": "EAST", "division": "CEN_DIV"},
    # Southeast (East)
    "ATL": {"conference": "EAST", "division": "SE_DIV"},
    "CHA": {"conference": "EAST", "division": "SE_DIV"},
    "MIA": {"conference": "EAST", "division": "SE_DIV"},
    "ORL": {"conference": "EAST", "division": "SE_DIV"},
    "WAS": {"conference": "EAST", "division": "SE_DIV"},
    # Northwest (West)
    "DEN": {"conference": "WEST", "division": "NW_DIV"},
    "MIN": {"conference": "WEST", "division": "NW_DIV"},
    "OKC": {"conference": "WEST", "division": "NW_DIV"},
    "POR": {"conference": "WEST", "division": "NW_DIV"},
    "UTA": {"conference": "WEST", "division": "NW_DIV"},
    # Pacific (West)
    "GSW": {"conference": "WEST", "division": "PAC_DIV"},
    "LAC": {"conference": "WEST", "division": "PAC_DIV"},
    "LAL": {"conference": "WEST", "division": "PAC_DIV"},
    "PHX": {"conference": "WEST", "division": "PAC_DIV"},
    "SAC": {"conference": "WEST", "division": "PAC_DIV"},
    # Southwest (West)
    "DAL": {"conference": "WEST", "division": "SW_DIV"},
    "HOU": {"conference": "WEST", "division": "SW_DIV"},
    "MEM": {"conference": "WEST", "division": "SW_DIV"},
    "NOP": {"conference": "WEST", "division": "SW_DIV"},
    "SAS": {"conference": "WEST", "division": "SW_DIV"},
}

# Maps opponent division → which column key to look up in team's standings data
OPPONENT_DIV_TO_KEY = {
    "ATL_DIV": "vs_atlantic",
    "CEN_DIV": "vs_central",
    "SE_DIV":  "vs_southeast",
    "NW_DIV":  "vs_northwest",
    "PAC_DIV": "vs_pacific",
    "SW_DIV":  "vs_southwest",
}

# Maps opponent conference → which column key to look up
OPPONENT_CONF_TO_KEY = {
    "EAST": "vs_east",
    "WEST": "vs_west",
}
```

### New: v4 Model Weights

```python
# ── Power Score composition (v4) ──────────────────────
SRS_WEIGHT           = 0.50   # was 0.70
FOUR_FACTORS_WEIGHT  = 0.20   # was 0.30 (off+def combined)
PYTHAGOREAN_WEIGHT   = 0.15   # NEW
FORM_WEIGHT          = 0.15   # NEW (replaces old hot/cold streak)

# ── Pythagorean regression ────────────────────────────
PYTH_SCALING         = 0.30   # points per win of luck delta

# ── Form trajectory ───────────────────────────────────
FORM_MONTH_WEIGHTS   = [0.50, 0.30, 0.20]  # current, previous, 2 months ago
FORM_SCALING         = 8.0    # converts win% delta to points scale
POST_ASB_MIN_GAMES   = 5      # minimum post-ASB games to use that signal
LAST10_WEIGHT        = 0.60   # blend: 60% last-10, 40% monthly when both available

# ── Contextual adjustments ────────────────────────────
HOME_ADVANTAGE_BASE  = 2.5    # unchanged
HOME_ADVANTAGE_RANGE = (1.0, 4.0)  # unchanged
B2B_PENALTY_BASE     = -1.5   # unchanged
B2B_ROAD_EXTRA       = -0.5   # unchanged

# NEW adjustments
CONF_MATCHUP_SCALING  = 3.0   # converts conf win% delta to points
CONF_MATCHUP_CAP      = 1.0   # max ±1.0 points
DIV_MATCHUP_SCALING   = 2.0   # converts div win% delta to points
DIV_MATCHUP_CAP       = 0.75  # max ±0.75 points
CLOSE_GAME_SCALING    = 2.0   # converts close-game luck to points
CLOSE_GAME_CAP        = 1.0   # max ±1.0 points
CLOSE_GAME_MIN_GAMES  = 5     # need 5+ close games for signal
H2H_SCALING           = 1.5   # converts H2H win% delta to points
H2H_CAP               = 0.75  # max ±0.75 points
H2H_MIN_GAMES         = 2     # need 2+ H2H meetings for signal

# ── Spread → Probability ─────────────────────────────
LOGISTIC_K = 5.5  # unchanged

# ── Pick selection ────────────────────────────────────
HIGH_CONFIDENCE_PROB   = 0.65  # unchanged
MEDIUM_CONFIDENCE_PROB = 0.58  # unchanged
MIN_PICK_PROB          = 0.55  # unchanged
MIN_GAMES_FOR_STATS    = 10    # unchanged
```

### Remove from config.py
```python
# DELETE these (replaced by FORM_WEIGHT system):
# HOT_STREAK_BONUS = 0.75
# COLD_STREAK_PENALTY = -0.75
# HOT_STREAK_THRESHOLD = 7
# COLD_STREAK_THRESHOLD = 3

# DELETE these (replaced by single FOUR_FACTORS_WEIGHT):
# OFF_FOUR_FACTORS_WEIGHT = 0.15
# DEF_FOUR_FACTORS_WEIGHT = 0.15

# KEEP these (still used internally within Four Factors):
# OFF_FACTOR_WEIGHTS = {...}
# DEF_FACTOR_WEIGHTS = {...}
```

---

## 3. THE MODEL — STEP BY STEP

### Phase 1: Power Score (per-team, independent of opponent)

```
power_score = 0.50 × SRS
            + 0.20 × four_factors_net
            + 0.15 × pythagorean_regression
            + 0.15 × form_trajectory
```

#### Component 1: SRS (50%)

Read directly from Advanced Stats table. Already on a points scale.
League average = 0. Elite teams ≈ +8 to +11. Bad teams ≈ -5 to -10.

```python
srs_component = SRS_WEIGHT * stats["srs"]
```

#### Component 2: Four Factors Net (20%)

Offensive Four Factors (already implemented, unchanged math):
```python
off = 25.0 * (
    efg_pct  * 0.40
  + tov_pct  * (-0.25)
  + orb_pct  * 0.20
  + ft_rate  * 0.15
)
```

Defensive Four Factors (already implemented, unchanged math):
```python
def_ = ((
    opp_efg_pct  * (-0.40)
  + opp_tov_pct  * 0.25
  + drb_pct      * 0.20
  + opp_ft_rate  * (-0.15)
) + 0.06) * 25.0
```

Combined as a single net score:
```python
ff_net = off + def_
ff_component = FOUR_FACTORS_WEIGHT * ff_net
```

Note: The +0.06 centering offset in the defensive calculation makes league-average
defense score ≈ 0, so the net correctly represents "points of quality above/below average."

#### Component 3: Pythagorean Regression (15%) — NEW

From Advanced Stats, read PW (Pythagorean Wins) and W (Actual Wins):
```python
luck_delta = stats["pyth_wins"] - stats["wins"]
# Positive = team has been UNLUCKY (true quality better than record)
# Negative = team has been LUCKY (true quality worse than record)

pyth_factor = luck_delta * PYTH_SCALING  # 0.30 points per win of luck
pyth_component = PYTHAGOREAN_WEIGHT * pyth_factor
```

Example values from current data:
- LAL: PW=38, W=45 → delta = -7 → factor = -2.1 (they're overperforming)
- MIA: PW=41, W=38 → delta = +3 → factor = +0.9 (they're underperforming)
- OKC: PW=56, W=55 → delta = +1 → factor = +0.3 (about right)

#### Component 4: Form Trajectory (15%) — NEW (replaces hot/cold streak)

Three data sources, used in priority order:

**Source A — Last 10 Games (from BDL API, best signal):**
```python
last10_wins / 10 → last10_wpct
season_wpct = wins / (wins + losses)
last10_delta = last10_wpct - season_wpct
last10_form = last10_delta * FORM_SCALING  # ×8.0
```

**Source B — Post All-Star Record (from Expanded Standings):**
```python
if post_allstar_games >= POST_ASB_MIN_GAMES:
    post_wpct = post_allstar_wins / post_allstar_games
    post_delta = post_wpct - season_wpct
    post_form = post_delta * FORM_SCALING
```

**Source C — Weighted Monthly Records (from Expanded Standings, fallback):**
```python
# Find the 3 most recent months with data
# Weight: [0.50, 0.30, 0.20] for current, previous, two-ago
monthly_wpct = weighted_average(recent_3_months, FORM_MONTH_WEIGHTS)
monthly_delta = monthly_wpct - season_wpct
monthly_form = monthly_delta * FORM_SCALING
```

**Blending logic:**
```python
if last10 available AND post_asb available:
    form = LAST10_WEIGHT * last10_form + (1 - LAST10_WEIGHT) * post_form
elif last10 available:
    form = LAST10_WEIGHT * last10_form + (1 - LAST10_WEIGHT) * monthly_form
elif post_asb available:
    form = post_form
else:
    form = monthly_form

form_component = FORM_WEIGHT * form
```

### Phase 2: Matchup Adjustments (per-game, opponent-aware)

Applied to each team's power score before computing the spread.

#### Adjustment 1: Home Court Advantage (unchanged from v3)

```python
if is_home:
    home_wpct = parse_wins(home_record) / parse_total(home_record)
    away_wpct = parse_wins(away_record) / parse_total(away_record)
    diff = home_wpct - away_wpct
    hca = HOME_ADVANTAGE_BASE + (diff * 5.0)
    hca = clamp(hca, 1.0, 4.0)
    adjusted += hca
```

Home team only. Typical range: +1.5 to +3.5 points.

#### Adjustment 2: Back-to-Back Fatigue (unchanged from v3)

```python
if b2b or rest_days == 0:
    adjusted += B2B_PENALTY_BASE       # -1.5
    if not is_home:
        adjusted += B2B_ROAD_EXTRA     # additional -0.5
```

Penalty: -1.5 (home B2B) or -2.0 (road B2B).

#### Adjustment 3: Conference Matchup — NEW

When a team plays an opponent from a specific conference, check how they perform
against that conference vs their overall record:

```python
opponent_conf = TEAM_DIVISIONS[opponent_abbr]["conference"]
vs_conf_key = OPPONENT_CONF_TO_KEY[opponent_conf]
vs_conf_record = team_standings[vs_conf_key]  # e.g. "37-9"

vs_conf_wpct = win_pct(vs_conf_record)
overall_wpct = win_pct(overall_record)
delta = vs_conf_wpct - overall_wpct

conf_adj = clamp(delta * CONF_MATCHUP_SCALING, -CONF_MATCHUP_CAP, CONF_MATCHUP_CAP)
adjusted += conf_adj
```

Example: HOU overall .603, vs East .697 → delta = +.094 → adj = +0.28 pts vs East opponent.

Note: Same-conference games (EAST vs EAST) still use this — a team's vs_east record
tells us how they do within their own conference, which is valuable context.

#### Adjustment 4: Division Matchup — NEW

Same logic but at division level — more granular:

```python
opponent_div = TEAM_DIVISIONS[opponent_abbr]["division"]
vs_div_key = OPPONENT_DIV_TO_KEY[opponent_div]
vs_div_record = team_standings[vs_div_key]  # e.g. "6-1"

vs_div_wpct = win_pct(vs_div_record)
overall_wpct = win_pct(overall_record)
delta = vs_div_wpct - overall_wpct

# Require minimum games to avoid noise from tiny samples
vs_div_games = total_games(vs_div_record)
if vs_div_games >= 4:
    div_adj = clamp(delta * DIV_MATCHUP_SCALING, -DIV_MATCHUP_CAP, DIV_MATCHUP_CAP)
    adjusted += div_adj
```

#### Adjustment 5: Close-Game Regression — NEW

Teams with extreme records in ≤3 point games are experiencing luck:

```python
close_w, close_l = parse_record(close_games_record)  # from Expanded Standings ≤3 column
close_total = close_w + close_l

if close_total >= CLOSE_GAME_MIN_GAMES:
    close_wpct = close_w / close_total
    # Expected close-game win% ≈ 50% (coin flip)
    luck_amount = close_wpct - 0.50
    # SUBTRACT because being lucky means they're WORSE than record shows
    close_adj = clamp(-luck_amount * CLOSE_GAME_SCALING, -CLOSE_GAME_CAP, CLOSE_GAME_CAP)
    adjusted += close_adj
```

Example: Team is 10-3 in close games (.769) → luck = +.269 → adj = -0.54 pts (penalize luck).
Example: Team is 2-8 in close games (.200) → luck = -.300 → adj = +0.60 pts (reward unlucky).

#### Adjustment 6: Head-to-Head — NEW

From Team vs. Team table, get the season series between the two specific teams:

```python
h2h_record = h2h_matrix[team_abbr][opponent_abbr]  # e.g. "2-1"
h2h_w, h2h_l = parse_record(h2h_record)
h2h_total = h2h_w + h2h_l

if h2h_total >= H2H_MIN_GAMES:
    h2h_wpct = h2h_w / h2h_total
    delta = h2h_wpct - 0.50
    h2h_adj = clamp(delta * H2H_SCALING, -H2H_CAP, H2H_CAP)
    adjusted += h2h_adj
```

Applied to BOTH teams (home gets their H2H adj, away gets theirs — they'll be
opposite since the records mirror).

### Phase 3: Spread and Probability

```python
home_final = home_base_power + home_adjustments
away_final = away_base_power + away_adjustments

predicted_spread = round(home_final - away_final, 1)
# Positive = home favored, negative = away favored

home_win_prob = 1.0 / (1.0 + 10 ** (-predicted_spread / LOGISTIC_K))
away_win_prob = 1.0 - home_win_prob
```

Logistic K = 5.5 maps:
- Spread ±3 → ~61.5% / 38.5%
- Spread ±5 → ~68.5% / 31.5%
- Spread ±7 → ~74.7% / 25.3%
- Spread ±10 → ~82.0% / 18.0%

### Phase 4: Pick Selection (unchanged from v3)

1. For each game, take the team with higher win probability
2. Filter: must be ≥ 55% (MIN_PICK_PROB)
3. Sort by probability descending
4. Pick #1 → Lock (free pick)
5. Picks #2-4 → Premium picks
6. Confidence label: HIGH (≥65%), MEDIUM (≥58%), LOW (<58%)

---

## 4. FILE-BY-FILE CHANGES

### config.py
- ADD: `TEAM_DIVISIONS` dict (30 teams → conference + division)
- ADD: `OPPONENT_DIV_TO_KEY` and `OPPONENT_CONF_TO_KEY` mapping dicts
- ADD: New weight constants (PYTHAGOREAN_WEIGHT, FORM_WEIGHT, etc.)
- ADD: New adjustment constants (CONF_MATCHUP_*, DIV_MATCHUP_*, CLOSE_GAME_*, H2H_*)
- ADD: Form-related constants (FORM_MONTH_WEIGHTS, POST_ASB_MIN_GAMES, LAST10_WEIGHT)
- REMOVE: HOT_STREAK_*, COLD_STREAK_*, OFF_FOUR_FACTORS_WEIGHT, DEF_FOUR_FACTORS_WEIGHT
- UPDATE: SRS_WEIGHT from 0.70 → 0.50
- UPDATE: model version string to "4.0"
- KEEP: OFF_FACTOR_WEIGHTS, DEF_FACTOR_WEIGHTS (internal Four Factors weights unchanged)
- KEEP: LOGISTIC_K, spread_to_prob(), HOME_ADVANTAGE_*, B2B_*, pick thresholds

### fetch_ingredients.py
- UPDATE: `parse_advanced_stats()` — extract PW, PL, MOV, SOS, NRtg, TS%, W, L
- UPDATE: `parse_expanded_standings()` — extract conference records (E, W, A, C),
  division records (SE, NW, P, SW), All-Star split (Pre, Post), all 7 monthly columns
- ADD: `parse_h2h_matrix()` — new function to parse Team vs. Team table from standings HTML
- UPDATE: `fetch_all_bref_data()` — return h2h_matrix as 3rd element of tuple
- ADD: `fetch_last10_form()` — new function to get last 10 games per team from BDL API
- UPDATE: `fetch_all_ingredients()` — include h2h_matrix and last10 data in output

### prediction_engine.py
- UPDATE: `calculate_power_score()` — new 4-component formula (SRS + FF + Pyth + Form)
- ADD: `_pythagorean_regression()` — compute luck delta from PW vs W
- ADD: `_form_trajectory()` — compute weighted form from last10, post-ASB, and monthly
- UPDATE: `_form_adjustment()` → REPLACE with `_form_trajectory()` (delete old hot/cold)
- ADD: `_conference_matchup_adj()` — adjustment based on vs-conference record
- ADD: `_division_matchup_adj()` — adjustment based on vs-division record
- ADD: `_close_game_regression()` — adjustment based on ≤3 record
- ADD: `_h2h_adjustment()` — adjustment based on season series
- UPDATE: `apply_adjustments()` — new signature to accept opponent info + h2h + standings
- UPDATE: `predict_game()` — pass opponent context to apply_adjustments

### generate_picks.py
- UPDATE: `_build_game_object()` — pass h2h_matrix and standings to predict_game
- UPDATE: `_generate_reasoning()` — include new signals in reasoning text
  (Pythagorean delta, conference record, H2H record, close-game regression)
- UPDATE: model_version from "3.0" → "4.0"

### history_manager.py
- UPDATE: `_generate_historical_picks()` — pass h2h_matrix context when available
- ADD: DRY fix — import `_confidence_from_prob` from prediction_engine instead of
  duplicating as `_confidence_label`

### utils.py
- No changes needed (already clean)

### validate_output.py
- No changes needed (validates structure, not model specifics)

### Kotlin frontend
- **Zero changes.** The JSON schema is identical — same games, picks, history structure.
  The model improvements are invisible to the frontend. The only visible difference is
  `model_version: "4.0"` in metadata and richer reasoning text in pick objects.

---

## 5. DATA FLOW DIAGRAM

```
B-Ref Main Page ──→ parse_advanced_stats()
                      → SRS, PW, PL, MOV, SOS, NRtg, TS%, Four Factors, ORtg, DRtg, Pace

B-Ref Standings ──→ parse_expanded_standings()
                      → records, home/away, vs_east/west, vs_6_divisions,
                        pre/post ASB, close_games, blowouts, monthly (Oct-Apr)
                 ──→ parse_h2h_matrix()
                      → 30×30 dict of team-vs-team records

BDL API ──────────→ fetch_schedule_and_fatigue()
                      → today's games, yesterday's teams (B2B set)
                 ──→ fetch_last10_form()
                      → last 10 game results per team in today's slate

                        ┌─────────────────────────────┐
                        │   fetch_all_ingredients()    │
                        │   Merges all data into one   │
                        │   dict per team + h2h matrix │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │      predict_game()          │
                        │                              │
                        │  For each team:              │
                        │   1. calculate_power_score() │
                        │      → SRS + FF + Pyth + Form│
                        │   2. apply_adjustments()     │
                        │      → HCA + B2B + Conf +    │
                        │        Div + CloseGame + H2H │
                        │                              │
                        │  Then:                       │
                        │   3. spread = home - away    │
                        │   4. prob = logistic(spread) │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │     find_best_picks()        │
                        │  Sort by prob, select top 4  │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │  generate_daily_json()       │
                        │  Assemble + validate + write │
                        │  → data/nba_daily.json       │
                        └─────────────────────────────┘
```

---

## 6. PARSING DETAILS — HANDLING B-REF QUIRKS

### Advanced Stats Multi-Index

The table has a multi-level header:
- Top row: empty (for basic cols), "Offense Four Factors", "Defense Four Factors"
- Bottom row: actual column names

Current flatten logic using `prefix_map={"Offense": "Off_", "Defense": "Def_"}`
already works. The new columns (PW, PL, MOV, SOS, NRtg, TS%, W, L) are all in the
non-prefixed section, so they flatten to their raw names. No parsing changes needed
for the flatten logic — just extract more columns.

### Expanded Standings Multi-Index

Top row groups: "Place", "Conference", "Division", "All-Star", "Margin", "Month"
Bottom row: actual column names within each group

Current prefix_map needs one addition:
```python
prefix_map={
    "Conference": "Conf_",  # E, W, A, C → Conf_E, Conf_W, Conf_A, Conf_C
    "Division": "Div_",     # SE, NW, P, SW → Div_SE, Div_NW, Div_P, Div_SW
    "All-Star": "AS_",      # Pre, Post → AS_Pre, AS_Post
    "Margin": "Margin_",    # ≤3, ≥10 → Margin_≤3, Margin_≥10
    "Month": "Mo_",         # Oct, Nov, ... Apr → Mo_Oct, Mo_Nov, ...
},
passthrough_groups={"Place", "Unnamed", "Expanded"}
```

This is already in the code. No structural changes needed — just read more columns.

### Team vs. Team Table

This is a flat table (no multi-index). Columns are team abbreviations.
B-Ref quirk: uses "BRK" for Brooklyn (not "BKN" like BDL uses).

```python
def parse_h2h_matrix(html_content: str) -> Dict[str, Dict[str, str]]:
    tables = pd.read_html(io.StringIO(html_content), match="Team vs. Team")
    df = tables[0]

    # Build abbreviation mapping (B-Ref abbr → our abbr)
    BREF_ABBR_MAP = {"BRK": "BKN", "CHO": "CHA", "NOP": "NOP", ...}

    matrix = {}
    for _, row in df.iterrows():
        team_name = str(row["Team"])
        team_abbr = resolve_team_to_abbr(team_name)

        team_records = {}
        for col in df.columns:
            if col in ("Rk", "Team"):
                continue
            opp_abbr = BREF_ABBR_MAP.get(col, col)
            record = str(row[col]) if pd.notna(row[col]) else ""
            if record and record != "nan":
                team_records[opp_abbr] = record

        matrix[team_abbr] = team_records

    return matrix
```

---

## 7. ENHANCED REASONING TEXT

The `_generate_reasoning()` function in generate_picks.py gets richer context:

```python
# v3 reasoning:
"NYK (45-25) — model gives them a 97% win probability.
 Opponent: BKN (17-52). SRS: +6.16, Net Rtg: +6.6.
 Recent form: 2-3. Confidence: HIGH."

# v4 reasoning (same structure, more signals):
"NYK (45-25, Pyth 48-22) — model gives them a 97% win probability.
 Opponent: BKN (17-52). SRS: +6.16, Net Rtg: +6.6.
 Last 10: 7-3. Post-ASB: 12-5. Season series: NYK leads 3-0.
 NYK is 28-15 vs East. BKN is 2-2 in close games.
 Confidence: HIGH."
```

---

## 8. IMPLEMENTATION ORDER

1. **config.py** — Add division registry + new constants, remove old streak constants
2. **fetch_ingredients.py** — Expand Advanced Stats parser, expand Expanded Standings
   parser, add H2H parser, add last-10 BDL fetcher
3. **prediction_engine.py** — Rewrite power score + add all new adjustments
4. **generate_picks.py** — Update predict calls + reasoning text, bump model version
5. **history_manager.py** — DRY fix (import confidence func), update backfill to pass context
6. **Test** — Run with --dry-run, compare v3 vs v4 picks for same day, verify JSON schema

---

## 9. RISK MITIGATION

- **B-Ref column name changes:** All column reads use `_safe_float()` with defaults.
  If a column is missing/renamed, the component gracefully degrades to a neutral value.
- **Small sample sizes:** Division (4-8 games), H2H (2-4 games), and close-game (5-15 games)
  adjustments are all capped at small absolute values to prevent overreaction.
- **BDL rate limits:** Last-10 fetches use existing `_api_get()` with retry/backoff.
  Only fetch for teams in today's slate (~10-12 teams, not all 30).
- **Model regression:** If v4 performs worse than v3, the weight structure makes it easy
  to dial back — increase SRS_WEIGHT toward 0.70 and reduce new components toward 0.
