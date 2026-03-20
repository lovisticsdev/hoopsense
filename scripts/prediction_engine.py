"""
Prediction Engine v4.

Power score = weighted blend of:
  - SRS (50%) — strength-of-schedule-adjusted net rating.
  - Four Factors Net (20%) — offensive − defensive quality composite.
  - Pythagorean Regression (15%) — luck adjustment from expected vs actual wins.
  - Form Trajectory (15%) — weighted recent performance trend.

Matchup adjustments:
  - Home-court advantage (team-specific, 1.0–4.0 range).
  - Back-to-back fatigue (-1.5 home, -2.0 road).
  - Conference matchup (how team performs vs opponent's conference).
  - Division matchup (how team performs vs opponent's division).
  - Close-game regression (penalize/reward extreme close-game records).
  - Head-to-head (season series between the two specific teams).

All predictions are purely model-based. No market/odds data is used.
"""
import logging
from typing import Dict, List, Optional

from config import (
    # Power score weights
    SRS_WEIGHT, FOUR_FACTORS_WEIGHT, PYTHAGOREAN_WEIGHT, FORM_WEIGHT,
    # Four Factors internal weights
    OFF_FACTOR_WEIGHTS, DEF_FACTOR_WEIGHTS,
    # Pythagorean
    PYTH_SCALING,
    # Form
    FORM_MONTH_WEIGHTS, FORM_SCALING, POST_ASB_MIN_GAMES, LAST10_WEIGHT,
    # Home court
    HOME_ADVANTAGE_BASE, HOME_ADVANTAGE_RANGE,
    # B2B
    B2B_PENALTY_BASE, B2B_ROAD_EXTRA,
    # Conference matchup
    CONF_MATCHUP_SCALING, CONF_MATCHUP_CAP,
    # Division matchup
    DIV_MATCHUP_SCALING, DIV_MATCHUP_CAP, DIV_MIN_GAMES,
    # Close-game regression
    CLOSE_GAME_SCALING, CLOSE_GAME_CAP, CLOSE_GAME_MIN_GAMES,
    # Head-to-head
    H2H_SCALING, H2H_CAP, H2H_MIN_GAMES,
    # Spread → probability
    LOCK_CONFIDENCE_PROB, HIGH_CONFIDENCE_PROB, MEDIUM_CONFIDENCE_PROB,
    MIN_PICK_PROB,
    spread_to_prob,
    # Division/conference lookups
    TEAM_DIVISIONS, OPPONENT_DIV_TO_KEY, OPPONENT_CONF_TO_KEY,
)
from utils import parse_record, record_win_pct, record_total_games, clamp

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
#  Power score components
# ═══════════════════════════════════════════════════════

def _offensive_four_factors(stats: dict) -> float:
    """Offensive quality from Dean Oliver's Four Factors, scaled to ~points."""
    return round(25.0 * (
        stats.get("efg_pct", 0.500) * OFF_FACTOR_WEIGHTS["efg"]
        + stats.get("tov_pct", 0.140) * OFF_FACTOR_WEIGHTS["tov"]
        + stats.get("orb_pct", 0.250) * OFF_FACTOR_WEIGHTS["orb"]
        + stats.get("ft_rate", 0.250) * OFF_FACTOR_WEIGHTS["ftr"]
    ), 3)


def _defensive_four_factors(stats: dict) -> float:
    """Defensive quality from opponent-side Four Factors, centered around zero."""
    raw = (
        stats.get("opp_efg_pct", 0.500) * DEF_FACTOR_WEIGHTS["opp_efg"]
        + stats.get("opp_tov_pct", 0.140) * DEF_FACTOR_WEIGHTS["opp_tov"]
        + stats.get("drb_pct", 0.750) * DEF_FACTOR_WEIGHTS["drb"]
        + stats.get("opp_ft_rate", 0.250) * DEF_FACTOR_WEIGHTS["opp_ftr"]
    )
    return round((raw + 0.06) * 25.0, 3)


def _four_factors_net(stats: dict) -> float:
    """Combined offensive + defensive Four Factors score."""
    return _offensive_four_factors(stats) + _defensive_four_factors(stats)


