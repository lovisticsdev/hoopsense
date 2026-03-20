"""
Fetch team stats and game schedule.

Sources:
  - Basketball-Reference: Advanced stats (Four Factors, SRS, Pythagorean, ratings),
                          Expanded Standings (records, form, margins, conference/division),
                          and Team vs. Team head-to-head matrix.
  - balldontlie.io (BDL): Today's schedule, yesterday's games (B2B detection),
                           and recent game results (last-10 rolling form).
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
    NBA_TEAMS, ABBR_TO_ID, CURRENT_SEASON, DATA_DIR,
    EASTERN_CONFERENCE, BREF_ABBR_MAP,
)
from utils import (
    resolve_team_by_name, get_abbr, write_json_atomic, read_json_safe,
    parse_record,
)

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


def _safe_int(row, col: str, default: int) -> int:
    """Safely extract an int from a DataFrame row."""
    try:
        val = row.get(col, default)
        return int(float(val)) if pd.notna(val) else default
    except (ValueError, TypeError):
        return default


def _normalize_bref_abbr(abbr: str) -> str:
    """Convert a B-Ref abbreviation to our internal abbreviation."""
    return BREF_ABBR_MAP.get(abbr.strip(), abbr.strip())


# ═══════════════════════════════════════════════════════
#  B-Ref parsers
# ═══════════════════════════════════════════════════════

def parse_advanced_stats(html_content: str) -> Dict[int, dict]:
    """
    Parse the Advanced Stats table → per-team stats including:
    SRS, PW, PL, MOV, SOS, NRtg, Four Factors, ORtg, DRtg, Pace, TS%.
    """
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
                # ── Core metrics (v4: now extracted) ──
                "wins": _safe_int(row, "W", 0),
                "losses": _safe_int(row, "L", 0),
                "pyth_wins": _safe_int(row, "PW", 0),
                "pyth_losses": _safe_int(row, "PL", 0),
                "mov": _safe_float(row, "MOV", 0.0),
                "sos": _safe_float(row, "SOS", 0.0),
                "srs": _safe_float(row, "SRS", 0.0),
                "nrtg": _safe_float(row, "NRtg", 0.0),
                "ts_pct": _safe_float(row, "TS%", 0.544),
                # ── Ratings ──
                "off_rating": _safe_float(row, "ORtg", 110.0),
                "def_rating": _safe_float(row, "DRtg", 110.0),
                "pace": _safe_float(row, "Pace", 99.0),
                # ── Offensive Four Factors ──
                "efg_pct": _safe_float(row, "Off_eFG%", 0.500),
                "tov_pct": _safe_float(row, "Off_TOV%", 14.0) / 100.0,
                "orb_pct": _safe_float(row, "Off_ORB%", 25.0) / 100.0,
                "ft_rate": _safe_float(row, "Off_FT/FGA", 0.250),
                # ── Defensive Four Factors ──
                "opp_efg_pct": _safe_float(row, "Def_eFG%", 0.500),
                "opp_tov_pct": _safe_float(row, "Def_TOV%", 14.0) / 100.0,
                "drb_pct": 1.0 - (_safe_float(row, "Def_ORB%", 25.0) / 100.0),
                "opp_ft_rate": _safe_float(row, "Def_FT/FGA", 0.250),
            }

        logger.info(f"Parsed advanced stats for {len(stats_dict)} teams.")
        return stats_dict

    except Exception as e:
        logger.error(f"CRITICAL: Advanced Stats parse failed: {e}")
        return {}


def parse_expanded_standings(html_content: str) -> Dict[int, dict]:
    """
    Parse Expanded Standings → records, home/away, conference, division,
    pre/post All-Star, margins, and monthly form.
    """
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

            # ── Overall record ──
            overall = str(row.get("Overall", "0-0"))
            parts = overall.split("-")
            wins = int(parts[0]) if len(parts) >= 2 else 0
            losses = int(parts[1]) if len(parts) >= 2 else 0

            home_rec = str(row.get("Home", "0-0"))
            road_rec = str(row.get("Road", "0-0"))

            # ── Conference records ──
            vs_east = str(row.get("Conf_E", "0-0"))
            vs_west = str(row.get("Conf_W", "0-0"))

            # Conference record for the team's own conference
            abbr = get_abbr(team_id)
            conf_rec = vs_east if abbr in EASTERN_CONFERENCE else vs_west

            # ── Division records ──
            # Under "Conference" header: A (Atlantic), C (Central)
            # Under "Division" header: SE (Southeast), NW (Northwest), P (Pacific), SW (Southwest)
            vs_atlantic = str(row.get("Conf_A", row.get("Div_A", "0-0")))
            vs_central = str(row.get("Conf_C", row.get("Div_C", "0-0")))
            vs_southeast = str(row.get("Div_SE", "0-0"))
            vs_northwest = str(row.get("Div_NW", "0-0"))
            vs_pacific = str(row.get("Div_P", "0-0"))
            vs_southwest = str(row.get("Div_SW", "0-0"))

            # ── All-Star split ──
            pre_allstar = str(row.get("AS_Pre", "0-0"))
            post_allstar = str(row.get("AS_Post", "0-0"))

            # ── Margin records ──
            margin_close = str(row.get("Margin_≤3", row.get("Margin_\u22643", "0-0")))
            margin_blow = str(row.get("Margin_≥10", row.get("Margin_\u226510", "0-0")))

            # ── Monthly records ──
            monthly = {}
            for month_key in ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]:
                col = f"Mo_{month_key}"
                val = str(row.get(col, "0-0"))
                monthly[month_key.lower()] = val if val and val != "nan" else "0-0"

            # ── Recent form: most recent month with data ──
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
                # v4: conference breakdown
                "vs_east": vs_east,
                "vs_west": vs_west,
                # v4: division breakdown
                "vs_atlantic": vs_atlantic,
                "vs_central": vs_central,
                "vs_southeast": vs_southeast,
                "vs_northwest": vs_northwest,
                "vs_pacific": vs_pacific,
                "vs_southwest": vs_southwest,
                # v4: all-star split
                "pre_allstar": pre_allstar,
                "post_allstar": post_allstar,
                # Margins
                "close_games": margin_close,
                "blowouts": margin_blow,
                # Form
                "recent_record": recent_month,
                "monthly": monthly,
            }

        logger.info(f"Parsed expanded standings for {len(result)} teams.")
        return result

    except Exception as e:
        logger.warning(f"Expanded standings parse failed (non-fatal): {e}")
        return {}


def parse_h2h_matrix(html_content: str) -> Dict[str, Dict[str, str]]:
    """
    Parse Team vs. Team table → dict of {team_abbr: {opp_abbr: "W-L", ...}}.

    This is the 30×30 head-to-head matrix from the standings page.
    """
    logger.info("Parsing Team vs. Team matrix…")
    try:
        tables = pd.read_html(io.StringIO(html_content), match="Team vs. Team")
        if not tables:
            logger.warning("No Team vs. Team table found.")
            return {}

        df = tables[0]

        # Flatten if multi-index (shouldn't be, but safety)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(c[-1]).strip() for c in df.columns]

        matrix: Dict[str, Dict[str, str]] = {}

        for _, row in df.iterrows():
            team_raw = str(row.get("Team", ""))
            team_id = resolve_team_by_name(team_raw)
            if not team_id:
                continue

            team_abbr = get_abbr(team_id)
            team_records: Dict[str, str] = {}

            for col in df.columns:
                if col in ("Rk", "Team"):
                    continue

                opp_abbr = _normalize_bref_abbr(col)
                # Skip self-matchup
                if opp_abbr == team_abbr:
                    continue

                val = row.get(col, "")
                record = str(val).strip() if pd.notna(val) else ""
                if record and record != "nan" and record != "":
                    team_records[opp_abbr] = record

            if team_records:
                matrix[team_abbr] = team_records

        logger.info(f"Parsed H2H matrix for {len(matrix)} teams.")
        return matrix

    except Exception as e:
        logger.warning(f"Team vs. Team parse failed (non-fatal): {e}")
        return {}


# ═══════════════════════════════════════════════════════
#  B-Ref orchestrator
# ═══════════════════════════════════════════════════════

def fetch_all_bref_data(
    season_str: str,
) -> Tuple[Dict[int, dict], Dict[int, dict], Dict[str, Dict[str, str]]]:
    """
    Fetch all B-Ref data with exactly 2 HTTP requests.

    Returns:
        (advanced_stats, expanded_standings, h2h_matrix)
    """
    year = int(season_str.split("-")[0]) + 1
    scraper = _create_scraper()

    # Page 1: Main page → Advanced Stats
    main_url = f"https://www.basketball-reference.com/leagues/NBA_{year}.html"
    logger.info(f"Fetching B-Ref main page: {main_url}")
    main_html = _fetch_bref_page(main_url, scraper)
    bref_stats = parse_advanced_stats(main_html)

    # Page 2: Standings page → Expanded Standings + Team vs. Team
    standings_url = f"https://www.basketball-reference.com/leagues/NBA_{year}_standings.html"
    logger.info(f"Fetching B-Ref standings page: {standings_url}")
    h2h_matrix: Dict[str, Dict[str, str]] = {}
    expanded: Dict[int, dict] = {}

    try:
        standings_html = _fetch_bref_page(standings_url, scraper)
        expanded = parse_expanded_standings(standings_html)
        h2h_matrix = parse_h2h_matrix(standings_html)
    except Exception as e:
        logger.warning(f"Standings page fetch failed: {e}")

    return bref_stats, expanded, h2h_matrix


# ═══════════════════════════════════════════════════════
#  BDL API — schedule & fatigue
# ═══════════════════════════════════════════════════════

def _get_api_key() -> str:
    key = os.getenv("BDL_API_KEY", "")
    if not key:
        logger.error("BDL_API_KEY not set!")
    return key


def _api_get(endpoint: str, params: dict = None, max_retries: int = 4) -> dict:
    """
    BDL API request with exponential backoff + jitter on 429s.

    Backoff sequence: ~3s, ~7s, ~15s, ~31s (base 2^(attempt+1) + jitter).
    """
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
                backoff = (2 ** (attempt + 1)) + random.uniform(1, 4)
                logger.warning(f"BDL 429 (attempt {attempt + 1}/{max_retries}), "
                               f"backoff {backoff:.0f}s…")
                time.sleep(backoff)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                logger.error(f"BDL API failed after {max_retries} attempts: {e}")
                return {}
            backoff = (2 ** (attempt + 1)) + random.uniform(0, 2)
            logger.warning(f"BDL request error (attempt {attempt + 1}): {e}, "
                           f"retrying in {backoff:.0f}s…")
            time.sleep(backoff)
    return {}


def _find_nba_team_id(team: dict) -> int:
    """Map a BDL team dict → internal ID via abbreviation."""
    return ABBR_TO_ID.get(team.get("abbreviation", ""), 0)


def _normalize_game_status(raw_status: str) -> str:
    """
    Normalize the BDL 'status' field to a clean enum.

    BDL returns:
      - "Final" for completed games
      - A tipoff timestamp (e.g. "2026-03-20T23:30:00Z") for future games
      - "In Progress" / a quarter string for live games
      - Various other strings

    We normalize to: FINAL, SCHEDULED, IN_PROGRESS.
    """
    if not raw_status:
        return "SCHEDULED"

    lower = raw_status.strip().lower()

    if lower == "final":
        return "FINAL"

    # BDL sometimes returns timestamps like "2026-03-20T23:30:00Z"
    if "t" in lower and ("z" in lower or "+" in lower or "-" in lower[11:]):
        return "SCHEDULED"

    # Check for in-progress indicators
    in_progress_keywords = ("in progress", "1st qtr", "2nd qtr", "3rd qtr",
                            "4th qtr", "halftime", "ot", "overtime")
    if any(kw in lower for kw in in_progress_keywords):
        return "IN_PROGRESS"

    # If it looks like a date/time string (digits and dashes), treat as scheduled
    if lower.replace("-", "").replace(":", "").replace(" ", "").isdigit():
        return "SCHEDULED"

    return "SCHEDULED"


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
            # start_time: always UTC ISO-8601 (e.g. "2026-03-20T23:30:00.000Z").
            # The Android app converts to device-local TZ for display.
            raw_time = game.get("datetime", game_date)
            # Ensure UTC suffix if missing (BDL sometimes omits it)
            if raw_time and not raw_time.endswith("Z") and "+" not in raw_time:
                raw_time = raw_time.rstrip() + "Z"

            todays_games.append({
                "id": str(game.get("id")),
                "start_time": raw_time,
                "status": _normalize_game_status(game.get("status", "")),
                "home_team_id": home_id,
                "away_team_id": away_id,
            })

    logger.info(f"Schedule: {len(todays_games)} games today, "
                f"{len(yesterdays_teams)} teams on B2B.")
    return todays_games, yesterdays_teams


# ═══════════════════════════════════════════════════════
#  BDL API — last-10 rolling form (v4)
# ═══════════════════════════════════════════════════════

def _bdl_team_id_lookup() -> Dict[str, int]:
    """
    BDL uses its own team IDs (1-30). Map our abbreviations → BDL IDs.
    We fetch the team list once and cache in memory.
    """
    result = _api_get("/nba/v1/teams", {"per_page": 30})
    lookup = {}
    for team in result.get("data", []):
        abbr = team.get("abbreviation", "")
        bdl_id = team.get("id", 0)
        if abbr and bdl_id:
            lookup[abbr] = bdl_id
    return lookup


def fetch_last10_form(team_abbrs: List[str], season: int) -> Dict[str, Dict]:
    """
    Fetch the last 10 completed games for each team in the slate.

    Returns: {abbr: {"last10_wins": int, "last10_losses": int, "last10_games": int}}
    """
    logger.info(f"Fetching last-10 form for {len(team_abbrs)} teams…")

    bdl_lookup = _bdl_team_id_lookup()
    if not bdl_lookup:
        logger.warning("Could not fetch BDL team IDs — skipping last-10 form.")
        return {}

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    form_data: Dict[str, Dict] = {}

    for idx, abbr in enumerate(team_abbrs):
        bdl_id = bdl_lookup.get(abbr)
        if not bdl_id:
            logger.debug(f"No BDL ID for {abbr}, skipping last-10.")
            continue

        # Extra pacing between teams to stay under BDL rate limits
        if idx > 0:
            time.sleep(1.5 + random.uniform(0, 1))

        result = _api_get("/nba/v1/games", {
            "team_ids[]": bdl_id,
            "seasons[]": season,
            "per_page": 15,
            "end_date": yesterday_str,
        })

        games = result.get("data", [])
        # Filter to only Final games, take last 10
        final_games = [g for g in games if g.get("status") == "Final"]
        recent = final_games[:10]

        wins = 0
        losses = 0
        for game in recent:
            home_team = game.get("home_team", {})
            home_score = game.get("home_team_score", 0)
            away_score = game.get("visitor_team_score", 0)

            if home_score == 0 and away_score == 0:
                continue

            is_home = home_team.get("abbreviation", "") == abbr
            if is_home:
                if home_score > away_score:
                    wins += 1
                else:
                    losses += 1
            else:
                if away_score > home_score:
                    wins += 1
                else:
                    losses += 1

        form_data[abbr] = {
            "last10_wins": wins,
            "last10_losses": losses,
            "last10_games": wins + losses,
        }
        logger.debug(f"  {abbr}: last-10 = {wins}-{losses}")

    logger.info(f"Fetched last-10 form for {len(form_data)} teams.")
    return form_data


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

    bref_stats, bref_standings, h2h_matrix = fetch_all_bref_data(season)

    if not bref_stats or len(bref_stats) < 30:
        raise RuntimeError(
            f"FAIL FAST: Only got advanced stats for {len(bref_stats)} teams (need 30). "
            "Basketball-Reference may be blocking or the page structure changed."
        )

    if len(bref_standings) < 30:
        logger.warning(f"Only got standings for {len(bref_standings)} teams "
                       "— continuing with available data.")

    todays_games, yesterdays_teams = fetch_schedule_and_fatigue(season_year)

    # Collect unique team abbreviations in today's slate for last-10 fetch
    slate_abbrs = set()
    for game in todays_games:
        home_id = game["home_team_id"]
        away_id = game["away_team_id"]
        home_info = NBA_TEAMS.get(home_id, {})
        away_info = NBA_TEAMS.get(away_id, {})
        if home_info.get("abbr"):
            slate_abbrs.add(home_info["abbr"])
        if away_info.get("abbr"):
            slate_abbrs.add(away_info["abbr"])

    last10_data = fetch_last10_form(list(slate_abbrs), season_year)

    teams: Dict[str, dict] = {}
    for team_id, team_info in NBA_TEAMS.items():
        raw_stats = bref_stats.get(team_id)
        exp = bref_standings.get(team_id, {})
        abbr = team_info["abbr"]

        teams[str(team_id)] = {
            "id": team_id,
            "abbr": abbr,
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
                "monthly": exp.get("monthly", {}),
                "pre_allstar": exp.get("pre_allstar", "0-0"),
                "post_allstar": exp.get("post_allstar", "0-0"),
                # v4: last-10 rolling form
                "last10_wins": last10_data.get(abbr, {}).get("last10_wins", 0),
                "last10_losses": last10_data.get(abbr, {}).get("last10_losses", 0),
                "last10_games": last10_data.get(abbr, {}).get("last10_games", 0),
            },
            # v4: conference/division records for matchup adjustments
            "standings": {
                "vs_east": exp.get("vs_east", "0-0"),
                "vs_west": exp.get("vs_west", "0-0"),
                "vs_atlantic": exp.get("vs_atlantic", "0-0"),
                "vs_central": exp.get("vs_central", "0-0"),
                "vs_southeast": exp.get("vs_southeast", "0-0"),
                "vs_northwest": exp.get("vs_northwest", "0-0"),
                "vs_pacific": exp.get("vs_pacific", "0-0"),
                "vs_southwest": exp.get("vs_southwest", "0-0"),
            },
        }

    final_data = {
        "cache_date": today_str,
        "teams": teams,
        "games": todays_games,
        "h2h_matrix": h2h_matrix,
    }

    try:
        write_json_atomic(final_data, CACHE_FILE)
        logger.info(f"Cached to {CACHE_FILE.name}")
    except Exception as e:
        logger.warning(f"Failed to write cache: {e}")

    return final_data
