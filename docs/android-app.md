# Android App

The Android app uses:

- Jetpack Compose
- Material 3
- Hilt
- OkHttp
- Kotlinx Serialization
- Coil

The data URL is configured through `BuildConfig.HOOPSENSE_DATA_URL` in `app/build.gradle.kts`.

The app displays forecasts, model confidence, and history. Backfilled simulated history is shown but excluded from the primary accuracy record.
