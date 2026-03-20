"""
Main orchestrator: generate the daily nba_daily.json file.

Pipeline: fetch stats → predict games → select picks → write JSON.
"""
import sys
import logging
from datetime import datetime, timezone
from typing import Dict, List

from fetch_ingredients import fetch_all_ingredients
from prediction_engine import predict_game, find_best_picks
from history_manager import update_and_get_history
from config import DATA_DIR, CURRENT_SEASON
from utils import setup_logging, write_json_atomic

logger = logging.getLogger(__name__)

OUTPUT_FILE = DATA_DIR / "nba_daily.json"


# ═══════════════════════════════════════════════════════
#  Reasoning generator
# ═══════════════════════════════════════════════════════

def _generate_reasoning(pick: dict, teams: dict, game_info: dict) -> str:
    """
    Generate human-readable reasoning for a pick.
    Covers: team record, opponent context, key stats, form, fatigue.
    """
    team = teams.get(str(pick["team_id"]), {})
    record = team.get("record", {})
    form = team.get("form", {})
    stats = team.get("stats", {})

    selection = pick["selection"]
    win_prob = pick["win_prob"]
    confidence = pick.get("confidence", "MEDIUM")
    wins = record.get("wins", 0)
    losses = record.get("losses", 0)

    # Identify opponent
    home = game_info.get("home", {})
    away = game_info.get("away", {})
    is_home_pick = selection == home.get("abbr", "")
    opp = away if is_home_pick else home
    opp_abbr = opp.get("abbr", "")
    opp_team = teams.get(str(opp.get("team_id", "")), {})
    opp_record = opp_team.get("record", {})

    parts = [
        f"{selection} ({wins}-{losses}) — model gives them a "
        f"{win_prob:.0%} win probability.",

        f"Opponent: {opp_abbr} "
        f"({opp_record.get('wins', 0)}-{opp_record.get('losses', 0)}).",
    ]

    if stats:
        net_rtg = round(stats.get("off_rating", 0) - stats.get("def_rating", 0), 1)
        srs = stats.get("srs", 0.0)
        parts.append(f"SRS: {srs:+}, Net Rtg: {net_rtg:+}.")

    recent = form.get("recent_record", "")
    if recent and recent != "0-0":
        parts.append(f"Recent form: {recent}.")

    if team.get("b2b"):
        parts.append("Note: on a back-to-back (fatigue adjusted).")

    opp_stats = opp_team.get("stats", {})
    if opp_stats:
        opp_net = round(opp_stats.get("off_rating", 0) - opp_stats.get("def_rating", 0), 1)
        if opp_net < -3:
            parts.append(f"{opp_abbr} has a poor net rating ({opp_net:+}).")

    parts.append(f"Confidence: {confidence}.")

    return " ".join(parts)


# ═══════════════════════════════════════════════════════
#  Schema validation
# ═══════════════════════════════════════════════════════

def _validate_daily_json(data: dict) -> bool:
    """Basic structural validation of the output JSON."""
    errors = []

    if "metadata" not in data:
        errors.append("missing 'metadata'")
    if "games" not in data:
        errors.append("missing 'games'")
    elif not isinstance(data["games"], list):
        errors.append("'games' is not a list")
    else:
        for game in data["games"]:
            for key in ("id", "home", "away"):
                if key not in game:
                    errors.append(f"game missing '{key}'")

    picks = data.get("picks")
    if picks and picks.get("lock"):
        for key in ("game_id", "selection", "win_prob", "reasoning"):
            if key not in picks["lock"]:
                errors.append(f"lock missing '{key}'")

    if errors:
        logger.error(f"Validation errors: {'; '.join(errors)}")
        return False
    return True


# ═══════════════════════════════════════════════════════
#  Game object builder
# ═══════════════════════════════════════════════════════