def _pythagorean_regression(stats: dict) -> float:
    """
    Luck adjustment: compare Pythagorean (expected) wins to actual wins.

    Positive result = team has been UNLUCKY (boost them).
    Negative result = team has been LUCKY (penalize them).
    """
    pyth_wins = stats.get("pyth_wins", 0)
    actual_wins = stats.get("wins", 0)

    if pyth_wins == 0 and actual_wins == 0:
        return 0.0

    luck_delta = pyth_wins - actual_wins
    return round(luck_delta * PYTH_SCALING, 3)


def _form_trajectory(form: dict, stats: dict) -> float:
    """
    Compute form trajectory from multiple signals:
      1. Last-10 rolling record (best signal, from BDL API)
      2. Post-All-Star record (from Expanded Standings)
      3. Weighted monthly records (fallback)

    Returns a value on a points scale (positive = trending up, negative = trending down).
    """
    total_games = stats.get("wins", 0) + stats.get("losses", 0)
    if total_games == 0:
        return 0.0
    season_wpct = stats.get("wins", 0) / total_games

    # Source A: Last-10 rolling form
    last10_form = None
    last10_games = form.get("last10_games", 0)
    if last10_games >= 5:
        last10_wpct = form.get("last10_wins", 0) / last10_games
        last10_delta = last10_wpct - season_wpct
        last10_form = last10_delta * FORM_SCALING

    # Source B: Post-All-Star record
    post_form = None
    post_rec = form.get("post_allstar", "0-0")
    post_w, post_l = parse_record(post_rec)
    post_total = post_w + post_l
    if post_total >= POST_ASB_MIN_GAMES:
        post_wpct = post_w / post_total
        post_delta = post_wpct - season_wpct
        post_form = post_delta * FORM_SCALING

    # Source C: Weighted monthly form (fallback)
    monthly_form = _weighted_monthly_form(form.get("monthly", {}), season_wpct)

    # Blending: prioritize last-10, blend with post-ASB or monthly
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
    """
    Compute weighted form from the most recent 3 months with actual data.

    Weights: [0.50, 0.30, 0.20] for most recent, 2nd most recent, 3rd most recent.
    """
    month_order = ["apr", "mar", "feb", "jan", "dec", "nov", "oct"]
    active_months = []

    for mo in month_order:
        rec = monthly.get(mo, "0-0")
        w, l = parse_record(rec)
        total = w + l
        if total >= 2:  # need at least 2 games in a month to count
            active_months.append(w / total)
        if len(active_months) == 3:
            break

    if not active_months:
        return None

    # Truncate weights to match available months
    weights = FORM_MONTH_WEIGHTS[:len(active_months)]
    weight_sum = sum(weights)
    normalized = [w / weight_sum for w in weights]

    weighted_wpct = sum(wp * nw for wp, nw in zip(active_months, normalized))
    return (weighted_wpct - season_wpct) * FORM_SCALING


def calculate_power_score(stats: dict) -> float:
    """
    Team power score on a points scale. League avg ≈ 0, elite ≈ +8 to +12.

    v4 formula:
      0.50 × SRS + 0.20 × Four Factors Net + 0.15 × Pythagorean + 0.15 × Form
    """
    if not stats:
        return 0.0

    return round(
        SRS_WEIGHT * stats.get("srs", 0.0)
        + FOUR_FACTORS_WEIGHT * _four_factors_net(stats)
        + PYTHAGOREAN_WEIGHT * _pythagorean_regression(stats),
        3,
    )


def calculate_full_power_score(stats: dict, form: dict) -> float:
    """
    Full power score including form trajectory.

    Separated from calculate_power_score so form can be passed independently.
    """
    base = calculate_power_score(stats)
    form_component = FORM_WEIGHT * _form_trajectory(form, stats)
    return round(base + form_component, 3)


# ═══════════════════════════════════════════════════════
#  Contextual adjustments
# ═══════════════════════════════════════════════════════

def _team_specific_hca(record: dict) -> float:
    """Derive team-specific home-court advantage from home/away record differential."""
    h_wins, h_losses = parse_record(record.get("home", "0-0"))
    a_wins, a_losses = parse_record(record.get("away", "0-0"))

    h_total = h_wins + h_losses
    a_total = a_wins + a_losses

    if h_total < 5 or a_total < 5:
        return HOME_ADVANTAGE_BASE

    diff = (h_wins / h_total) - (a_wins / a_total)
    hca = HOME_ADVANTAGE_BASE + (diff * 5.0)

    floor, ceiling = HOME_ADVANTAGE_RANGE
    return round(max(floor, min(ceiling, hca)), 2)


