# HoopSense V6 Plan: Model Accuracy & Data Integrity Overhaul

**Objective:** Address every issue surfaced by the deep audit — mathematical flaws, data integrity gaps, selection bias, inflated history, and missing signals. V5 was about code quality. V6 is about **making the predictions better and the data honest**.

**Baseline metrics (from audit):**
- Historical win rate: 88.1% (59 graded picks, 52W-7L) — **inflated by backfill**
- Home-team selection bias: 89.2% of all picks are home teams
- 8 of 30 teams have zero Pythagorean luck adjustment (integer rounding)
- Charlotte Hornets last-10 data = 0 (missing entirely)
- 7 losses, all on LOCK-tier picks (>90% confidence) — calibration issue
- Duplicate probabilities across dates (model staleness from static backfill)

---

## Phase 1: Fix Inflated History (Honesty Layer)

**Problem:** Backfilled picks use today's stats to "predict" past games. The 88.1% win rate is not real out-of-sample accuracy. Users see this as the model's track record and may make real betting decisions based on it.

**Files:** `scripts/history_manager.py`, `scripts/generate_picks.py`, `app/.../model/DailyData.kt`, `app/.../screens/history/HistoryScreen.kt`

### 1.1 `history_manager.py` — Tag backfilled vs real-time picks

```python
# Line ~170, in _generate_historical_picks(), add to each candidate dict:
"backfilled": True,

# Line ~219, in update_and_get_history(), when archiving daily picks:
if picks and picks.get("date") and picks["date"] not in history_data:
    # Tag all picks in this slip as real-time (not backfilled)
    _tag_picks_realtime(picks)
    history_data[picks["date"]] = picks
```

Add helper:
```python
def _tag_picks_realtime(slip: dict) -> None:
    """Mark all picks in a slip as real-time (not backfilled)."""
    if slip.get("lock"):
        slip["lock"]["backfilled"] = False
    for p in slip.get("premium", []):
        p["backfilled"] = False
```

### 1.2 `history_manager.py` — Split stats in history payload

Change the return value of `update_and_get_history()` (line ~247):

```python
# Compute separate stats for real-time vs backfilled
realtime_picks = []
backfilled_picks = []
for slip in past_slips:
    for pick in _get_all_picks(slip):
        if pick.get("backfilled", True):
            backfilled_picks.append(pick)
        else:
            realtime_picks.append(pick)

return {
    "past_slips": past_slips,
    "backfilled_dates": backfilled,
    "stats": {
        "realtime": _compute_stats(realtime_picks),
        "backfilled": _compute_stats(backfilled_picks),
        "combined": _compute_stats(realtime_picks + backfilled_picks),
    },
}
```

Add helper:
```python
def _compute_stats(picks: list) -> dict:
    wins = sum(1 for p in picks if p.get("status") == "WIN")
    losses = sum(1 for p in picks if p.get("status") == "LOSS")
    total = wins + losses
    return {
        "wins": wins,
        "losses": losses,
        "total": total,
        "win_rate": round(wins / total, 4) if total > 0 else 0.0,
    }
```

### 1.3 `DailyData.kt` — Add backfilled flag to Pick model

```kotlin
// In data/model/DailyData.kt, Pick data class:
@Serializable
data class Pick(
    // ... existing fields ...
    val backfilled: Boolean = true,  // NEW — default true for safety
)
```

### 1.4 `HistoryScreen.kt` — Visual distinction for backfilled picks

Add a subtle indicator (e.g., dashed border or small "Retroactive" tag) on picks where `backfilled == true`. Show separate win-rate stats: "Real-time: X-Y (Z%)" vs "Including backfill: A-B (C%)".

### 1.5 `history_manager.py` — Prune old history entries

**Problem:** `history_slips.json` currently has 16 dates but only 10 are shown. Old entries accumulate forever.

Add to `update_and_get_history()`, after grading (line ~242):

