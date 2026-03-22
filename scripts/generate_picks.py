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
MODEL_VERSION = "4.0"


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
        for key in ("game_id", "selection", "win_prob"):
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
    game: Dict, home_team: Dict, away_team: Dict, h2h_matrix: Dict,
) -> Dict:
    """Build a game object with embedded model prediction."""
    prediction = predict_game(home_team, away_team, h2h_matrix=h2h_matrix)

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


def _build_pick(pick: dict, game_info: dict) -> Dict:
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
        "start_time": game_info.get("start_time", ""),
    }


# ═══════════════════════════════════════════════════════
#  Main pipeline
# ═══════════════════════════════════════════════════════

def generate_daily_json(force_refresh: bool = False) -> Dict:
    logger.info("═══ HOOPSENSE v4 DAILY GENERATION START ═══")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Step 1: Fetch all team data
    nba_data = fetch_all_ingredients(force_refresh=force_refresh)
    teams = nba_data["teams"]
    games_schedule = nba_data["games"]
    h2h_matrix = nba_data.get("h2h_matrix", {})

    # Step 2: Update history and grade past picks
    history_data = update_and_get_history(teams, h2h_matrix)

    # Step 3: Handle no-games days
    if not games_schedule:
        daily_data = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "season": CURRENT_SEASON,
                "status": "NO_GAMES",
                "model_version": MODEL_VERSION,
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
            merged_game = _build_game_object(game, home_team, away_team, h2h_matrix)
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
        lock = _build_pick(best_picks[0], lock_info)

        for pick in best_picks[1:]:
            p_info = game_lookup.get(pick["game_id"], {})
            premium.append(_build_pick(pick, p_info))

    picks = {"date": today, "lock": lock, "premium": premium}

    # Step 7: Assemble final output
    daily_data = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "season": CURRENT_SEASON,
            "status": "ACTIVE",
            "model_version": MODEL_VERSION,
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