def _conference_matchup_adj(
    team_standings: dict, overall_record: dict, opponent_abbr: str,
) -> float:
    """
    Adjust based on how the team performs against the opponent's conference.

    If a team performs significantly better/worse against the opponent's conference
    compared to their overall record, apply a small adjustment.
    """
    opp_info = TEAM_DIVISIONS.get(opponent_abbr)
    if not opp_info:
        return 0.0

    opp_conf = opp_info["conference"]
    conf_key = OPPONENT_CONF_TO_KEY.get(opp_conf)
    if not conf_key:
        return 0.0

    vs_conf_rec = team_standings.get(conf_key, "0-0")
    vs_conf_total = record_total_games(vs_conf_rec)
    if vs_conf_total < 5:
        return 0.0

    vs_conf_wpct = record_win_pct(vs_conf_rec)
    overall_wins = overall_record.get("wins", 0)
    overall_losses = overall_record.get("losses", 0)
    overall_total = overall_wins + overall_losses
    overall_wpct = overall_wins / overall_total if overall_total > 0 else 0.5

    delta = vs_conf_wpct - overall_wpct
    return clamp(delta * CONF_MATCHUP_SCALING, -CONF_MATCHUP_CAP, CONF_MATCHUP_CAP)


def _division_matchup_adj(
    team_standings: dict, overall_record: dict, opponent_abbr: str,
) -> float:
    """
    Adjust based on how the team performs against the opponent's specific division.
    """
    opp_info = TEAM_DIVISIONS.get(opponent_abbr)
    if not opp_info:
        return 0.0

    opp_div = opp_info["division"]
    div_key = OPPONENT_DIV_TO_KEY.get(opp_div)
    if not div_key:
        return 0.0

    vs_div_rec = team_standings.get(div_key, "0-0")
    vs_div_total = record_total_games(vs_div_rec)
    if vs_div_total < DIV_MIN_GAMES:
        return 0.0

    vs_div_wpct = record_win_pct(vs_div_rec)
    overall_wins = overall_record.get("wins", 0)
    overall_losses = overall_record.get("losses", 0)
    overall_total = overall_wins + overall_losses
    overall_wpct = overall_wins / overall_total if overall_total > 0 else 0.5

    delta = vs_div_wpct - overall_wpct
    return clamp(delta * DIV_MATCHUP_SCALING, -DIV_MATCHUP_CAP, DIV_MATCHUP_CAP)


def _close_game_regression(form: dict) -> float:
    """
    Adjust for luck in close games (decided by ≤3 points).

    Expected close-game win% ≈ 50%. Teams far from 50% are experiencing luck.
    PENALIZE teams that are winning too many close games (they'll regress).
    REWARD teams that are losing too many close games (they'll improve).
    """
    close_rec = form.get("close_games", "0-0")
    close_w, close_l = parse_record(close_rec)
    close_total = close_w + close_l

    if close_total < CLOSE_GAME_MIN_GAMES:
        return 0.0

    close_wpct = close_w / close_total
    luck_amount = close_wpct - 0.50

    # Negate: being lucky (positive luck_amount) should REDUCE power score
    return clamp(-luck_amount * CLOSE_GAME_SCALING, -CLOSE_GAME_CAP, CLOSE_GAME_CAP)


def _h2h_adjustment(
    team_abbr: str, opponent_abbr: str, h2h_matrix: dict,
) -> float:
    """
    Adjust based on the season series between the two specific teams.
    """
    if not h2h_matrix:
        return 0.0

    team_h2h = h2h_matrix.get(team_abbr, {})
    h2h_rec = team_h2h.get(opponent_abbr, "")
    if not h2h_rec:
        return 0.0

    h2h_w, h2h_l = parse_record(h2h_rec)
    h2h_total = h2h_w + h2h_l

    if h2h_total < H2H_MIN_GAMES:
        return 0.0

    h2h_wpct = h2h_w / h2h_total
    delta = h2h_wpct - 0.50

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

    # 1. Home-court advantage
    if is_home:
        adjusted += _team_specific_hca(record)

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
#  Confidence label (single source — used by both engine and history)
# ═══════════════════════════════════════════════════════

