"""
Prediction Engine v5.

Power score = weighted blend of:
  - SRS (50%) — strength-of-schedule-adjusted net rating.
  - NRtg (10%) — pace-adjusted net rating (orthogonal to SRS, r≈0.85–0.90).
  - Pythagorean Regression (20%) — fractional luck adjustment.
  - Form Trajectory (20%) — weighted recent performance trend.

Matchup adjustments: HCA, road-warrior bonus, B2B, conference, division,
close-game regression, head-to-head.

All predictions are purely model-based. No market/odds data is used.
"""
import logging
from typing import Dict, List, Optional

from config import (
    SRS_WEIGHT, NRTG_WEIGHT, PYTHAGOREAN_WEIGHT, FORM_WEIGHT,
    PYTH_EXPONENT, PYTH_SCALING,
    FORM_MONTH_WEIGHTS, FORM_SCALING, POST_ASB_MIN_GAMES, LAST10_WEIGHT,
    HOME_ADVANTAGE_BASE, HOME_ADVANTAGE_RANGE,
    B2B_PENALTY_BASE, B2B_ROAD_EXTRA,
    ROAD_WARRIOR_MIN_AWAY_GAMES, ROAD_WARRIOR_MIN_WPCT,
    ROAD_WARRIOR_LEAGUE_AVG, ROAD_WARRIOR_SCALING, ROAD_WARRIOR_CAP,
    CONF_MATCHUP_SCALING, CONF_MATCHUP_CAP,
    DIV_MATCHUP_SCALING, DIV_MATCHUP_CAP, DIV_MIN_GAMES,
    CLOSE_GAME_SCALING, CLOSE_GAME_CAP, CLOSE_GAME_MIN_GAMES,
    H2H_SCALING, H2H_CAP, H2H_MIN_GAMES,
    DEFAULT_WIN_PROB, LOCK_CONFIDENCE_PROB, HIGH_CONFIDENCE_PROB,
    MIN_PICKS,
    spread_to_prob, confidence_from_prob,
    TEAM_DIVISIONS, OPPONENT_DIV_TO_KEY, OPPONENT_CONF_TO_KEY,
)
from utils import parse_record, record_win_pct, record_total_games, clamp

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
#  Power score components
# ═══════════════════════════════════════════════════════

def _fractional_pyth_wins(stats: dict) -> float:
    """
    Compute fractional Pythagorean wins from off/def ratings.
    Avoids the integer rounding in B-Ref's PW/PL that zeroes out
    the luck signal for ~30% of teams.
    """
    off_rtg = stats.get("off_rating", 110.0)
    def_rtg = stats.get("def_rating", 110.0)
    total = stats.get("wins", 0) + stats.get("losses", 0)
    if total == 0 or (off_rtg + def_rtg) == 0:
        return 0.0
    pyth_pct = off_rtg ** PYTH_EXPONENT / (off_rtg ** PYTH_EXPONENT + def_rtg ** PYTH_EXPONENT)
    return pyth_pct * total


def _pythagorean_regression(stats: dict) -> float:
    """
    Luck adjustment: fractional Pythagorean wins vs actual wins.
    Positive = unlucky (boost), negative = lucky (penalize).
    """
    actual_wins = stats.get("wins", 0)
    total = actual_wins + stats.get("losses", 0)
    if total == 0:
        return 0.0
    luck_delta = _fractional_pyth_wins(stats) - actual_wins
    return round(luck_delta * PYTH_SCALING, 3)


