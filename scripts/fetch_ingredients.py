"""
Fetch team stats and game schedule.

Sources:
  - Basketball-Reference: Advanced stats (Four Factors, SRS, ratings)
                          and Expanded Standings (records, form, margins).
  - balldontlie.io (BDL): Today's schedule and yesterday's games (B2B detection).
"""
import os
import time
import random
import logging
import requests
import pandas as pd
import io
import cloudscraper
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Set, Optional

from config import (
    NBA_TEAMS, ABBR_TO_ID, CURRENT_SEASON, DATA_DIR, EASTERN_CONFERENCE,
)
from utils import resolve_team_by_name, get_abbr, write_json_atomic, read_json_safe

logger = logging.getLogger(__name__)

BASE_URL = "https://api.balldontlie.io"
CACHE_FILE = DATA_DIR / "nba_raw_stats_cache.json"
REQUEST_DELAY = 1.0


# ═══════════════════════════════════════════════════════
#  B-Ref scraping infrastructure
# ═══════════════════════════════════════════════════════

_BREF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}


def _create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )
    scraper.headers.update(_BREF_HEADERS)
    return scraper


def _strip_comments(html: str) -> str:
    """B-Ref hides tables inside HTML comments."""
    return html.replace("<!--", "").replace("-->", "")


def _flatten_multi_columns(
    df: pd.DataFrame,
    prefix_map: Optional[Dict[str, str]] = None,
    passthrough_groups: Optional[Set[str]] = None,
) -> pd.DataFrame:
    """
    Flatten a MultiIndex-column DataFrame.

    Args:
        prefix_map: Maps top-level substring → prefix to prepend to bottom-level name.
        passthrough_groups: Set of top-level substrings that should use the bottom
                            name as-is (no prefix).
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    passthrough = passthrough_groups or set()
    new_cols = []

    for levels in df.columns:
        top = str(levels[0]).strip()
        bottom = str(levels[-1]).strip()

        if any(g in top for g in passthrough):
            new_cols.append(bottom)
            continue

        if prefix_map:
            matched = False
            for key, prefix in prefix_map.items():
                if key in top:
                    new_cols.append(prefix + bottom)
                    matched = True
                    break
            if matched:
                continue

        new_cols.append(bottom if bottom and bottom != top else top)

    df.columns = new_cols
    return df


def _fetch_bref_page(url: str, scraper, max_attempts: int = 4) -> str:
    """Fetch a B-Ref page with exponential backoff + jitter."""
    for attempt in range(1, max_attempts + 1):
        delay = (2 ** attempt) + random.uniform(0, 2)
        time.sleep(delay)
        try:
            resp = scraper.get(url, timeout=30)
            if resp.status_code in (429, 403) and attempt < max_attempts:
                wait = delay * 3
                logger.warning(f"B-Ref {resp.status_code} on attempt {attempt}, retrying in {wait:.0f}s…")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return _strip_comments(resp.text)
        except requests.RequestException as e:
            if attempt == max_attempts:
                raise
            logger.warning(f"B-Ref request failed (attempt {attempt}): {e}")

    raise RuntimeError(f"Failed to fetch {url} after {max_attempts} attempts")


def _safe_float(row, col: str, default: float) -> float:
    """Safely extract a float from a DataFrame row."""
    try:
        val = row.get(col, default)
        return round(float(val), 4) if pd.notna(val) else round(default, 4)
    except (ValueError, TypeError):
        return round(default, 4)


# ═══════════════════════════════════════════════════════
#  B-Ref parsers
# ═══════════════════════════════════════════════════════

def parse_advanced_stats(html_content: str) -> Dict[int, dict]:
    """Parse the Advanced Stats table → per-team Four Factors + ratings + SRS."""
    logger.info("Parsing Advanced Stats from Basketball-Reference…")
    try:
        tables = pd.read_html(io.StringIO(html_content), match="Advanced")
        df = tables[0]
        df = _flatten_multi_columns(df, prefix_map={"Offense": "Off_", "Defense": "Def_"})
        df = df[df["Team"] != "League Average"]

        stats_dict: Dict[int, dict] = {}
        for _, row in df.iterrows():
            team_id = resolve_team_by_name(str(row["Team"]))
            if not team_id:
                continue

            stats_dict[team_id] = {
                "efg_pct": _safe_float(row, "Off_eFG%", 0.500),
                "tov_pct": _safe_float(row, "Off_TOV%", 14.0) / 100.0,
                "orb_pct": _safe_float(row, "Off_ORB%", 25.0) / 100.0,
                "ft_rate": _safe_float(row, "Off_FT/FGA", 0.250),
                "opp_efg_pct": _safe_float(row, "Def_eFG%", 0.500),
                "opp_tov_pct": _safe_float(row, "Def_TOV%", 14.0) / 100.0,
                "drb_pct": 1.0 - (_safe_float(row, "Def_ORB%", 25.0) / 100.0),
                "opp_ft_rate": _safe_float(row, "Def_FT/FGA", 0.250),
                "off_rating": _safe_float(row, "ORtg", 110.0),
                "def_rating": _safe_float(row, "DRtg", 110.0),
                "pace": _safe_float(row, "Pace", 99.0),
                "srs": _safe_float(row, "SRS", 0.0),
            }

        logger.info(f"Parsed advanced stats for {len(stats_dict)} teams.")
        return stats_dict

    except Exception as e:
        logger.error(f"CRITICAL: Advanced Stats parse failed: {e}")
        return {}


def parse_expanded_standings(html_content: str) -> Dict[int, dict]:
    """Parse Expanded Standings → records, home/away, conference, margins, form."""
    logger.info("Parsing Expanded Standings…")
    try:
        tables = pd.read_html(io.StringIO(html_content), match="Expanded Standings")
        if not tables:
            logger.warning("No Expanded Standings table found.")
            return {}

        df = tables[0]
        df = _flatten_multi_columns(
            df,
            prefix_map={
                "Conference": "Conf_",
                "Division": "Div_",
                "All-Star": "AS_",
                "Margin": "Margin_",
                "Month": "Mo_",
            },
            passthrough_groups={"Place", "Unnamed", "Expanded"},
        )

        logger.debug(f"Expanded Standings columns: {list(df.columns)}")

        result: Dict[int, dict] = {}
        for _, row in df.iterrows():
            team_raw = str(row.get("Team", row.iloc[1] if len(row) > 1 else ""))
            team_id = resolve_team_by_name(team_raw)
            if not team_id:
                continue

            overall = str(row.get("Overall", "0-0"))
            parts = overall.split("-")
            wins = int(parts[0]) if len(parts) >= 2 else 0
            losses = int(parts[1]) if len(parts) >= 2 else 0

            home_rec = str(row.get("Home", "0-0"))
            road_rec = str(row.get("Road", "0-0"))

            conf_e = str(row.get("Conf_E", "0-0"))
            conf_w = str(row.get("Conf_W", "0-0"))
            abbr = get_abbr(team_id)
            conf_rec = conf_e if abbr in EASTERN_CONFERENCE else conf_w

            margin_close = str(row.get("Margin_≤3", row.get("Margin_\u22643", "0-0")))
            margin_blow = str(row.get("Margin_≥10", row.get("Margin_\u226510", "0-0")))

            recent_month = "0-0"
            for mo in reversed(["Mo_Apr", "Mo_Mar", "Mo_Feb", "Mo_Jan",
                                "Mo_Dec", "Mo_Nov", "Mo_Oct"]):
                val = str(row.get(mo, ""))
                if val and val != "nan" and val != "0-0":
                    recent_month = val
                    break

            result[team_id] = {
                "wins": wins,
                "losses": losses,
                "home": home_rec,
                "away": road_rec,
                "conf": conf_rec,
                "close_games": margin_close,
                "blowouts": margin_blow,
                "recent_record": recent_month,
            }

        logger.info(f"Parsed expanded standings for {len(result)} teams.")
        return result

    except Exception as e:
        logger.warning(f"Expanded standings parse failed (non-fatal): {e}")
        return {}


# ═══════════════════════════════════════════════════════
#  B-Ref orchestrator
# ═══════════════════════════════════════════════════════

def fetch_all_bref_data(season_str: str) -> Tuple[Dict[int, dict], Dict[int, dict]]:
    """Fetch all B-Ref data with exactly 2 HTTP requests."""
    year = int(season_str.split("-")[0]) + 1
    scraper = _create_scraper()

    main_url = f"https://www.basketball-reference.com/leagues/NBA_{year}.html"
    logger.info(f"Fetching B-Ref main page: {main_url}")
    main_html = _fetch_bref_page(main_url, scraper)
    bref_stats = parse_advanced_stats(main_html)

    standings_url = f"https://www.basketball-reference.com/leagues/NBA_{year}_standings.html"
    logger.info(f"Fetching B-Ref standings page: {standings_url}")
    try:
        standings_html = _fetch_bref_page(standings_url, scraper)
        expanded = parse_expanded_standings(standings_html)
    except Exception as e:
        logger.warning(f"Standings page fetch failed: {e}")
        expanded = {}

    return bref_stats, expanded


# ═══════════════════════════════════════════════════════
#  BDL API — schedule & fatigue
# ═══════════════════════════════════════════════════════

def _get_api_key() -> str:
    key = os.getenv("BDL_API_KEY", "")
    if not key:
        logger.error("BDL_API_KEY not set!")
    return key


def _api_get(endpoint: str, params: dict = None, max_retries: int = 3) -> dict:
    api_key = _get_api_key()
    if not api_key:
        return {}
    headers = {"Authorization": api_key}
    url = f"{BASE_URL}{endpoint}"

    for attempt in range(max_retries):
        try:
            time.sleep(REQUEST_DELAY)
            response = requests.get(url, headers=headers, params=params, timeout=15)
            if response.status_code == 429:
                wait = 15 * (attempt + 1)
                logger.warning(f"BDL 429, waiting {wait}s…")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                logger.error(f"BDL API failed after {max_retries} attempts: {e}")
                return {}
    return {}


def _find_nba_team_id(team: dict) -> int:
    """Map a BDL team dict → internal ID via abbreviation."""
    return ABBR_TO_ID.get(team.get("abbreviation", ""), 0)


def fetch_schedule_and_fatigue(season: int) -> Tuple[List[Dict], Set[int]]:
    """Fetch yesterday's and today's games from BDL for B2B detection + schedule."""
    logger.info("Fetching schedule (yesterday + today) from BDL…")
    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)

    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    result = _api_get("/nba/v1/games", {
        "dates[]": [yesterday_str, today_str],
        "seasons[]": season,
    })

    yesterdays_teams: Set[int] = set()
    todays_games: List[Dict] = []

    for game in result.get("data", []):
        game_date = game.get("date", "")
        home_id = _find_nba_team_id(game.get("home_team", {}))
        away_id = _find_nba_team_id(game.get("visitor_team", {}))

        if not home_id or not away_id:
            continue

        if game_date.startswith(yesterday_str):
            yesterdays_teams.add(home_id)
            yesterdays_teams.add(away_id)
        elif game_date.startswith(today_str):
            todays_games.append({
                "id": str(game.get("id")),
                "start_time": game.get("datetime", game_date),
                "status": game.get("status", "SCHEDULED"),
                "home_team_id": home_id,
                "away_team_id": away_id,
            })

    logger.info(f"Schedule: {len(todays_games)} games today, "
                f"{len(yesterdays_teams)} teams on B2B.")
    return todays_games, yesterdays_teams


# ═══════════════════════════════════════════════════════
#  Main orchestrator
# ═══════════════════════════════════════════════════════

def fetch_all_ingredients(season: str = CURRENT_SEASON, force_refresh: bool = False) -> Dict:
    """Assemble all raw data into a single dict ready for the prediction engine."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    season_year = int(season.split("-")[0])

    if not force_refresh:
        cached = read_json_safe(CACHE_FILE)
        if cached and cached.get("cache_date") == today_str:
            logger.info("Using cached data from today.")
            return cached

    bref_stats, bref_standings = fetch_all_bref_data(season)

    if not bref_stats or len(bref_stats) < 30:
        raise RuntimeError(
            f"FAIL FAST: Only got advanced stats for {len(bref_stats)} teams (need 30). "
            "Basketball-Reference may be blocking or the page structure changed."
        )

    if len(bref_standings) < 30:
        logger.warning(f"Only got standings for {len(bref_standings)} teams "
                       "— continuing with available data.")

    todays_games, yesterdays_teams = fetch_schedule_and_fatigue(season_year)

    teams: Dict[str, dict] = {}
    for team_id, team_info in NBA_TEAMS.items():
        raw_stats = bref_stats.get(team_id)
        exp = bref_standings.get(team_id, {})

        teams[str(team_id)] = {
            "id": team_id,
            "abbr": team_info["abbr"],
            "name": team_info["name"],
            "stats": raw_stats,
            "b2b": team_id in yesterdays_teams,
            "rest_days": 0 if team_id in yesterdays_teams else 1,
            "record": {
                "wins": exp.get("wins", 0),
                "losses": exp.get("losses", 0),
                "home": exp.get("home", "0-0"),
                "away": exp.get("away", "0-0"),
                "conf": exp.get("conf", "0-0"),
            },
            "form": {
                "recent_record": exp.get("recent_record", "0-0"),
                "close_games": exp.get("close_games", "0-0"),
                "blowouts": exp.get("blowouts", "0-0"),
            },
        }

    final_data = {
        "cache_date": today_str,
        "teams": teams,
        "games": todays_games,
    }

    try:
        write_json_atomic(final_data, CACHE_FILE)
        logger.info(f"Cached to {CACHE_FILE.name}")
    except Exception as e:
        logger.warning(f"Failed to write cache: {e}")

    return final_data