def _build_game_object(
    game: Dict, home_team: Dict, away_team: Dict
) -> Dict:
    """Build a game object with embedded model prediction."""
    prediction = predict_game(home_team, away_team)

    return {
        "id": game["id"],
        "start_time": game.get("start_time", ""),
        "status": game.get("status", "SCHEDULED"),
        "home": {
            "team_id": game["home_team_id"],
            "abbr": home_team.get("abbr", ""),
            "name": home_team.get("name", ""),
        },
        "away": {
            "team_id": game["away_team_id"],
            "abbr": away_team.get("abbr", ""),
            "name": away_team.get("name", ""),
        },
        "prediction": {
            "home_win_prob": prediction["home_win_prob"],
            "away_win_prob": prediction["away_win_prob"],
            "predicted_spread": prediction["predicted_spread"],
            "confidence": prediction["confidence"],
        },
    }


def _build_pick(pick: dict, teams: dict, game_info: dict) -> Dict:
    """Build a single pick object."""
    home = game_info.get("home", {})
    away = game_info.get("away", {})
    return {
        "game_id": pick["game_id"],
        "away_abbr": away.get("abbr", ""),
        "home_abbr": home.get("abbr", ""),
        "selection": pick["selection"],
        "win_prob": pick["win_prob"],
        "confidence": pick["confidence"],
        "reasoning": _generate_reasoning(pick, teams, game_info),
    }


# ═══════════════════════════════════════════════════════
#  Main pipeline
# ═══════════════════════════════════════════════════════

def generate_daily_json(force_refresh: bool = False) -> Dict:
    logger.info("═══ HOOPSENSE DAILY GENERATION START ═══")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Step 1: Fetch all team data
    nba_data = fetch_all_ingredients(force_refresh=force_refresh)
    teams = nba_data["teams"]
    games_schedule = nba_data["games"]

    # Step 2: Update history and grade past picks
    history_data = update_and_get_history(teams)

    # Step 3: Handle no-games days
    if not games_schedule:
        daily_data = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "season": CURRENT_SEASON,
                "status": "NO_GAMES",
                "model_version": "3.0",
            },
            "games": [],
            "picks": None,
            "history": history_data,
        }
        write_json_atomic(daily_data, OUTPUT_FILE)
        logger.info("No games today. Wrote empty daily file.")
        return daily_data

    # Step 4: Build game objects with predictions
    games: List[Dict] = []
    seen_game_ids = set()

    for game in games_schedule:
        game_id = game["id"]
        if game_id in seen_game_ids:
            continue
        seen_game_ids.add(game_id)

        home_team = teams.get(str(game["home_team_id"]), {})
        away_team = teams.get(str(game["away_team_id"]), {})

        try:
            merged_game = _build_game_object(game, home_team, away_team)
            games.append(merged_game)
        except ValueError as e:
            logger.warning(f"Skipping game {game_id}: {e}")

    # Step 5: Find best picks from model predictions
    best_picks = find_best_picks(games)
    game_lookup = {g["id"]: g for g in games}

    # Step 6: Build picks payload
    lock = None
    premium = []

    if best_picks:
        lock_info = game_lookup.get(best_picks[0]["game_id"], {})
        lock = _build_pick(best_picks[0], teams, lock_info)

        for pick in best_picks[1:4]:
            p_info = game_lookup.get(pick["game_id"], {})
            premium.append(_build_pick(pick, teams, p_info))

    picks = {"date": today, "lock": lock, "premium": premium}

    # Step 7: Assemble final output
    daily_data = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "season": CURRENT_SEASON,
            "status": "ACTIVE",
            "model_version": "3.0",
            "games_count": len(games),
            "picks_found": len(best_picks),
        },
        "games": games,
        "picks": picks,
        "history": history_data,
    }

    # Step 8: Validate and write
    if not _validate_daily_json(daily_data):
        logger.error("JSON validation failed — writing anyway but check the output.")

    write_json_atomic(daily_data, OUTPUT_FILE)
    logger.info(f"═══ COMPLETE: {len(games)} games, {len(best_picks)} picks ═══")
    return daily_data


if __name__ == "__main__":
    setup_logging()
    force_run = "--force" in sys.argv
    generate_daily_json(force_refresh=force_run)