def _form_trajectory(form: dict, stats: dict) -> float:
    """
    Blend last-10 rolling form, post-All-Star record, and monthly form
    into a points-scale trajectory signal.
    """
    total_games = stats.get("wins", 0) + stats.get("losses", 0)
    if total_games == 0:
        return 0.0
    season_wpct = stats.get("wins", 0) / total_games

    last10_form = None
    last10_games = form.get("last10_games", 0)
    if last10_games >= 5:
        last10_wpct = form.get("last10_wins", 0) / last10_games
        last10_form = (last10_wpct - season_wpct) * FORM_SCALING

    post_form = None
    post_w, post_l = parse_record(form.get("post_allstar", "0-0"))
    post_total = post_w + post_l
    if post_total >= POST_ASB_MIN_GAMES:
        post_form = (post_w / post_total - season_wpct) * FORM_SCALING

    monthly_form = _weighted_monthly_form(form.get("monthly", {}), season_wpct)

    if last10_form is not None and post_form is not None:
        form_score = LAST10_WEIGHT * last10_form + (1 - LAST10_WEIGHT) * post_form
    elif last10_form is not None:
        secondary = monthly_form if monthly_form is not None else 0.0
        form_score = LAST10_WEIGHT * last10_form + (1 - LAST10_WEIGHT) * secondary
    elif post_form is not None:
        form_score = post_form
    elif monthly_form is not None:
        form_score = monthly_form
    else:
        form_score = 0.0

    return round(form_score, 3)


def _weighted_monthly_form(monthly: dict, season_wpct: float) -> Optional[float]:
    """Weighted form from the most recent 3 months with ≥2 games each."""
    month_order = ["apr", "mar", "feb", "jan", "dec", "nov", "oct"]
    active_months = []

    for mo in month_order:
        w, l = parse_record(monthly.get(mo, "0-0"))
        if w + l >= 2:
            active_months.append(w / (w + l))
        if len(active_months) == 3:
            break

    if not active_months:
        return None

    weights = FORM_MONTH_WEIGHTS[:len(active_months)]
    weight_sum = sum(weights)
    normalized = [w / weight_sum for w in weights]
    weighted_wpct = sum(wp * nw for wp, nw in zip(active_months, normalized))
    return (weighted_wpct - season_wpct) * FORM_SCALING


def calculate_power_score(stats: dict) -> float:
    """
    Base power score (excludes form trajectory).

    0.50 × SRS + 0.10 × NRtg + 0.20 × Pythagorean Regression.
    """
    if not stats:
        return 0.0
    return round(
        SRS_WEIGHT * stats.get("srs", 0.0)
        + NRTG_WEIGHT * stats.get("nrtg", 0.0)
        + PYTHAGOREAN_WEIGHT * _pythagorean_regression(stats),
        3,
    )


def calculate_full_power_score(stats: dict, form: dict) -> float:
    """Full power score including form trajectory."""
    base = calculate_power_score(stats)
    return round(base + FORM_WEIGHT * _form_trajectory(form, stats), 3)


# ═══════════════════════════════════════════════════════
#  Contextual adjustments
# ═══════════════════════════════════════════════════════

def _team_specific_hca(record: dict) -> float:
    """Team-specific home-court advantage from home/away record differential."""
    h_wins, h_losses = parse_record(record.get("home", "0-0"))
    a_wins, a_losses = parse_record(record.get("away", "0-0"))

    if h_wins + h_losses < 5 or a_wins + a_losses < 5:
        return HOME_ADVANTAGE_BASE

    diff = (h_wins / (h_wins + h_losses)) - (a_wins / (a_wins + a_losses))
    hca = HOME_ADVANTAGE_BASE + (diff * 5.0)
    floor, ceiling = HOME_ADVANTAGE_RANGE
    return round(clamp(hca, floor, ceiling), 2)


def _road_warrior_bonus(record: dict) -> float:
    """
    Bonus for teams with proven road records (away-side counterpart to HCA).

    Gate: away win% > 55% AND 15+ road games.
    Bonus: (away_wpct - league_avg_road) * scaling, clamped to [0, cap].
    Elite road teams (OKC, CLE, BOS) get ~0.5–1.0 points; others get 0.
    """
    a_wins, a_losses = parse_record(record.get("away", "0-0"))
    a_total = a_wins + a_losses

    if a_total < ROAD_WARRIOR_MIN_AWAY_GAMES:
        return 0.0

    away_wpct = a_wins / a_total
    if away_wpct < ROAD_WARRIOR_MIN_WPCT:
        return 0.0

    bonus = (away_wpct - ROAD_WARRIOR_LEAGUE_AVG) * ROAD_WARRIOR_SCALING
    return clamp(bonus, 0.0, ROAD_WARRIOR_CAP)


