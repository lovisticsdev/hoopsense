package com.lovistics.hoopsense.domain.repository

import com.lovistics.hoopsense.data.model.DailyData
import kotlinx.coroutines.flow.StateFlow

/**
 * Abstraction for daily data access.
 *
 * Decouples ViewModels from the concrete GameRepository implementation,
 * enabling testability via fakes and respecting Dependency Inversion.
 */
interface GameDataRepository {
    val dailyDataStream: StateFlow<DailyData?>
    suspend fun getDailyData(forceRefresh: Boolean = false): Result<DailyData>
}
