"""
Schema validation for nba_daily.json output.

Single source of truth — used by both the pipeline (generate_picks.py)
and the standalone validator (validate_output.py).
"""
import json
import logging
from pathlib import Path
from typing import List

from config import confidence_from_prob

logger = logging.getLogger(__name__)


def validate_daily_json(data: dict) -> List[str]:
    """
    Validate the structure and consistency of a daily JSON payload.
    Returns a list of error strings. Empty list = valid.
    """
    errors: List[str] = []

    if "metadata" not in data:
        errors.append("missing 'metadata'")
    if "games" not in data:
        errors.append("missing 'games'")
    elif not isinstance(data["games"], list):
        errors.append("'games' is not a list")

    meta = data.get("metadata", {})

    game_ids = set()
    games_list = data.get("games", [])
    if not isinstance(games_list, list):
        games_list = []

    for i, game in enumerate(games_list):
        for key in ("id", "start_time", "status", "home", "away"):
            if key not in game:
                errors.append(f"game[{i}] missing '{key}'")

        if "id" in game:
            game_ids.add(game["id"])

        pred = game.get("prediction", {})
        if pred:
            for prob_key in ("home_win_prob", "away_win_prob"):
                prob = pred.get(prob_key, -1)
                if not isinstance(prob, (int, float)) or not (0.0 <= prob <= 1.0):
                    errors.append(f"game[{i}] {prob_key}={prob} outside [0.0, 1.0]")

            home_p = pred.get("home_win_prob", 0)
            away_p = pred.get("away_win_prob", 0)
            if isinstance(home_p, (int, float)) and isinstance(away_p, (int, float)):
                if abs((home_p + away_p) - 1.0) > 0.01:
                    errors.append(
                        f"game[{i}] probabilities sum to {home_p + away_p:.4f} (expected ~1.0)"
                    )

    # Picks validation (only if ACTIVE status)
    if meta.get("status") == "ACTIVE":
        if not data.get("games"):
            errors.append("status is ACTIVE but no games found")

        picks = data.get("picks") or {}
        _validate_pick_object(picks.get("lock"), "lock", game_ids, errors)
        for i, premium_pick in enumerate(picks.get("premium", [])):
            _validate_pick_object(premium_pick, f"premium[{i}]", game_ids, errors)

    return errors


def _validate_pick_object(
    pick: dict | None,
    label: str,
    valid_game_ids: set,
    errors: List[str],
) -> None:
    if pick is None:
        return

    for key in ("game_id", "selection", "win_prob", "confidence"):
        if key not in pick:
            errors.append(f"{label} missing '{key}'")

    prob = pick.get("win_prob", -1)
    if isinstance(prob, (int, float)) and not (0.0 <= prob <= 1.0):
        errors.append(f"{label} win_prob={prob} outside [0.0, 1.0]")

    game_id = pick.get("game_id")
    if game_id is not None and valid_game_ids and game_id not in valid_game_ids:
        errors.append(f"{label} references game_id='{game_id}' not in games list")

    if isinstance(prob, (int, float)) and 0.0 <= prob <= 1.0:
        expected = confidence_from_prob(prob)
        actual = pick.get("confidence", "")
        if actual and actual != expected:
            errors.append(
                f"{label} confidence='{actual}' but prob={prob} expects '{expected}'"
            )


def validate_file(filepath: Path) -> bool:
    """Load and validate a JSON file. Prints results and returns True if valid."""
    if not filepath.exists():
        print(f"ERROR: {filepath.name} not found at {filepath}")
        return False

    try:
        with open(filepath) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: {filepath.name} is not valid JSON: {e}")
        return False

    errors = validate_daily_json(data)
    if errors:
        print(f"VALIDATION ERRORS: {'; '.join(errors)}")
        return False

    meta = data.get("metadata", {})
    print(f"OK: {len(data.get('games', []))} games, {meta.get('picks_found', 0)} picks, "
          f"status={meta.get('status', 'UNKNOWN')}, model=v{meta.get('model_version', '?')}")
    return True