def _record_vs_segment_adj(
    team_standings: dict,
    overall_record: dict,
    standings_key: str | None,
    scaling: float,
    cap: float,
    min_games: int = 5,
) -> float:
    """Adjustment based on team's record vs an opponent segment (conference/division)."""
    if not standings_key:
        return 0.0

    vs_rec = team_standings.get(standings_key, "0-0")
    if record_total_games(vs_rec) < min_games:
        return 0.0

    overall_wins = overall_record.get("wins", 0)
    overall_losses = overall_record.get("losses", 0)
    overall_total = overall_wins + overall_losses
    overall_wpct = overall_wins / overall_total if overall_total > 0 else DEFAULT_WIN_PROB

    delta = record_win_pct(vs_rec) - overall_wpct
    return clamp(delta * scaling, -cap, cap)


def _conference_matchup_adj(
    team_standings: dict, overall_record: dict, opponent_abbr: str,
) -> float:
    opp_conf = TEAM_DIVISIONS.get(opponent_abbr, {}).get("conference")
    standings_key = OPPONENT_CONF_TO_KEY.get(opp_conf) if opp_conf else None
    return _record_vs_segment_adj(
        team_standings, overall_record, standings_key,
        CONF_MATCHUP_SCALING, CONF_MATCHUP_CAP,
    )


def _division_matchup_adj(
    team_standings: dict, overall_record: dict, opponent_abbr: str,
) -> float:
    opp_div = TEAM_DIVISIONS.get(opponent_abbr, {}).get("division")
    standings_key = OPPONENT_DIV_TO_KEY.get(opp_div) if opp_div else None
    return _record_vs_segment_adj(
        team_standings, overall_record, standings_key,
        DIV_MATCHUP_SCALING, DIV_MATCHUP_CAP, DIV_MIN_GAMES,
    )


def _close_game_regression(form: dict) -> float:
    """Penalize close-game luck (expected ~50%); negate to reduce inflated records."""
    close_w, close_l = parse_record(form.get("close_games", "0-0"))
    close_total = close_w + close_l
    if close_total < CLOSE_GAME_MIN_GAMES:
        return 0.0
    luck_amount = close_w / close_total - 0.50
    return clamp(-luck_amount * CLOSE_GAME_SCALING, -CLOSE_GAME_CAP, CLOSE_GAME_CAP)


def _h2h_adjustment(
    team_abbr: str, opponent_abbr: str, h2h_matrix: dict,
) -> float:
    if not h2h_matrix:
        return 0.0
    h2h_rec = h2h_matrix.get(team_abbr, {}).get(opponent_abbr, "")
    if not h2h_rec:
        return 0.0
    h2h_w, h2h_l = parse_record(h2h_rec)
    if h2h_w + h2h_l < H2H_MIN_GAMES:
        return 0.0
    delta = h2h_w / (h2h_w + h2h_l) - 0.50
    return clamp(delta * H2H_SCALING, -H2H_CAP, H2H_CAP)


def apply_adjustments(
    base_score: float,
    is_home: bool,
    record: dict,
    form: dict,
    b2b: bool,
    rest_days: int,
    team_abbr: str,
    opponent_abbr: str,
    team_standings: dict,
    h2h_matrix: dict,
) -> float:
    """Apply all contextual adjustments to a base power score."""
    adjusted = base_score

    # 1. Home-court advantage / Road-warrior bonus
    if is_home:
        adjusted += _team_specific_hca(record)
    else:
        adjusted += _road_warrior_bonus(record)

    # 2. Back-to-back fatigue
    if b2b or rest_days == 0:
        adjusted += B2B_PENALTY_BASE
        if not is_home:
            adjusted += B2B_ROAD_EXTRA

    # 3. Conference matchup
    adjusted += _conference_matchup_adj(team_standings, record, opponent_abbr)

    # 4. Division matchup
    adjusted += _division_matchup_adj(team_standings, record, opponent_abbr)

    # 5. Close-game regression
    adjusted += _close_game_regression(form)

    # 6. Head-to-head
    adjusted += _h2h_adjustment(team_abbr, opponent_abbr, h2h_matrix)

    return round(adjusted, 3)


# ═══════════════════════════════════════════════════════
#  Game prediction
# ═══════════════════════════════════════════════════════