```python
# Prune dates outside the history window
valid_dates = set(dates)
valid_dates.add(datetime.now(timezone.utc).strftime("%Y-%m-%d"))  # keep today
pruned_keys = [k for k in history_data if k not in valid_dates]
for k in pruned_keys:
    del history_data[k]
if pruned_keys:
    logger.info(f"Pruned {len(pruned_keys)} old history entries: {pruned_keys}")
```

---

## Phase 2: Fix Pythagorean Regression (Math Fix)

**Problem:** Basketball-Reference rounds Pythagorean wins to integers. 8 of 30 teams have `pyth_wins == actual_wins`, so the luck-adjustment component contributes exactly 0.0 for them. Charlotte has a +8 delta (massively unlucky) but only gets +0.36 points total adjustment. Lakers have -7 (massively lucky) but only -0.315 penalty.

**Files:** `scripts/fetch_ingredients.py`, `scripts/prediction_engine.py`, `scripts/config.py`

### 2.1 `fetch_ingredients.py` — Compute fractional Pythagorean wins

In `parse_advanced_stats()`, after extracting `off_rating` and `def_rating`, compute our own Pythagorean expectation:

```python
# After line ~205, add computed Pythagorean:
off_rtg = _safe_float(row, "ORtg", 110.0)
def_rtg = _safe_float(row, "DRtg", 110.0)
total_games = _safe_int(row, "W", 0) + _safe_int(row, "L", 0)

# Morey exponent (13.91) for NBA Pythagorean expectation
MOREY_EXPONENT = 13.91
if off_rtg > 0 and def_rtg > 0 and total_games > 0:
    pyth_pct = off_rtg ** MOREY_EXPONENT / (
        off_rtg ** MOREY_EXPONENT + def_rtg ** MOREY_EXPONENT
    )
    pyth_wins_fractional = round(pyth_pct * total_games, 2)
else:
    pyth_wins_fractional = float(_safe_int(row, "PW", 0))

stats_dict[team_id] = {
    # ... existing fields ...
    "pyth_wins_fractional": pyth_wins_fractional,  # NEW
}
```

### 2.2 `prediction_engine.py` — Use fractional Pythagorean

Change `_pythagorean_regression()` (line ~86):

```python
def _pythagorean_regression(stats: dict) -> float:
    """Luck adjustment using fractional Pythagorean expectation."""
    # Prefer our own fractional computation; fall back to B-Ref integer
    pyth_wins = stats.get("pyth_wins_fractional", stats.get("pyth_wins", 0))
    actual_wins = stats.get("wins", 0)

    if pyth_wins == 0 and actual_wins == 0:
        return 0.0

    luck_delta = pyth_wins - actual_wins
    return round(luck_delta * PYTH_SCALING, 3)
```

### 2.3 `config.py` — Increase PYTH_SCALING

**Problem:** Even with fractional Pythagorean, `PYTH_SCALING = 0.30` yields tiny adjustments. An 8-game luck delta at 0.30 × 0.15 weight = only +0.36 total points. NBA research suggests luck-adjusted models should penalize/boost more aggressively.

```python
# config.py line 188
PYTH_SCALING = 0.50  # was 0.30 — increased for stronger luck adjustment
```

This means an 8-game unlucky team gets `8 × 0.50 × 0.15 = +0.60` boost (still modest but more meaningful).

### 2.4 `config.py` — Add Morey exponent constant

```python
# Add near PYTH_SCALING (line ~188):
MOREY_EXPONENT = 13.91  # NBA-specific Pythagorean exponent (Morey, 1993)
```

---

## Phase 3: Fix Home-Team Selection Bias

**Problem:** 89.2% of picks are home teams. The model adds +2.5 HCA to every home team, making it nearly impossible for away teams to surface. This means the model is essentially saying "pick the better team at home" every day, which doesn't add much value.

**Files:** `scripts/config.py`, `scripts/prediction_engine.py`

### 3.1 `config.py` — Reduce base HCA

