"""
Configuration and constants for HoopSense v4.

Single source of truth for: team registry, division/conference mappings,
model weights, thresholds, and derived lookups.
"""
import os
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


# ── Season helper ──────────────────────────────────────

def get_current_season() -> str:
    now = datetime.now(timezone.utc)
    year = now.year
    if now.month >= 10:
        return f"{year}-{str(year + 1)[-2:]}"
    return f"{year - 1}-{str(year)[-2:]}"


# ── API keys ───────────────────────────────────────────

BDL_API_KEY: str = os.getenv("BDL_API_KEY", "")

# ── Paths ──────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Team registry ──────────────────────────────────────

NBA_TEAMS: Dict[int, Dict[str, str]] = {
    1610612737: {"abbr": "ATL", "name": "Atlanta Hawks"},
    1610612738: {"abbr": "BOS", "name": "Boston Celtics"},
    1610612751: {"abbr": "BKN", "name": "Brooklyn Nets"},
    1610612766: {"abbr": "CHA", "name": "Charlotte Hornets"},
    1610612741: {"abbr": "CHI", "name": "Chicago Bulls"},
    1610612739: {"abbr": "CLE", "name": "Cleveland Cavaliers"},
    1610612742: {"abbr": "DAL", "name": "Dallas Mavericks"},
    1610612743: {"abbr": "DEN", "name": "Denver Nuggets"},
    1610612765: {"abbr": "DET", "name": "Detroit Pistons"},
    1610612744: {"abbr": "GSW", "name": "Golden State Warriors"},
    1610612745: {"abbr": "HOU", "name": "Houston Rockets"},
    1610612754: {"abbr": "IND", "name": "Indiana Pacers"},
    1610612746: {"abbr": "LAC", "name": "Los Angeles Clippers"},
    1610612747: {"abbr": "LAL", "name": "Los Angeles Lakers"},
    1610612763: {"abbr": "MEM", "name": "Memphis Grizzlies"},
    1610612748: {"abbr": "MIA", "name": "Miami Heat"},
    1610612749: {"abbr": "MIL", "name": "Milwaukee Bucks"},
    1610612750: {"abbr": "MIN", "name": "Minnesota Timberwolves"},
    1610612740: {"abbr": "NOP", "name": "New Orleans Pelicans"},
    1610612752: {"abbr": "NYK", "name": "New York Knicks"},
    1610612760: {"abbr": "OKC", "name": "Oklahoma City Thunder"},
    1610612753: {"abbr": "ORL", "name": "Orlando Magic"},
    1610612755: {"abbr": "PHI", "name": "Philadelphia 76ers"},
    1610612756: {"abbr": "PHX", "name": "Phoenix Suns"},
    1610612757: {"abbr": "POR", "name": "Portland Trail Blazers"},
    1610612758: {"abbr": "SAC", "name": "Sacramento Kings"},
    1610612759: {"abbr": "SAS", "name": "San Antonio Spurs"},
    1610612761: {"abbr": "TOR", "name": "Toronto Raptors"},
    1610612762: {"abbr": "UTA", "name": "Utah Jazz"},
    1610612764: {"abbr": "WAS", "name": "Washington Wizards"},
}

CURRENT_SEASON: str = get_current_season()

# ── Derived lookups (built once at import) ─────────────

ABBR_TO_ID: Dict[str, int] = {v["abbr"]: k for k, v in NBA_TEAMS.items()}
NAME_TO_ID: Dict[str, int] = {v["name"].lower(): k for k, v in NBA_TEAMS.items()}
ID_TO_ABBR: Dict[int, str] = {k: v["abbr"] for k, v in NBA_TEAMS.items()}
ID_TO_NAME: Dict[int, str] = {k: v["name"] for k, v in NBA_TEAMS.items()}

# ── Conference sets ────────────────────────────────────

EASTERN_CONFERENCE = frozenset({
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET", "IND",
    "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS",
})
WESTERN_CONFERENCE = frozenset({
    "DAL", "DEN", "GSW", "HOU", "LAC", "LAL", "MEM", "MIN",
    "NOP", "OKC", "PHX", "POR", "SAC", "SAS", "UTA",
})

# ── Division registry ──────────────────────────────────