def confidence_from_prob(max_prob: float) -> str:
    """
    Derive confidence label from the model's strongest win probability.

    5-tier system calibrated to NBA spread ranges:
      LOCK      ≥ 90%  (~11+ pt spread)   — near-certain
      HIGH      ≥ 80%  (~7-11 pt spread)  — strong edge
      MEDIUM    ≥ 65%  (~3.5-7 pt spread) — moderate edge
      LOW       < 65%  (below ~3.5 pts)   — slight edge
    """
    if max_prob >= LOCK_CONFIDENCE_PROB:
        return "LOCK"
    if max_prob >= HIGH_CONFIDENCE_PROB:
        return "HIGH"
    if max_prob >= MEDIUM_CONFIDENCE_PROB:
        return "MEDIUM"
    return "LOW"


# ═══════════════════════════════════════════════════════
#  Game prediction (pure model — no market data)
# ═══════════════════════════════════════════════════════

def predict_game(
    home_team: Dict,
    away_team: Dict,
    h2h_matrix: Optional[Dict] = None,
) -> Dict:
    """
    Predict a single game using only the model (no market data).

    Returns a dict with power scores, predicted spread, win probabilities,
    and confidence.
    """
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

    # Phase 1: Base power scores (including form trajectory)
    home_base = calculate_full_power_score(
        home_stats, (home_team or {}).get("form", {})
    )
    away_base = calculate_full_power_score(
        away_stats, (away_team or {}).get("form", {})
    )

    # Phase 2: Contextual adjustments
    home_power = apply_adjustments(
        base_score=home_base,
        is_home=True,
        record=(home_team or {}).get("record", {}),
        form=(home_team or {}).get("form", {}),
        b2b=(home_team or {}).get("b2b", False),
        rest_days=(home_team or {}).get("rest_days", 1),
        team_abbr=home_abbr,
        opponent_abbr=away_abbr,
        team_standings=(home_team or {}).get("standings", {}),
        h2h_matrix=h2h,
    )
    away_power = apply_adjustments(
        base_score=away_base,
        is_home=False,
        record=(away_team or {}).get("record", {}),
        form=(away_team or {}).get("form", {}),
        b2b=(away_team or {}).get("b2b", False),
        rest_days=(away_team or {}).get("rest_days", 1),
        team_abbr=away_abbr,
        opponent_abbr=home_abbr,
        team_standings=(away_team or {}).get("standings", {}),
        h2h_matrix=h2h,
    )

    # Phase 3: Spread → Probability
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
#  Pick selection (ranked by model probability)
# ═══════════════════════════════════════════════════════

def find_best_picks(
    games: List[Dict],
    min_prob: float = MIN_PICK_PROB,
) -> List[Dict]:
    """
    Select the strongest model-based picks across all games.

    For each game, picks the team with higher win probability (if above min_prob).
    Returns picks ranked by win probability (highest first).
    """
    picks = []

    for game in games:
        pred = game.get("prediction", {})
        home_prob = pred.get("home_win_prob", 0.5)
        away_prob = pred.get("away_win_prob", 0.5)

        home_info = game.get("home", {})
        away_info = game.get("away", {})

        if home_prob > away_prob and home_prob >= min_prob:
            picks.append({
                "game_id": game.get("id"),
                "selection": home_info.get("abbr", ""),
                "team_id": home_info.get("team_id", 0),
                "win_prob": round(home_prob, 4),
                "predicted_spread": pred.get("predicted_spread", 0),
                "confidence": pred.get("confidence", "LOW"),
            })
        elif away_prob > home_prob and away_prob >= min_prob:
            picks.append({
                "game_id": game.get("id"),
                "selection": away_info.get("abbr", ""),
                "team_id": away_info.get("team_id", 0),
                "win_prob": round(away_prob, 4),
                "predicted_spread": pred.get("predicted_spread", 0),
                "confidence": pred.get("confidence", "LOW"),
            })

    picks.sort(key=lambda x: x["win_prob"], reverse=True)
    return picks
