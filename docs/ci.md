# CI Plan

Recommended checks:

- Python: `cd scripts && pytest`
- Python validation: `python scripts/validate_output.py`
- Android: `./gradlew :app:testDebugUnitTest :app:assembleDebug`

Daily feed generation should run in GitHub Actions with `BDL_API_KEY` stored as a repository secret.
