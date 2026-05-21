# HoopSense

HoopSense is a native Android NBA forecast app powered by a Python-generated daily JSON feed.

The project has two main parts:

- `scripts/`: fetches NBA data, computes model forecasts, grades history, validates output, and writes public JSON.
- `app/`: Android/Jetpack Compose client that fetches the generated feed, caches it locally, and displays forecasts/history.

HoopSense is framed as an analytics/forecasting tool. It does not process wagers, connect to sportsbooks, or provide financial advice.

## Project layout

```text
app/       Android client
data/      generated public JSON feed and local cache placeholders
scripts/   Python data pipeline and tests
schema/    JSON schemas for generated feed files
docs/      architecture, model, and operating notes
```

## Android app

From the repository root:

```bash
./gradlew :app:assembleDebug
```

The app fetches `data/nba_daily.json` through a configurable `BuildConfig.HOOPSENSE_DATA_URL` value. Debug builds default to the GitHub raw feed.

## Python pipeline

Create a Python virtual environment and install dependencies:

```bash
cd scripts
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `scripts/.env` with:

```env
BDL_API_KEY=your_balldontlie_api_key
```

Generate and validate the daily feed:

```bash
python generate_picks.py --force
python validate_output.py
```

Run tests:

```bash
cd scripts
pytest
```

## Daily automation

```bash
scripts/run_daily.sh --dry-run
scripts/run_daily.sh --force
```

The automation stages only the public generated files:

```text
data/nba_daily.json
data/history_slips.json
```

It intentionally does not run `git add .`.

## Data and model notes

The model is deterministic and explainable, but its confidence labels are heuristic until calibrated against historical outcomes. Backfilled historical slips are marked with `backfilled=true` and are excluded from the primary Android accuracy record.

See `docs/model.md` and `docs/data-pipeline.md`.
