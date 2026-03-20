"""
Configuration and constants for HoopSense.

Single source of truth for: team registry, model weights, thresholds, and derived lookups.
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

EASTERN_CONFERENCE = frozenset({
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET", "IND",
    "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS",
})
WESTERN_CONFERENCE = frozenset({
    "DAL", "DEN", "GSW", "HOU", "LAC", "LAL", "MEM", "MIN",
    "NOP", "OKC", "PHX", "POR", "SAC", "SAS", "UTA",
})

# ── Power-score composition weights ───────────────────

SRS_WEIGHT = 0.70
OFF_FOUR_FACTORS_WEIGHT = 0.15
DEF_FOUR_FACTORS_WEIGHT = 0.15

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

# ── Contextual adjustments ────────────────────────────

HOME_ADVANTAGE_BASE = 2.5
HOME_ADVANTAGE_RANGE = (1.0, 4.0)
B2B_PENALTY_BASE = -1.5
B2B_ROAD_EXTRA = -0.5
HOT_STREAK_BONUS = 0.75
COLD_STREAK_PENALTY = -0.75
HOT_STREAK_THRESHOLD = 7
COLD_STREAK_THRESHOLD = 3

# ── Spread → probability (logistic model) ─────────────
# k ≈ 5.5 gives ~73% at +7 spread, calibrated to NBA history.

LOGISTIC_K = 5.5


def spread_to_prob(spread: float) -> float:
    """Point spread (home perspective, positive = home favored) → win probability."""
    return 1.0 / (1.0 + math.pow(10, -spread / LOGISTIC_K))


# ── Pick selection thresholds ─────────────────────────

HIGH_CONFIDENCE_PROB = 0.65    # model prob that earns HIGH confidence
MEDIUM_CONFIDENCE_PROB = 0.58  # model prob that earns MEDIUM confidence
MIN_PICK_PROB = 0.55           # minimum model probability to make a pick
MIN_GAMES_FOR_STATS = 10       # don't predict if team has fewer games