NBA home-court advantage has been declining since 2020 (COVID era onward). Academic studies now estimate it at ~1.5-2.0 points, not 2.5.

```python
# config.py line 199
HOME_ADVANTAGE_BASE = 2.0     # was 2.5 — reflects post-COVID HCA decline
HOME_ADVANTAGE_RANGE = (0.5, 3.5)  # was (1.0, 4.0) — tighter range
```

### 3.2 `prediction_engine.py` — Give away teams a "road warrior" boost

Some teams are genuinely better on the road (e.g., Boston is 23-13 away). Add an away-team signal:

Add to `apply_adjustments()` (after line ~363):

```python
# 2b. Road warrior bonus (for teams with strong away records)
if not is_home:
    h_wins, h_losses = parse_record(record.get("home", "0-0"))
    a_wins, a_losses = parse_record(record.get("away", "0-0"))
    a_total = a_wins + a_losses
    h_total = h_wins + h_losses
    if a_total >= 10 and h_total >= 10:
        away_wpct = a_wins / a_total
        home_wpct = h_wins / h_total
        # If team is better on road than at home, give them a small boost
        if away_wpct > home_wpct:
            road_bonus = min((away_wpct - home_wpct) * 3.0, 1.0)
            adjusted += road_bonus
```

### 3.3 `config.py` — Add road warrior constants

```python
ROAD_WARRIOR_SCALING = 3.0
ROAD_WARRIOR_CAP = 1.0
ROAD_WARRIOR_MIN_GAMES = 10
```

---

## Phase 4: Fix Missing Last-10 Data

**Problem:** `fetch_last10_form` only fetches for teams on today's slate. Teams not playing today have `last10_games: 0` in the cache. When backfill predictions run for past dates, these teams have no form signal. Charlotte Hornets showed up with zeroed last-10 data.

**Files:** `scripts/fetch_ingredients.py`

### 4.1 `fetch_ingredients.py` — Fetch last-10 for ALL 30 teams

Change `fetch_all_ingredients()` (line ~698):

```python
# BEFORE (only slate teams):
slate_abbrs = set()
for game in todays_games:
    # ... collect only today's teams ...

# AFTER (all 30 teams):
all_abbrs = [info["abbr"] for info in NBA_TEAMS.values()]
last10_data = fetch_last10_form(all_abbrs, season_year)
```

**Trade-off:** This adds ~30 API calls (one per team) with 1.5-2.5s delay each ≈ 60-75 seconds extra. But it runs once daily and the data is cached.

### 4.2 `fetch_ingredients.py` — Add batch optimization

To reduce API calls, fetch recent games in bulk instead of per-team:

```python
def fetch_last10_form_bulk(season: int) -> Dict[str, Dict]:
    """Fetch last-10 form for all teams using date-range bulk query."""
    logger.info("Fetching last-10 form (bulk method)…")
    today = datetime.now(timezone.utc)

    # Fetch games from last 14 days (covers 10 games for most teams)
    results = {}
    for days_back in range(0, 15, 5):  # 3 API calls instead of 30
        start = (today - timedelta(days=days_back + 5)).strftime("%Y-%m-%d")
        end = (today - timedelta(days=days_back + 1)).strftime("%Y-%m-%d")
        time.sleep(HISTORY_API_DELAY + random.uniform(0.5, 2.0))
        result = _api_get("/nba/v1/games", {
            "start_date": start,
            "end_date": end,
            "seasons[]": season,
            "per_page": 100,
        })
        for game in result.get("data", []):
            if game.get("status") != "Final":
                continue
            results.setdefault("_all_games", []).append(game)

    # Tally per-team from the bulk results
    team_games: Dict[str, list] = {}
    for game in results.get("_all_games", []):
        home_abbr = game.get("home_team", {}).get("abbreviation", "")
        away_abbr = game.get("visitor_team", {}).get("abbreviation", "")
        for abbr in (home_abbr, away_abbr):
            if abbr:
                team_games.setdefault(abbr, []).append(game)

    form_data = {}
    for abbr, games in team_games.items():
        # Sort by date descending, take last 10
        games.sort(key=lambda g: g.get("date", ""), reverse=True)
        recent = games[:10]
        wins = losses = 0
        for game in recent:
            home_abbr = game.get("home_team", {}).get("abbreviation", "")
            home_score = game.get("home_team_score", 0)
            away_score = game.get("visitor_team_score", 0)
            if home_score == 0 and away_score == 0:
                continue
            is_home = home_abbr == abbr
            if (is_home and home_score > away_score) or (not is_home and away_score > home_score):
                wins += 1
            else:
                losses += 1
        form_data[abbr] = {
            "last10_wins": wins,
            "last10_losses": losses,
            "last10_games": wins + losses,
        }

    logger.info(f"Fetched last-10 form for {len(form_data)} teams (bulk).")
    return form_data
```

