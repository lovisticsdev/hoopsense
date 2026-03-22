# HoopSense v5 Plan: 8.1 → 9.5+

**Objective:** Systematically address every rubric gap to elevate the codebase from 8.1/10 to 9.5–10/10 across Clean Code, Efficiency, Architecture, and Robustness.

**Approach:** Changes are grouped into 7 phases ordered by impact and dependency. Each phase lists the rubric principles it addresses, the specific files affected, and the exact changes to make.

---

## Phase 1: Docstring & Comment Accuracy (30 min)

**Rubric:** Self-Documenting Code & Purposeful Comments

These are the lowest-hanging fruit — factual inaccuracies in documentation that actively mislead readers.

### 1.1 history_manager.py — Module docstring
- **Line 2:** Change `"maintain a 5-day rolling history"` → `"maintain a rolling history (window configured in config.py)"`
- **Line 203 (update_and_get_history docstring):** Change `"Backfill any missing days in the last 5"` → `"Backfill any missing days in the history window"`

### 1.2 prediction_engine.py — calculate_power_score docstring
- **Line 184-189:** Current docstring claims formula includes Form (0.15 × Form). The function body only uses SRS + Four Factors + Pythagorean. Fix:
```python
def calculate_power_score(stats: dict) -> float:
    """
    Base power score (excludes form trajectory).

    0.50 × SRS + 0.20 × Four Factors Net + 0.15 × Pythagorean Regression.
    League avg ≈ 0, elite ≈ +8 to +12.

    See calculate_full_power_score() for the complete score including form.
    """
```

### 1.3 generate_picks.py — MODEL_VERSION
- **Line 20:** Change `MODEL_VERSION = "4.0"` → `"5.0"` to reflect v5 changes.

