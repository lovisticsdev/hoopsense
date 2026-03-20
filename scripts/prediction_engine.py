"""
Prediction Engine.

Power score = weighted blend of:
  - SRS (70%) — strength-of-schedule-adjusted net rating.
  - Offensive Four Factors (15%) — eFG%, TOV%, ORB%, FT rate.
  - Defensive Four Factors (15%) — opponent eFG%, forced TOV%, DRB%, opp FT rate.

All predictions are purely model-based. No market/odds data is used.
"""
import logging
from typing import Dict, List

from config import (
    SRS_WEIGHT, OFF_FOUR_FACTORS_WEIGHT, DEF_FOUR_FACTORS_WEIGHT,
    OFF_FACTOR_WEIGHTS, DEF_FACTOR_WEIGHTS,
    HOME_ADVANTAGE_BASE, HOME_ADVANTAGE_RANGE,
    B2B_PENALTY_BASE, B2B_ROAD_EXTRA,
    HOT_STREAK_BONUS, COLD_STREAK_PENALTY,
    HOT_STREAK_THRESHOLD, COLD_STREAK_THRESHOLD,
    HIGH_CONFIDENCE_PROB, MEDIUM_CONFIDENCE_PROB, MIN_PICK_PROB,
    spread_to_prob,
)
from utils import parse_record

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


def calculate_power_score(stats: dict) -> float:
    """Team power score on a points scale. League avg ≈ 0, elite ≈ +8 to +12."""
    if not stats:
        return 0.0

    return round(
        SRS_WEIGHT * stats.get("srs", 0.0)
        + OFF_FOUR_FACTORS_WEIGHT * _offensive_four_factors(stats)
        + DEF_FOUR_FACTORS_WEIGHT * _defensive_four_factors(stats),
        3,
    )


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


def _form_adjustment(form: dict) -> float:
    """Adjust power score based on recent monthly form."""
    wins, losses = parse_record(form.get("recent_record", "0-0"))
    total = wins + losses

    if total < 3:
        return 0.0

    win_rate_10 = (wins / total) * 10.0

    if win_rate_10 >= HOT_STREAK_THRESHOLD:
        return HOT_STREAK_BONUS
    if win_rate_10 <= COLD_STREAK_THRESHOLD:
        return COLD_STREAK_PENALTY
    return 0.0


def apply_adjustments(
    base_score: float,
    is_home: bool,
    record: dict,
    form: dict,
    b2b: bool,
    rest_days: int,
) -> float:
    """Apply all contextual adjustments to a base power score."""
    adjusted = base_score

    if is_home:
        adjusted += _team_specific_hca(record)

    if b2b or rest_days == 0:
        adjusted += B2B_PENALTY_BASE
        if not is_home:
            adjusted += B2B_ROAD_EXTRA

    adjusted += _form_adjustment(form)
    return round(adjusted, 3)


# ═══════════════════════════════════════════════════════
#  Game prediction (pure model — no market data)
# ═══════════════════════════════════════════════════════

def _confidence_from_prob(max_prob: float) -> str:
    """Derive confidence label from the model's strongest win probability."""
    if max_prob >= HIGH_CONFIDENCE_PROB:
        return "HIGH"
    if max_prob >= MEDIUM_CONFIDENCE_PROB:
        return "MEDIUM"
    return "LOW"


def predict_game(home_team: Dict, away_team: Dict) -> Dict:
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

    home_power = apply_adjustments(
        base_score=calculate_power_score(home_stats),
        is_home=True,
        record=(home_team or {}).get("record", {}),
        form=(home_team or {}).get("form", {}),
        b2b=(home_team or {}).get("b2b", False),
        rest_days=(home_team or {}).get("rest_days", 1),
    )
    away_power = apply_adjustments(
        base_score=calculate_power_score(away_stats),
        is_home=False,
        record=(away_team or {}).get("record", {}),
        form=(away_team or {}).get("form", {}),
        b2b=(away_team or {}).get("b2b", False),
        rest_days=(away_team or {}).get("rest_days", 1),
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
        "confidence": _confidence_from_prob(max(home_win_prob, away_win_prob)),
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