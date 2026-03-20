"""
Validate the nba_daily.json output file.
"""
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR.parent / "data" / "nba_daily.json"


def validate() -> bool:
    if not DATA_FILE.exists():
        print(f"ERROR: nba_daily.json not found at {DATA_FILE}")
        return False

    with open(DATA_FILE) as f:
        data = json.load(f)

    errors = []

    if "metadata" not in data:
        errors.append("missing metadata")
    if "games" not in data:
        errors.append("missing games key")
    elif not isinstance(data["games"], list):
        errors.append("games is not a list")

    if data.get("metadata", {}).get("status") == "ACTIVE":
        if not data.get("games"):
            errors.append("status is ACTIVE but no games found")

        lock = (data.get("picks") or {}).get("lock")
        if lock:
            for key in ("game_id", "selection", "win_prob", "reasoning"):
                if key not in lock:
                    errors.append(f"lock missing '{key}'")

    if errors:
        print("VALIDATION ERRORS:", "; ".join(errors))
        return False

    meta = data.get("metadata", {})
    games_count = len(data.get("games", []))
    print(f"OK: {games_count} games, {meta.get('picks_found', 0)} picks, "
          f"status={meta.get('status', 'UNKNOWN')}, model=v{meta.get('model_version', '?')}")
    return True


if __name__ == "__main__":
    sys.exit(0 if validate() else 1)