### 1.4 Audit all remaining comments
- Remove any `# v4:` prefixes that no longer add value (they're historical noise now)
- Ensure every "why" comment actually explains *why*, not *what*

---

## Phase 2: Error Handling & Fail Fast (1-2 hours)

**Rubric:** Defensive Programming, Fail Fast, Error Handling

This is the biggest single gap. Currently 6.5/10 → target 9.5.

### 2.1 fetch_ingredients.py — Replace bare `except Exception` (3 locations)

The three B-Ref parsers (`parse_advanced_stats`, `parse_expanded_standings`, `parse_h2h_matrix`) all catch `Exception` and silently return `{}`. This masks structural changes in Basketball-Reference HTML that should be caught immediately.

**Change:** Narrow the exceptions and add structured error context:
```python
# parse_advanced_stats (line 211)
except (ValueError, KeyError) as e:
    logger.error(f"Advanced Stats parse failed — B-Ref schema may have changed: {e}")
    raise  # Fail fast — this is critical data
except pd.errors.EmptyDataError:
    logger.error("No Advanced Stats table found in HTML")
    raise RuntimeError("Basketball-Reference Advanced Stats table missing")
```

For `parse_expanded_standings` and `parse_h2h_matrix`, these are non-critical (the engine can run without them), so keep the return `{}` pattern but narrow the exception:
```python
except (ValueError, KeyError, IndexError) as e:
    logger.warning(f"Expanded standings parse failed (non-fatal): {e}")
    return {}
```

### 2.2 FileCache.kt — Replace `e.printStackTrace()` with proper logging

**Line 13-14:**
```kotlin
// BEFORE
} catch (e: Exception) {
    e.printStackTrace()
}

// AFTER
} catch (e: IOException) {
    Log.w("FileCache", "Failed to write cache file: $fileName", e)
}
```

### 2.3 validate_output.py — Comprehensive validation

Current validation is too shallow. Expand to check:

```python
def validate() -> bool:
    # ... existing checks ...

    # NEW: Validate game structure
    for i, game in enumerate(data.get("games", [])):
        for key in ("id", "start_time", "status", "home", "away", "prediction"):
            if key not in game:
                errors.append(f"game[{i}] missing '{key}'")

        pred = game.get("prediction", {})
        for prob_key in ("home_win_prob", "away_win_prob"):
            prob = pred.get(prob_key, -1)
            if not (0.0 <= prob <= 1.0):
                errors.append(f"game[{i}] {prob_key}={prob} out of [0,1] range")

        if pred.get("home_win_prob", 0) + pred.get("away_win_prob", 0) > 1.01:
            errors.append(f"game[{i}] probabilities sum > 1.0")

    # NEW: Validate pick-game cross-references
    game_ids = {g["id"] for g in data.get("games", []) if "id" in g}
    picks = data.get("picks") or {}
    for pick_name, pick in [("lock", picks.get("lock")),
                             *((f"premium[{i}]", p) for i, p in enumerate(picks.get("premium", [])))]:
        if pick and pick.get("game_id") not in game_ids:
            errors.append(f"{pick_name} references game_id={pick.get('game_id')} not in games list")

    # NEW: Validate confidence labels match probability tiers
    if picks.get("lock"):
        lock = picks["lock"]
        prob = lock.get("win_prob", 0)
        conf = lock.get("confidence", "")
        expected = _expected_confidence(prob)
        if conf != expected:
            errors.append(f"lock confidence='{conf}' but prob={prob} expects '{expected}'")
```

### 2.4 Remove duplicate validation

Currently validation exists in **both** `validate_output.py` AND `generate_picks.py` (`_validate_daily_json`). This is a DRY violation.

**Change:** Move all validation logic into a shared `validation.py` module. Both the pipeline and the standalone validator import from it.

```
scripts/
  validation.py          # NEW — single source of truth for all schema validation
  validate_output.py     # Thin wrapper: loads file → calls validation.validate()
  generate_picks.py      # Calls validation.validate(data) inline
```

### 2.5 generate_picks.py — Don't write invalid data

**Line 191:** Currently logs error then writes anyway. Change to:
```python
if not validate_daily_json(daily_data):
    raise RuntimeError("Generated JSON failed validation — aborting write")
```

---

## Phase 3: DRY & SRP Refactoring (2-3 hours)

**Rubric:** DRY, Single Responsibility, High Cohesion

### 3.1 prediction_engine.py — Unify conference/division matchup functions

`_conference_matchup_adj()` (lines 235-265) and `_division_matchup_adj()` (lines 268-296) are structurally identical. Extract a shared function:

```python
def _record_vs_opponent_adj(
    team_standings: dict,
    overall_record: dict,
    opponent_abbr: str,
    record_key_resolver,  # callable: abbr → standings key or None
    scaling: float,
    cap: float,
    min_games: int = 5,
) -> float:
    """Adjustment based on team's record vs a segment of opponents."""
    key = record_key_resolver(opponent_abbr)
    if not key:
        return 0.0

    vs_rec = team_standings.get(key, "0-0")
    if record_total_games(vs_rec) < min_games:
        return 0.0

    overall_total = overall_record.get("wins", 0) + overall_record.get("losses", 0)
    overall_wpct = overall_record.get("wins", 0) / overall_total if overall_total > 0 else 0.5

    delta = record_win_pct(vs_rec) - overall_wpct
    return clamp(delta * scaling, -cap, cap)
```

Then:
```python
def _conference_matchup_adj(standings, record, opp_abbr):
    return _record_vs_opponent_adj(
        standings, record, opp_abbr,
        lambda a: OPPONENT_CONF_TO_KEY.get(TEAM_DIVISIONS.get(a, {}).get("conference")),
        CONF_MATCHUP_SCALING, CONF_MATCHUP_CAP,
    )

def _division_matchup_adj(standings, record, opp_abbr):
    return _record_vs_opponent_adj(
        standings, record, opp_abbr,
        lambda a: OPPONENT_DIV_TO_KEY.get(TEAM_DIVISIONS.get(a, {}).get("division")),
        DIV_MATCHUP_SCALING, DIV_MATCHUP_CAP, DIV_MIN_GAMES,
    )
```

### 3.2 fetch_ingredients.py — Split into SRP modules

`fetch_ingredients.py` is 759 lines doing 5 different things: B-Ref scraping, B-Ref parsing, BDL API calls, BDL data transformation, and caching. Split into:

```
scripts/
  sources/
    __init__.py
    bref_scraper.py      # _create_scraper, _fetch_bref_page, _strip_comments
    bref_parser.py       # parse_advanced_stats, parse_expanded_standings, parse_h2h_matrix
    bdl_client.py        # _api_get, _get_api_key, fetch_schedule_and_fatigue, fetch_last10_form
    helpers.py           # _safe_float, _safe_int, _flatten_multi_columns, _normalize_bref_abbr
  fetch_ingredients.py   # Slim orchestrator: fetch_all_ingredients only, imports from sources/
```

Each file has a single responsibility and can be tested independently.

### 3.3 history_manager.py — Extract grading logic

`history_manager.py` does grading, backfilling, and archival. The grading logic (`_grade_pick`, `_grade_slip`) should be extractable if it grows, but for now the file is 246 lines — acceptable SRP. **No split needed**, but:

- **Fix:** `_grade_slip` extracts `all_picks` twice (line 92 and line 115). Extract once and pass through.

### 3.4 Kotlin ViewModels — Extract shared pattern

Both ViewModels have identical init + collect patterns. Create a base:

```kotlin
abstract class DataViewModel<S>(
    initialState: S,
    private val repository: GameRepository,
) : ViewModel() {

    protected val _uiState = MutableStateFlow(initialState)
    val uiState = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.dailyDataStream.collect { data ->
                if (data != null) onDataLoaded(data)
            }
        }
        viewModelScope.launch {
            repository.getDailyData().onFailure { onLoadFailed(it) }
        }
    }

    fun refresh() {
        _uiState.update { onRefreshStarted(it) }
        viewModelScope.launch {
            repository.getDailyData(forceRefresh = true)
                .onSuccess { _uiState.update { state -> onRefreshSuccess(state, it) } }
                .onFailure { _uiState.update { state -> onRefreshFailed(state, it) } }
        }
    }

    protected abstract fun onDataLoaded(data: DailyData)
    protected abstract fun onRefreshStarted(state: S): S
    protected abstract fun onRefreshSuccess(state: S, data: DailyData): S
    protected abstract fun onRefreshFailed(state: S, error: Throwable): S
    protected open fun onLoadFailed(error: Throwable) {}
}
```

Then BetslipViewModel and HistoryViewModel each become ~20 lines implementing the abstract methods.

---

## Phase 4: Architecture & Separation of Concerns (1-2 hours)

**Rubric:** SoC, DIP (Dependency Inversion), Loose Coupling

### 4.1 GameRepository — Extract date utility from FormatUtils

**Problem:** `GameRepository.kt` (data layer) imports `FormatUtils` (presentation/domain layer) for `isUtcToday()`. This violates Separation of Concerns.

**Fix:** Move `isUtcToday()` to a new `DateUtils` object in the data layer:

```kotlin
// data/util/DateUtils.kt
object DateUtils {
    fun isUtcToday(utcDateStr: String): Boolean {
        return try {
            LocalDate.parse(utcDateStr) == LocalDate.now(ZoneOffset.UTC)
        } catch (_: Exception) { false }
    }
}
```

`FormatUtils` can delegate to `DateUtils.isUtcToday()` or keep its own copy. Either way, the repository no longer reaches into presentation code.

### 4.2 GameRepository — Interface abstraction

**Problem:** ViewModels depend directly on `GameRepository` concrete class. This makes testing impossible without the real repository.

**Fix:** Extract interface:

```kotlin
// domain/repository/GameDataRepository.kt
interface GameDataRepository {
    val dailyDataStream: StateFlow<DailyData?>
    suspend fun getDailyData(forceRefresh: Boolean = false): Result<DailyData>
}

// data/repository/GameRepository.kt
class GameRepositoryImpl @Inject constructor(...) : GameDataRepository { ... }
```

Update AppModule to provide the interface:
```kotlin
@Provides @Singleton
fun provideGameRepository(impl: GameRepositoryImpl): GameDataRepository = impl
```

### 4.3 StatsGrid — Move computation to ViewModel

**Problem:** `StatsGrid.kt` computes wins/losses/winRate on every recomposition. This is data transformation that belongs in the ViewModel.

**Fix:** Add a `HistoryStats` data class and compute in HistoryViewModel:

```kotlin
data class HistoryStats(
    val wins: Int = 0,
    val losses: Int = 0,
    val pending: Int = 0,
    val winRate: Double = 0.0,
    val totalBets: Int = 0,
)

// In HistoryViewModel:
private fun computeStats(slips: List<Picks>): HistoryStats {
    val allPicks = slips.flatMap { slip ->
        buildList {
            slip.lock?.let { add(it) }
            addAll(slip.premium)
        }
    }
    val wins = allPicks.count { it.status?.uppercase() == "WIN" }
    val losses = allPicks.count { it.status?.uppercase() == "LOSS" }
    val total = wins + losses
    return HistoryStats(
        wins = wins, losses = losses,
        pending = allPicks.size - total,
        winRate = if (total > 0) (wins.toDouble() / total) * 100.0 else 0.0,
        totalBets = total,
    )
}
```

`StatsGrid` becomes a pure display component receiving pre-computed `HistoryStats`.

### 4.4 BetslipScreen — Pre-compute game lookup in ViewModel

**Problem:** `games.find { it.id == pick.gameId }` is called per-pick in composables. O(n*m) on every recomposition.

**Fix:** Build a `Map<String, Game>` in the ViewModel and expose it in `BetslipUiState`:

```kotlin
data class BetslipUiState(
    ...
    val gameById: Map<String, Game> = emptyMap(),  // NEW
)

// In data loading:
_uiState.update {
    it.copy(
        ...
        gameById = data.games.associateBy { game -> game.id },
    )
}
```

Composables use `uiState.gameById[pick.gameId]` — O(1) lookup.

---

## Phase 5: Naming & Readability Cleanup (1 hour)

**Rubric:** Meaningful Naming, KISS

### 5.1 Python naming improvements
| Current | Proposed | File |
|---------|----------|------|
| `mo` | `month_key` | fetch_ingredients.py:294 |
| `exp` | `standings_data` | fetch_ingredients.py:703 |
| `h2h` | `head_to_head` (or keep `h2h` — it's domain-standard) | Keep as-is |
| `conf` | `conference_record` | fetch_ingredients.py:265 |
| `clamp()` | Keep, but add type hints: `clamp(value: float, minimum: float, maximum: float) -> float` | utils.py:72 |

### 5.2 Kotlin naming improvements
| Current | Proposed | File |
|---------|----------|------|
| `BetslipUiState.error: String?` | `errorMessage: String?` | BetslipViewModel.kt |
| `Long.MAX_VALUE` for stale cache | Extract: `const val STALE_CACHE_NO_EXPIRY = Long.MAX_VALUE` | GameRepository.kt |
| `TAG` | Already good — standard Android pattern | — |

### 5.3 Remove abbreviation inconsistencies
- `_BREF_HEADERS` → `_BASKETBALL_REFERENCE_HEADERS` (or keep — `BREF` is well-known in NBA dev circles. **Decision: keep**, add one-line comment at first use)

---

## Phase 6: Robustness & Edge Cases (1-2 hours)

**Rubric:** Defensive Programming, Algorithmic Efficiency

### 6.1 validate_output.py — Handle corrupt JSON

**Line 17-18:** `json.load(f)` can throw `json.JSONDecodeError` but isn't wrapped:
```python
try:
    with open(DATA_FILE) as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(f"ERROR: nba_daily.json is not valid JSON: {e}")
    return False
```

### 6.2 Backfill bias disclosure

Add a constant and use it in the history payload:
```python
# history_manager.py
BACKFILL_DISCLAIMER = (
    "Backfilled dates use the current model state applied retroactively. "
    "Accuracy metrics for these dates may be inflated."
)
```

In the output JSON, add a `backfilled_dates` list so the app can display a subtle indicator:
```python
return {
    "past_slips": past_slips,
    "backfilled_dates": [d for d in dates if d not in original_history_dates],
}
```

### 6.3 Config — Add DEFAULT_WIN_PROB constant

The value `0.5` appears as a magic number in 6+ places across the codebase (prediction_engine, fetch_ingredients, PremiumGate). Define once:
```python
DEFAULT_WIN_PROB = 0.50  # Prior for no-information games
```

### 6.4 Kotlin data validation

Add `init` blocks to critical data classes for fail-fast:
```kotlin
@Serializable
data class GamePrediction(
    @SerialName("home_win_prob") val homeWinProb: Double = 0.5,
    @SerialName("away_win_prob") val awayWinProb: Double = 0.5,
    @SerialName("predicted_spread") val predictedSpread: Double = 0.0,
    val confidence: String = "LOW"
) {
    init {
        require(homeWinProb in 0.0..1.0) { "homeWinProb must be in [0,1], got $homeWinProb" }
        require(awayWinProb in 0.0..1.0) { "awayWinProb must be in [0,1], got $awayWinProb" }
    }
}
```

---

## Phase 7: Testability Foundation (2-3 hours)

**Rubric:** Testability

This is the biggest single-score gap (5/10 → 9/10). We don't need 100% coverage, but we need the *architecture* for tests and key unit tests.

### 7.1 Python tests

Create `scripts/tests/` with pytest:

```
scripts/tests/
    __init__.py
    test_prediction_engine.py    # Test spread_to_prob, confidence_from_prob, calculate_power_score
    test_validation.py           # Test the new validation module with valid/invalid fixtures
    test_utils.py                # Test parse_record, record_win_pct, clamp
    test_pick_selection.py       # Test find_best_picks with mock game data
    conftest.py                  # Shared fixtures (sample team data, game data)
```

**Priority tests** (highest value):
1. `spread_to_prob` — verify the logistic curve against known spreads
2. `confidence_from_prob` — verify tier boundaries exactly
3. `find_best_picks` — verify STRONG/SOLID selection logic with edge cases (0 candidates, all STRONGs, no STRONGs, exactly MIN_PICKS)
4. `validate()` — verify it catches all known error types
5. `parse_record` — verify edge cases ("0-0", "nan", empty string, "32-18")

### 7.2 Kotlin tests

The repository interface from Phase 4.2 enables ViewModel testing:

```kotlin
// test/FakeGameRepository.kt
class FakeGameRepository : GameDataRepository {
    private val _stream = MutableStateFlow<DailyData?>(null)
    override val dailyDataStream = _stream.asStateFlow()
    var nextResult: Result<DailyData> = Result.success(testDailyData())

    override suspend fun getDailyData(forceRefresh: Boolean) = nextResult
    fun emit(data: DailyData) { _stream.value = data }
}
```

**Priority tests:**
1. `FormatUtils` — timezone conversion, edge cases, fallbacks
2. `BetslipViewModel` — verify state transitions (loading → loaded, refresh → success/failure)
3. `HistoryStats` computation — verify win/loss counting

### 7.3 Add a `pytest.ini` or `pyproject.toml` test config

```toml
[tool.pytest.ini_options]
testpaths = ["scripts/tests"]
pythonpath = ["scripts"]
```

---

## Summary: Impact Per Phase

| Phase | Time | Rubric Impact | Score Gain |
|-------|------|---------------|------------|
| 1. Docstrings | 30 min | Self-Documenting: 7→9.5 | +0.3 |
| 2. Error Handling | 1-2 hr | Error Handling: 6.5→9.5, Fail Fast: 7.5→9.5 | +0.8 |
| 3. DRY & SRP | 2-3 hr | DRY: 7→9.5, SRP: 7.5→9.5 | +0.6 |
| 4. Architecture | 1-2 hr | SoC: 7.5→9.5, DIP: 7→9, Coupling: 7.5→9.5 | +0.5 |
| 5. Naming | 1 hr | Naming: 8→9.5, KISS: 8.5→9.5 | +0.2 |
| 6. Robustness | 1-2 hr | Defensive Programming: 7→9, Efficiency: 8.5→9.5 | +0.3 |
| 7. Testability | 2-3 hr | Testability: 5→9 | +0.8 |
| **Total** | **~10-14 hr** | | **8.1 → ~9.6** |

---

## What We're NOT Doing (and Why)

- **ML model replacement:** The friend flagged "hand-tuned heuristic, not learned." This is a product decision, not a code quality issue. The heuristic model is well-structured, configurable, and documented. Replacing it with ML would require a training pipeline, data warehouse, and model serving — a separate project entirely.
- **Google Play Billing integration:** Premium gate enforcement is real-world feature work, not refactoring. The gate architecture is already correct; it just needs the billing SDK wired in.
- **Launcher icon WebP fallback:** Cosmetic, not code quality.
- **fetch_ingredients split (Phase 3.2):** This is marked as the most ambitious change. If time is tight, it can be deferred — the file is long but readable. The other 6 phases deliver 80% of the score gain without it.

---

## Recommended Implementation Order

1. **Phase 1** (docstrings) — do first, fast wins, no risk
2. **Phase 2** (error handling) — highest score impact, moderate effort
3. **Phase 5** (naming) — quick, pairs well with Phase 2
4. **Phase 6** (robustness) — completes the error handling story
5. **Phase 4** (architecture) — structural changes, test before Phase 7
6. **Phase 3** (DRY/SRP) — most code movement, needs care
7. **Phase 7** (tests) — last, because it benefits from all prior refactors