Replace the call in `fetch_all_ingredients()`:
```python
# BEFORE:
last10_data = fetch_last10_form(list(slate_abbrs), season_year)

# AFTER:
last10_data = fetch_last10_form_bulk(season_year)
```

---

## Phase 5: Fix Confidence Calibration

**Problem:** 7 out of 59 picks with >90% confidence LOST. That's a 12% loss rate on LOCK picks, but the model claims they're 90%+ certain. This suggests the logistic curve is too aggressive — it's producing overconfident probabilities.

**Files:** `scripts/config.py`

### 5.1 `config.py` — Recalibrate LOGISTIC_K

The current `LOGISTIC_K = 5.5` maps a +5.5 spread to 73% and +11 to 91%. NBA historical data shows:

- +5.5 point favorites win ~68-70% (not 73%)
- +11 point favorites win ~85-88% (not 91%)

The model is overconfident by ~3-5% at every spread level.

```python
# config.py line 227
LOGISTIC_K = 6.5  # was 5.5 — recalibrated to reduce overconfidence
```

With `K = 6.5`:
- +2.0 spread → 55% (was 58%)
- +5.5 spread → 68% (was 73%)
- +8.0 spread → 78% (was 83%)
- +11 spread → 87% (was 91%)
- +14 spread → 93% (was 96%)

This means fewer games will cross the LOCK (90%) threshold, but the ones that do will be more reliable.

### 5.2 `config.py` — Adjust confidence tiers to match new K

```python
# With K=6.5, recalibrate tiers:
LOCK_CONFIDENCE_PROB = 0.88       # was 0.90 — ~12+ pt spread with new K
HIGH_CONFIDENCE_PROB = 0.78       # was 0.80 — ~8-12 pt spread
MEDIUM_CONFIDENCE_PROB = 0.62     # was 0.65 — ~3.5-8 pt spread
```

**Alternative approach (less disruptive):** Keep K=5.5 and thresholds the same but add a **flattening adjustment** that pulls extreme probabilities toward 50%:

```python
def spread_to_prob(spread: float) -> float:
    """Point spread → win probability, with shrinkage toward 50%."""
    raw = 1.0 / (1.0 + math.pow(10, -spread / LOGISTIC_K))
    # Apply shrinkage: pull extreme probs toward 50% by SHRINKAGE_FACTOR
    SHRINKAGE = 0.05  # 5% shrinkage
    return raw * (1 - SHRINKAGE) + 0.5 * SHRINKAGE
```

This turns 91% → 86.5%, 73% → 69.9%, which is closer to real-world NBA accuracy.

**Decision:** Implement the shrinkage approach first (less risky, easy to tune). If backtesting confirms K=6.5 is better, switch later.

---

## Phase 6: Add Rest-Days Modeling

**Problem:** `rest_days` is binary (0 or 1). Teams with 2+ days rest get no advantage. NBA research shows significant edges: 2 days rest vs 0 days = ~3-4 point swing; 3+ days rest vs B2B = ~5 point swing.

