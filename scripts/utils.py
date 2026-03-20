"""
Shared utilities for HoopSense.

Pure functions for: team resolution, record parsing, win-percentage helpers,
and atomic file I/O.
"""
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from config import ABBR_TO_ID, NAME_TO_ID, ID_TO_ABBR, ID_TO_NAME


# ── Logging ────────────────────────────────────────────

def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger. Call once from the entry point."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── Team resolution ────────────────────────────────────

def resolve_team_by_name(name: str) -> Optional[int]:
    """Full team name (e.g. 'Oklahoma City Thunder*') → internal ID."""
    return NAME_TO_ID.get(name.replace("*", "").strip().lower())


def resolve_team_by_abbr(abbr: str) -> Optional[int]:
    """Abbreviation (e.g. 'OKC') → internal ID."""
    return ABBR_TO_ID.get(abbr.upper().strip())


def get_abbr(team_id: int) -> str:
    return ID_TO_ABBR.get(team_id, "???")


def get_name(team_id: int) -> str:
    return ID_TO_NAME.get(team_id, "Unknown")


# ── W-L record parsing ────────────────────────────────

def parse_record(record_str: str) -> Tuple[int, int]:
    """Parse '32-18' → (32, 18). Returns (0, 0) on failure."""
    try:
        parts = record_str.strip().split("-")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


def record_win_pct(record_str: str) -> float:
    """Parse a W-L string and return win percentage. Returns 0.5 on failure."""
    w, l = parse_record(record_str)
    total = w + l
    return w / total if total > 0 else 0.5


def record_total_games(record_str: str) -> int:
    """Parse a W-L string and return total games played."""
    w, l = parse_record(record_str)
    return w + l


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))


# ── Atomic file I/O ────────────────────────────────────

def write_json_atomic(data: dict, filepath: Path) -> None:
    """Write JSON atomically: temp file → rename."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(filepath.parent), suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, str(filepath))
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def read_json_safe(filepath: Path, default=None):
    """Read JSON with graceful fallback on missing/corrupt files."""
    if not filepath.exists():
        return default
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default
