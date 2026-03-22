"""
History manager: grade past picks, maintain a 5-day rolling history, backfill gaps.
"""
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fetch_ingredients import _api_get
from prediction_engine import predict_game, confidence_from_prob
from config import DATA_DIR, MIN_PICK_PROB, PICK_COUNT
from utils import write_json_atomic, read_json_safe

logger = logging.getLogger(__name__)

HISTORY_FILE = DATA_DIR / "history_slips.json"
DAILY_FILE = DATA_DIR / "nba_daily.json"

HISTORY_API_DELAY = 3.0
HISTORY_WINDOW_DAYS = 10


# ═══════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════

def _get_all_picks(slip: dict) -> List[dict]:
    """Extract all pick objects from a slip (lock + premium)."""
    picks = []
    if slip.get("lock"):
        picks.append(slip["lock"])
    picks.extend(slip.get("premium", []))
    return picks


def _last_n_dates(n: int) -> List[str]:
    """Return the last N date strings (yesterday through N days ago)."""
    return [
        (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(1, n + 1)
    ]


def _fetch_games_for_date(date_str: str) -> list:
    """Fetch games from BDL with rate-limit-friendly delay + jitter."""
    time.sleep(HISTORY_API_DELAY + random.uniform(0.5, 2.0))
    result = _api_get("/nba/v1/games", {"dates[]": date_str})
    games = result.get("data", [])
    if not games:
        logger.warning(f"BDL returned no games for {date_str} "
                       "(may be off-day or rate-limited)")
    return games


def _build_abbr_lookup(teams: dict) -> Dict[str, dict]:
    """Build abbr → team dict for O(1) lookups during backfill."""
    return {t.get("abbr", ""): t for t in teams.values() if t.get("abbr")}


# ═══════════════════════════════════════════════════════
#  Grading
# ═══════════════════════════════════════════════════════

def _grade_pick(pick: dict, results_map: dict) -> None:
    """Grade a single pick in-place against final game results."""
    if pick.get("status") in ("WIN", "LOSS"):
        return

    game_id = str(pick.get("game_id"))
    if game_id not in results_map:
        return

    game = results_map[game_id]
    home_score = game.get("home_team_score", 0)
    away_score = game.get("visitor_team_score", 0)

    if home_score == 0 and away_score == 0:
        return

    home_abbr = pick.get("home_abbr",
                         game.get("home_team", {}).get("abbreviation", ""))
    away_abbr = pick.get("away_abbr",
                         game.get("visitor_team", {}).get("abbreviation", ""))

    actual_winner = home_abbr if home_score > away_score else away_abbr
    pick["status"] = "WIN" if pick["selection"] == actual_winner else "LOSS"


def _grade_slip(slip: dict, date_str: str) -> None:
    """Grade all picks in a slip for a given date."""
    all_picks = _get_all_picks(slip)
    if all(p.get("status") in ("WIN", "LOSS") for p in all_picks):
        return

    logger.info(f"Grading picks for {date_str}…")
    games_data = _fetch_games_for_date(date_str)

    if not games_data:
        logger.warning(f"No API data for {date_str} — keeping existing statuses")
        return

    results_map = {
        str(g["id"]): g
        for g in games_data
        if g.get("status") == "Final"
    }

    if not results_map:
        logger.info(f"Games for {date_str} not yet Final — keeping PENDING")
        return

    # Backfill start_time for picks that lack it
    all_results = {str(g["id"]): g for g in games_data}
    for pick in all_picks:
        if not pick.get("start_time"):
            gid = str(pick.get("game_id"))
            g = all_results.get(gid)
            if g:
                pick["start_time"] = g.get("datetime", g.get("date", ""))
        _grade_pick(pick, results_map)


# ═══════════════════════════════════════════════════════
#  Backfill (generate picks for missing dates)
# ═══════════════════════════════════════════════════════

def _generate_historical_picks(
    date_str: str,
    abbr_lookup: Dict[str, dict],
    h2h_matrix: dict,
) -> Optional[dict]:
    """
    Generate picks for a past date using the model.
    Uses current team stats to retroactively pick winners.
    """
    games_data = _fetch_games_for_date(date_str)
    if not games_data:
        return None

    candidates = []
    for game in games_data:
        home_abbr = game.get("home_team", {}).get("abbreviation", "")
        away_abbr = game.get("visitor_team", {}).get("abbreviation", "")
        home_team = abbr_lookup.get(home_abbr)
        away_team = abbr_lookup.get(away_abbr)

        if not home_team or not away_team:
            continue

        try:
            prediction = predict_game(home_team, away_team, h2h_matrix=h2h_matrix)
        except ValueError as e:
            logger.warning(f"Skipping backfill game {game.get('id')} "
                           f"({away_abbr}@{home_abbr}): {e}")
            continue

        if prediction["home_win_prob"] > prediction["away_win_prob"]:
            selection, prob = home_abbr, prediction["home_win_prob"]
        else:
            selection, prob = away_abbr, prediction["away_win_prob"]

        if prob < MIN_PICK_PROB:
            continue

        candidates.append({
            "game_id": str(game["id"]),
            "away_abbr": away_abbr,
            "home_abbr": home_abbr,
            "selection": selection,
            "win_prob": round(prob, 4),
            "confidence": confidence_from_prob(prob),
            "status": "PENDING",
            "start_time": game.get("datetime", game.get("date", "")),
        })

    candidates.sort(key=lambda x: x["win_prob"], reverse=True)
    candidates = candidates[:PICK_COUNT]

    if not candidates:
        return None

    return {
        "date": date_str,
        "lock": candidates[0],
        "premium": candidates[1:],
    }


# ═══════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════

def update_and_get_history(teams: dict, h2h_matrix: dict = None) -> dict:
    """
    1. Load existing history.
    2. Archive today's daily picks (if they exist).
    3. Backfill any missing days in the last 5.
    4. Grade all ungraded picks.
    5. Return the history payload for the daily JSON.

    Stats are computed client-side from the displayed slips.
    """
    h2h = h2h_matrix or {}
    history_data: dict = read_json_safe(HISTORY_FILE, default={})

    # Archive current daily picks into history
    daily_data = read_json_safe(DAILY_FILE)
    if daily_data:
        picks = daily_data.get("picks")
        if picks and picks.get("date") and picks["date"] not in history_data:
            history_data[picks["date"]] = picks

    dates = _last_n_dates(HISTORY_WINDOW_DAYS)
    abbr_lookup = _build_abbr_lookup(teams)

    # Backfill missing dates
    for date_str in dates:
        if date_str not in history_data:
            logger.info(f"Backfilling history for {date_str}…")
            slip = _generate_historical_picks(date_str, abbr_lookup, h2h)
            if slip:
                history_data[date_str] = slip
            else:
                logger.warning(f"No games for {date_str} — skipping")

    # Grade all slips
    for date_str in sorted(history_data.keys()):
        _grade_slip(history_data[date_str], date_str)

    write_json_atomic(history_data, HISTORY_FILE)

    past_slips = [history_data[d] for d in dates if d in history_data]

    return {
        "past_slips": past_slips,
    }
