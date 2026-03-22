package com.lovistics.hoopsense.data.repository

import android.util.Log
import com.lovistics.hoopsense.data.cache.FileCache
import com.lovistics.hoopsense.data.model.DailyData
import com.lovistics.hoopsense.data.util.DateUtils
import com.lovistics.hoopsense.domain.repository.GameDataRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import javax.inject.Inject

class GameRepository @Inject constructor(
    private val json: Json,
    private val fileCache: FileCache,
    private val client: OkHttpClient
) : GameDataRepository {

    companion object {
        private const val TAG = "GameRepository"
        const val DATA_URL =
            "https://raw.githubusercontent.com/lovisticsdev/hoopsense/main/data/nba_daily.json"
        private const val CACHE_FILE = "nba_daily.json"
        private const val CACHE_MAX_AGE_MS = 15 * 60 * 1000L   // 15 minutes
        private const val STALE_CACHE_NO_EXPIRY = Long.MAX_VALUE
    }

    private val _dailyDataStream = MutableStateFlow<DailyData?>(null)
    override val dailyDataStream = _dailyDataStream.asStateFlow()

    override suspend fun getDailyData(forceRefresh: Boolean): Result<DailyData> {
        return withContext(Dispatchers.IO) {
            if (!forceRefresh) {
                val cached = loadFromCache()
                if (cached != null) return@withContext Result.success(cached)
            }
            fetchFromNetwork()
        }
    }

    private fun loadFromCache(): DailyData? {
        val cached = fileCache.read(CACHE_FILE, CACHE_MAX_AGE_MS) ?: return null
        return try {
            val dailyData = json.decodeFromString<DailyData>(cached)
            val picksDate = dailyData.picks?.date

            if (picksDate != null && !DateUtils.isUtcToday(picksDate)) {
                Log.d(TAG, "Cache is from $picksDate (not today UTC). Forcing network fetch.")
                return null
            }

            Log.d(TAG, "Returning data from cache (date=$picksDate)")
            _dailyDataStream.value = dailyData
            dailyData
        } catch (e: Exception) {
            Log.w(TAG, "Cache corrupted, falling back to network", e)
            null
        }
    }

    private fun fetchFromNetwork(): Result<DailyData> {
        return try {
            val bustUrl = "$DATA_URL?t=${System.currentTimeMillis()}"
            Log.d(TAG, "Fetching data from network: $bustUrl")
            val request = Request.Builder()
                .url(bustUrl)
                .header("Cache-Control", "no-cache, no-store")
                .build()
            val response = client.newCall(request).execute()

            if (!response.isSuccessful) {
                Log.w(TAG, "Network error: HTTP ${response.code}")
                return fallbackToStaleCache()
                    ?: Result.failure(IOException("Server error (${response.code}). Try again later."))
            }

            val body = response.body?.string()
                ?: return Result.failure(IOException("Empty response from server."))

            Log.d(TAG, "Fetched ${body.length} bytes from network")
            fileCache.write(CACHE_FILE, body)
            val newData = json.decodeFromString<DailyData>(body)

            _dailyDataStream.value = newData
            Result.success(newData)

        } catch (e: IOException) {
            Log.e(TAG, "Network fetch failed, trying stale cache", e)
            fallbackToStaleCache()
                ?: Result.failure(IOException("No internet connection. Check your network and try again."))
        } catch (e: Exception) {
            Log.e(TAG, "Unexpected error during fetch", e)
            fallbackToStaleCache()
                ?: Result.failure(Exception("Something went wrong. Please try again."))
        }
    }

    private fun fallbackToStaleCache(): Result<DailyData>? {
        val stale = fileCache.read(CACHE_FILE, STALE_CACHE_NO_EXPIRY) ?: return null
        return try {
            Log.d(TAG, "Using stale cache as fallback")
            val staleData = json.decodeFromString<DailyData>(stale)
            _dailyDataStream.value = staleData
            Result.success(staleData)
        } catch (e: Exception) {
            Log.e(TAG, "Stale cache also corrupted", e)
            null
        }
    }
}
