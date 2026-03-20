#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

FORCE_FLAG=""
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --force)   FORCE_FLAG="--force" ;;
        --dry-run) DRY_RUN=true ;;
    esac
done

echo "════════════════════════════════════════════════════"
echo " HoopSense v3 — $(date '+%Y-%m-%d %H:%M %Z')"
if [ -n "$FORCE_FLAG" ]; then echo " Mode: FORCE REFRESH"; fi
if [ "$DRY_RUN" = true ];  then echo " Mode: DRY RUN (no push)"; fi
echo "════════════════════════════════════════════════════"

if   [ -d "$SCRIPT_DIR/.venv" ]; then source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -d "$SCRIPT_DIR/venv" ];  then source "$SCRIPT_DIR/venv/bin/activate"
fi

cd "$SCRIPT_DIR"

echo "[1/3] Running data pipeline…"
python generate_picks.py $FORCE_FLAG

echo "[2/3] Validating output…"
python "$SCRIPT_DIR/validate_output.py"

if [ $? -ne 0 ]; then
    echo "ERROR: Validation failed. Aborting."
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    echo "[3/3] Dry run — skipping git push."
else
    cd "$PROJECT_ROOT"
    git add data/nba_daily.json
    git add data/history_slips.json   2>/dev/null || true
    git add data/season_stats.json    2>/dev/null || true
    git add data/nba_raw_stats_cache.json 2>/dev/null || true
    git add scripts/*.py scripts/*.sh scripts/requirements.txt 2>/dev/null || true
    git add .github/ 2>/dev/null || true

    if git diff --staged --quiet; then
        echo "[3/3] No changes to commit."
    else
        git commit -m "Daily update: $(date +'%Y-%m-%d %H:%M') [v3]"
        git push origin main
        echo "[3/3] Pushed updates to GitHub."
    fi
fi

echo "════════════════════════════════════════════════════"
echo " Done! $(date '+%H:%M %Z')"
echo "════════════════════════════════════════════════════"