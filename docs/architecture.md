# Architecture

HoopSense uses a static-feed architecture.

```text
Python pipeline → data/nba_daily.json → GitHub raw URL → Android app → local cache/UI
```

There is no custom backend service. The Python pipeline owns data fetching, model calculation, history grading, and feed validation. The Android app is a presentation client.

## Runtime flow

1. `scripts/generate_picks.py` fetches schedule/team data.
2. `scripts/prediction_engine.py` computes game forecasts.
3. `scripts/history_manager.py` grades and backfills history.
4. `scripts/validation.py` validates the public payload.
5. `data/nba_daily.json` is committed/published.
6. Android `GameRepository` fetches and caches the feed.
