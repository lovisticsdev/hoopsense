# Data Pipeline

The Python pipeline produces the public feed consumed by Android.

## Commands

```bash
cd scripts
python generate_picks.py --force
python validate_output.py
pytest
```

## Secrets

`BDL_API_KEY` belongs in `scripts/.env`. Do not commit it.

## Generated public files

- `data/nba_daily.json`
- `data/history_slips.json`

## Runtime cache

`data/nba_raw_stats_cache.json` is treated as runtime cache and is ignored by the cleaned repository.