**Files:** `scripts/fetch_ingredients.py`, `scripts/prediction_engine.py`, `scripts/config.py`

### 6.1 `fetch_ingredients.py` — Compute actual rest days

Change schedule fetching to look back 3 days instead of 1:

```python
def fetch_schedule_and_fatigue(season: int) -> Tuple[List[Dict], Dict[int, int]]:
    """Fetch schedule and compute rest days per team."""
    today = datetime.now(timezone.utc)

    # Look back 3 days for rest calculation
    date_strs = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(4)]
    result = _api_get("/nba/v1/games", {
        "dates[]": date_strs,
        "seasons[]": season,
    })

    # Track most recent game date per team
    team_last_game: Dict[int, str] = {}
    todays_games: List[Dict] = []
    today_str = date_strs[0]

    for game in result.get("data", []):
        game_date = game.get("date", "")[:10]
        home_id = _find_nba_team_id(game.get("home_team", {}))
        away_id = _find_nba_team_id(game.get("visitor_team", {}))
        if not home_id or not away_id:
            continue

        if game_date == today_str:
            todays_games.append({...})  # same as before
        else:
            # Track last game for rest calculation
            for tid in (home_id, away_id):
                if tid not in team_last_game or game_date > team_last_game[tid]:
                    team_last_game[tid] = game_date

    # Compute rest days
    rest_days_map: Dict[int, int] = {}
    for tid, last_date in team_last_game.items():
        delta = (today - datetime.strptime(last_date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )).days
        rest_days_map[tid] = delta - 1  # subtract 1: game yesterday = 0 rest days

    return todays_games, rest_days_map
```

### 6.2 `fetch_ingredients.py` — Update team assembly

```python
# In fetch_all_ingredients(), change:
"b2b": team_id in yesterdays_teams,
"rest_days": 0 if team_id in yesterdays_teams else 1,

# To:
"rest_days": rest_days_map.get(team_id, 2),  # default 2 if no recent game found
"b2b": rest_days_map.get(team_id, 2) == 0,
```

### 6.3 `prediction_engine.py` — Graduated rest adjustment

Replace the B2B section in `apply_adjustments()` (lines 359-363):

```python
# 2. Rest-day adjustment (graduated)
if rest_days == 0:  # B2B
    adjusted += B2B_PENALTY_BASE
    if not is_home:
        adjusted += B2B_ROAD_EXTRA
elif rest_days >= 2:  # Well-rested bonus
    adjusted += REST_BONUS_BASE
    if rest_days >= 3:
        adjusted += REST_BONUS_EXTRA
```

### 6.4 `config.py` — Add rest constants

```python
# Rest-day adjustments
B2B_PENALTY_BASE = -1.5    # existing
B2B_ROAD_EXTRA = -0.5      # existing
REST_BONUS_BASE = 0.5      # NEW — 2 days rest
REST_BONUS_EXTRA = 0.3     # NEW — 3+ days rest (cumulative with BASE)
```

---

## Phase 7: Fix Four Factors Defensive Centering

**Problem:** `_defensive_four_factors()` adds a hard-coded `+0.06` to center the defensive score around zero. This is a magic number with no derivation. If league averages shift, this constant becomes wrong.

**File:** `scripts/prediction_engine.py`, `scripts/config.py`

### 7.1 `config.py` — Document the centering constant

```python
# Defensive Four Factors centering offset.
# Derived from: league-average defensive factor ≈ -0.06, so adding 0.06 centers at zero.
# Recompute each season from league-average opp_efg, opp_tov, drb, opp_ftr.
DEF_CENTERING_OFFSET = 0.06
```

### 7.2 `prediction_engine.py` — Use the named constant