TEAM_DIVISIONS: Dict[str, Dict[str, str]] = {
    # Atlantic (East)
    "BOS": {"conference": "EAST", "division": "ATL_DIV"},
    "BKN": {"conference": "EAST", "division": "ATL_DIV"},
    "NYK": {"conference": "EAST", "division": "ATL_DIV"},
    "PHI": {"conference": "EAST", "division": "ATL_DIV"},
    "TOR": {"conference": "EAST", "division": "ATL_DIV"},
    # Central (East)
    "CHI": {"conference": "EAST", "division": "CEN_DIV"},
    "CLE": {"conference": "EAST", "division": "CEN_DIV"},
    "DET": {"conference": "EAST", "division": "CEN_DIV"},
    "IND": {"conference": "EAST", "division": "CEN_DIV"},
    "MIL": {"conference": "EAST", "division": "CEN_DIV"},
    # Southeast (East)
    "ATL": {"conference": "EAST", "division": "SE_DIV"},
    "CHA": {"conference": "EAST", "division": "SE_DIV"},
    "MIA": {"conference": "EAST", "division": "SE_DIV"},
    "ORL": {"conference": "EAST", "division": "SE_DIV"},
    "WAS": {"conference": "EAST", "division": "SE_DIV"},
    # Northwest (West)
    "DEN": {"conference": "WEST", "division": "NW_DIV"},
    "MIN": {"conference": "WEST", "division": "NW_DIV"},
    "OKC": {"conference": "WEST", "division": "NW_DIV"},
    "POR": {"conference": "WEST", "division": "NW_DIV"},
    "UTA": {"conference": "WEST", "division": "NW_DIV"},
    # Pacific (West)
    "GSW": {"conference": "WEST", "division": "PAC_DIV"},
    "LAC": {"conference": "WEST", "division": "PAC_DIV"},
    "LAL": {"conference": "WEST", "division": "PAC_DIV"},
    "PHX": {"conference": "WEST", "division": "PAC_DIV"},
    "SAC": {"conference": "WEST", "division": "PAC_DIV"},
    # Southwest (West)
    "DAL": {"conference": "WEST", "division": "SW_DIV"},
    "HOU": {"conference": "WEST", "division": "SW_DIV"},
    "MEM": {"conference": "WEST", "division": "SW_DIV"},
    "NOP": {"conference": "WEST", "division": "SW_DIV"},
    "SAS": {"conference": "WEST", "division": "SW_DIV"},
}

# Map opponent division key → standings data key
OPPONENT_DIV_TO_KEY: Dict[str, str] = {
    "ATL_DIV": "vs_atlantic",
    "CEN_DIV": "vs_central",
    "SE_DIV":  "vs_southeast",
    "NW_DIV":  "vs_northwest",
    "PAC_DIV": "vs_pacific",
    "SW_DIV":  "vs_southwest",
}

# Map opponent conference → standings data key
OPPONENT_CONF_TO_KEY: Dict[str, str] = {
    "EAST": "vs_east",
    "WEST": "vs_west",
}

# B-Ref uses different abbreviations for some teams
BREF_ABBR_MAP: Dict[str, str] = {
    "BRK": "BKN",
    "CHO": "CHA",
    "PHO": "PHX",
    "NJN": "BKN",
    "NOH": "NOP",
    "NOK": "NOP",
    "SEA": "OKC",
    "VAN": "MEM",
    "WSB": "WAS",
    "KCK": "SAC",
    "SDC": "LAC",
}


# ── Power-score composition weights (v4) ──────────────

SRS_WEIGHT = 0.50
FOUR_FACTORS_WEIGHT = 0.20
PYTHAGOREAN_WEIGHT = 0.15
FORM_WEIGHT = 0.15

# Dean Oliver's Four Factors weights (within each component)
OFF_FACTOR_WEIGHTS = {
    "efg":  0.40,
    "tov": -0.25,
    "orb":  0.20,
    "ftr":  0.15,
}
DEF_FACTOR_WEIGHTS = {
    "opp_efg": -0.40,
    "opp_tov":  0.25,
    "drb":      0.20,
    "opp_ftr": -0.15,
}

# ── Pythagorean regression ─────────────────────────────

PYTH_SCALING = 0.30  # points per win of luck delta

# ── Form trajectory ────────────────────────────────────

FORM_MONTH_WEIGHTS = [0.50, 0.30, 0.20]  # current, previous, two months ago
FORM_SCALING = 8.0  # converts win% delta to points scale
POST_ASB_MIN_GAMES = 5  # minimum post-ASB games to use that signal
LAST10_WEIGHT = 0.60  # blend: 60% last-10, 40% monthly/post-ASB

# ── Contextual adjustments ─────────────────────────────

HOME_ADVANTAGE_BASE = 2.5
HOME_ADVANTAGE_RANGE = (1.0, 4.0)
B2B_PENALTY_BASE = -1.5
B2B_ROAD_EXTRA = -0.5

# Conference matchup
CONF_MATCHUP_SCALING = 3.0
CONF_MATCHUP_CAP = 1.0

# Division matchup
DIV_MATCHUP_SCALING = 2.0
DIV_MATCHUP_CAP = 0.75
DIV_MIN_GAMES = 4

# Close-game regression
CLOSE_GAME_SCALING = 2.0
CLOSE_GAME_CAP = 1.0
CLOSE_GAME_MIN_GAMES = 5

# Head-to-head
H2H_SCALING = 1.5
H2H_CAP = 0.75
H2H_MIN_GAMES = 2


# ── Spread → probability (logistic model) ──────────────
# k ≈ 5.5 gives ~73% at +7 spread, calibrated to NBA history.

LOGISTIC_K = 5.5


def spread_to_prob(spread: float) -> float:
    """Point spread (home perspective, positive = home favored) → win probability."""
    return 1.0 / (1.0 + math.pow(10, -spread / LOGISTIC_K))


# ── Pick selection thresholds ──────────────────────────

HIGH_CONFIDENCE_PROB = 0.65
MEDIUM_CONFIDENCE_PROB = 0.58
MIN_PICK_PROB = 0.55
MIN_GAMES_FOR_STATS = 10
