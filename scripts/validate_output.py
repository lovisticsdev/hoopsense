"""
Validate the nba_daily.json output file.

Thin wrapper around validation.validate_file() — used as a standalone
CI/CD check after the pipeline runs.
"""
import sys
from pathlib import Path

from validation import validate_file

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR.parent / "data" / "nba_daily.json"

if __name__ == "__main__":
    sys.exit(0 if validate_file(DATA_FILE) else 1)