```python
def _defensive_four_factors(stats: dict) -> float:
    raw = (
        stats.get("opp_efg_pct", 0.500) * DEF_FACTOR_WEIGHTS["opp_efg"]
        + stats.get("opp_tov_pct", 0.140) * DEF_FACTOR_WEIGHTS["opp_tov"]
        + stats.get("drb_pct", 0.750) * DEF_FACTOR_WEIGHTS["drb"]
        + stats.get("opp_ft_rate", 0.250) * DEF_FACTOR_WEIGHTS["opp_ftr"]
    )
    return round((raw + DEF_CENTERING_OFFSET) * 25.0, 3)
```

### 7.3 (Ideal) `fetch_ingredients.py` — Compute centering from league average

In `parse_advanced_stats()`, after parsing all teams, compute the league-average defensive factor and use it dynamically:

```python
# After the for loop that builds stats_dict:
if len(stats_dict) == 30:
    avg_def = sum(
        s.get("opp_efg_pct", 0.5) * DEF_FACTOR_WEIGHTS["opp_efg"]
        + s.get("opp_tov_pct", 0.14) * DEF_FACTOR_WEIGHTS["opp_tov"]
        + s.get("drb_pct", 0.75) * DEF_FACTOR_WEIGHTS["drb"]
        + s.get("opp_ft_rate", 0.25) * DEF_FACTOR_WEIGHTS["opp_ftr"]
        for s in stats_dict.values()
    ) / 30
    # Store for use by prediction_engine
    for s in stats_dict.values():
        s["_league_def_offset"] = round(-avg_def, 4)
```

Then `_defensive_four_factors` uses `stats.get("_league_def_offset", DEF_CENTERING_OFFSET)`.

---

## Phase 8: Fix Version String Mismatch + Logging

**Problem:** `generate_picks.py` line 77 logs "HOOPSENSE v4" but `MODEL_VERSION = "5.0"`. When model changes, there's no way to trace which version produced which historical pick.

**Files:** `scripts/generate_picks.py`, `scripts/history_manager.py`

### 8.1 `generate_picks.py` — Fix log string

```python
# Line 77:
logger.info(f"═══ HOOPSENSE v{MODEL_VERSION} DAILY GENERATION START ═══")
```

### 8.2 `generate_picks.py` — Bump to v6

```python
MODEL_VERSION = "6.0"
```

### 8.3 `history_manager.py` — Stamp model version on each pick

In `_generate_historical_picks()`, add to each candidate:
```python
"model_version": MODEL_VERSION,
```

In `_build_pick()` in `generate_picks.py`:
```python
"model_version": MODEL_VERSION,
```

---

## Phase 9: Widen Conference/Division Caps

**Problem:** Conference matchup cap is ±1.0, division cap is ±0.75. Boston is 10-0 vs Pacific but the adjustment is clamped to +1.0. This suppresses meaningful signal.

**File:** `scripts/config.py`

### 9.1 `config.py` — Widen caps

```python
# Conference matchup
CONF_MATCHUP_SCALING = 4.0   # was 3.0
CONF_MATCHUP_CAP = 1.5       # was 1.0

# Division matchup
DIV_MATCHUP_SCALING = 3.0    # was 2.0
DIV_MATCHUP_CAP = 1.25       # was 0.75
```

---

## Phase 10: Improve `find_best_picks` Logic

**Problem:** The `if c not in strongs` comparison is O(n²) dict identity check, and semantically fragile (relies on object identity, not game_id equality).

**File:** `scripts/prediction_engine.py`

### 10.1 `prediction_engine.py` — Use set-based filtering

```python
def find_best_picks(games: List[Dict]) -> List[Dict]:
    candidates = []
    # ... existing candidate collection ...

    candidates.sort(key=lambda x: x["win_prob"], reverse=True)

    strongs = [c for c in candidates if c["win_prob"] >= LOCK_CONFIDENCE_PROB]

    if len(strongs) >= MIN_PICKS:
        return strongs

    # Use game_id set for O(1) lookup instead of list identity
    strong_ids = {c["game_id"] for c in strongs}
    solids = [c for c in candidates if c["game_id"] not in strong_ids]
    needed = MIN_PICKS - len(strongs)
    return strongs + solids[:needed]
```