def predict_game(
    home_team: Dict,
    away_team: Dict,
    h2h_matrix: Optional[Dict] = None,
) -> Dict:
    """Predict a single game. Returns power scores, spread, probabilities, confidence."""
    home_stats = (home_team or {}).get("stats")
    away_stats = (away_team or {}).get("stats")

    if not home_stats or not away_stats:
        missing = []
        if not home_stats:
            missing.append((home_team or {}).get("abbr", "HOME"))
        if not away_stats:
            missing.append((away_team or {}).get("abbr", "AWAY"))
        raise ValueError(f"Missing stats for: {', '.join(missing)}. Cannot predict.")

    h2h = h2h_matrix or {}
    home_abbr = (home_team or {}).get("abbr", "")
    away_abbr = (away_team or {}).get("abbr", "")

    home_base = calculate_full_power_score(home_stats, (home_team or {}).get("form", {}))
    away_base = calculate_full_power_score(away_stats, (away_team or {}).get("form", {}))

    home_power = apply_adjustments(
        home_base, True,
        (home_team or {}).get("record", {}),
        (home_team or {}).get("form", {}),
        (home_team or {}).get("b2b", False),
        (home_team or {}).get("rest_days", 1),
        home_abbr, away_abbr,
        (home_team or {}).get("standings", {}),
        h2h,
    )
    away_power = apply_adjustments(
        away_base, False,
        (away_team or {}).get("record", {}),
        (away_team or {}).get("form", {}),
        (away_team or {}).get("b2b", False),
        (away_team or {}).get("rest_days", 1),
        away_abbr, home_abbr,
        (away_team or {}).get("standings", {}),
        h2h,
    )

    predicted_spread = round(home_power - away_power, 1)
    home_win_prob = spread_to_prob(predicted_spread)
    away_win_prob = 1.0 - home_win_prob

    return {
        "home_power_score": home_power,
        "away_power_score": away_power,
        "predicted_spread": predicted_spread,
        "home_win_prob": round(home_win_prob, 4),
        "away_win_prob": round(away_win_prob, 4),
        "confidence": confidence_from_prob(max(home_win_prob, away_win_prob)),
    }


# ═══════════════════════════════════════════════════════
#  Pick selection
# ═══════════════════════════════════════════════════════

def find_best_picks(games: List[Dict]) -> List[Dict]:
    """
    Select picks:
      1. Take ALL LOCKs (prob >= 0.90).
      2. If < MIN_PICKS, fill with HIGHs (prob >= 0.80).
      3. Never surface below HIGH.
    Returns picks ranked by probability (highest first).
    """
    candidates = []

    for game in games:
        pred = game.get("prediction", {})
        home_prob = pred.get("home_win_prob", DEFAULT_WIN_PROB)
        away_prob = pred.get("away_win_prob", DEFAULT_WIN_PROB)
        home_info = game.get("home", {})
        away_info = game.get("away", {})

        if home_prob > away_prob and home_prob >= HIGH_CONFIDENCE_PROB:
            candidates.append({
                "game_id": game.get("id"),
                "selection": home_info.get("abbr", ""),
                "team_id": home_info.get("team_id", 0),
                "win_prob": round(home_prob, 4),
                "predicted_spread": pred.get("predicted_spread", 0),
                "confidence": pred.get("confidence", "LOW"),
            })
        elif away_prob > home_prob and away_prob >= HIGH_CONFIDENCE_PROB:
            candidates.append({
                "game_id": game.get("id"),
                "selection": away_info.get("abbr", ""),
                "team_id": away_info.get("team_id", 0),
                "win_prob": round(away_prob, 4),
                "predicted_spread": pred.get("predicted_spread", 0),
                "confidence": pred.get("confidence", "LOW"),
            })

    candidates.sort(key=lambda x: x["win_prob"], reverse=True)

    strongs = [c for c in candidates if c["win_prob"] >= LOCK_CONFIDENCE_PROB]
    if len(strongs) >= MIN_PICKS:
        return strongs

    strong_ids = {c["game_id"] for c in strongs}
    solids = [c for c in candidates if c["game_id"] not in strong_ids]
    needed = MIN_PICKS - len(strongs)
    return strongs + solids[:needed]