---

## Phase 11: Add Early-Month Form Guard

**Problem:** Monthly form weights are [0.50, 0.30, 0.20] for most recent 3 months. Early in a month (e.g., March 2 with 1 game played), the current month is heavily weighted but has almost no data. The `>= 2` games guard helps but 2 games is still very small sample.

**File:** `scripts/prediction_engine.py`

### 11.1 `prediction_engine.py` — Raise minimum games per month

```python
def _weighted_monthly_form(monthly: dict, season_wpct: float) -> Optional[float]:
    # ...
    for mo in month_order:
        rec = monthly.get(mo, "0-0")
        w, l = parse_record(rec)
        total = w + l
        if total >= 4:  # was 2 — require more data per month
            active_months.append(w / total)
        if len(active_months) == 3:
            break
    # ...
```

---

## Summary: All Changes By File

| File | Changes | Phase |
|------|---------|-------|
| `scripts/config.py` | LOGISTIC_K shrinkage, PYTH_SCALING ↑, HCA ↓, rest constants, caps widened, DEF_CENTERING_OFFSET named, MOREY_EXPONENT, road warrior constants, confidence tiers adjusted | 2, 3, 5, 6, 7, 9 |
| `scripts/prediction_engine.py` | Fractional pyth, road warrior boost, graduated rest, DEF centering constant, `find_best_picks` set-based, monthly min games ↑ | 2, 3, 6, 7, 10, 11 |
| `scripts/fetch_ingredients.py` | Fractional pyth computation, bulk last-10 fetch, multi-day rest tracking | 2, 4, 6 |
| `scripts/history_manager.py` | Backfill tagging, split stats, history pruning, model version stamping | 1, 8 |
| `scripts/generate_picks.py` | Version bump to 6.0, fix log string, model version in picks | 8 |
| `app/.../model/DailyData.kt` | Add `backfilled` field to Pick | 1 |
| `app/.../screens/history/HistoryScreen.kt` | Visual distinction for backfilled picks, separate stats display | 1 |

---

## Implementation Priority

| Priority | Phase | Impact | Effort | Risk |
|----------|-------|--------|--------|------|
| **P0** | 1 (History honesty) | HIGH — user trust | 2 hr | Low |
| **P0** | 5 (Calibration) | HIGH — prediction accuracy | 1 hr | Medium |
| **P1** | 2 (Fractional Pyth) | MEDIUM — model accuracy | 1.5 hr | Low |
| **P1** | 4 (Last-10 fix) | MEDIUM — data completeness | 2 hr | Low |
| **P1** | 3 (Home bias) | MEDIUM — pick diversity | 1.5 hr | Medium |
| **P2** | 6 (Rest days) | MEDIUM — new signal | 2 hr | Medium |
| **P2** | 8 (Version fix) | LOW — housekeeping | 30 min | None |
| **P2** | 9 (Wider caps) | LOW — marginal accuracy | 15 min | Low |
| **P3** | 7 (Def centering) | LOW — code quality | 1 hr | Low |
| **P3** | 10 (Pick logic) | LOW — correctness | 15 min | None |
| **P3** | 11 (Month guard) | LOW — edge case | 15 min | None |

**Total estimated effort: ~12-13 hours**

---

## What V6 Does NOT Cover (Deferred to V7)

- **Injury/roster data integration** — the single biggest accuracy gap, but requires a new data source (NBA injury reports API or scraping). This is a separate project.
- **ML model replacement** — the heuristic model is well-structured; ML would need a training pipeline, historical dataset, and serving infrastructure.
- **Live game updates** — currently predictions are pre-game only. In-game probability updates would require real-time data feeds.
- **Line shopping / market data** — comparing model predictions against Vegas lines for edge detection. Would require an odds API subscription.
- **Historical backtesting framework** — running the model against past seasons to validate accuracy. Requires storing historical daily stats snapshots, not just current-day stats.
