package com.lovistics.hoopsense.ui.screens.history

import com.lovistics.hoopsense.data.model.DailyData
import com.lovistics.hoopsense.data.model.History
import com.lovistics.hoopsense.data.model.Picks
import com.lovistics.hoopsense.domain.repository.GameDataRepository
import com.lovistics.hoopsense.ui.screens.BaseDataViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

/**
 * Pre-computed aggregate stats for the history screen.
 * Keeps computation out of the composable (SoC: ViewModel owns logic).
 */
data class HistoryStats(
    val wins: Int = 0,
    val losses: Int = 0,
    val totalForecasts: Int = 0,
    val winRate: Double = 0.0,
    val simulatedSlipCount: Int = 0
)

data class HistoryUiState(
    val history: History? = null,
    val stats: HistoryStats = HistoryStats(),
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false
)

@HiltViewModel
class HistoryViewModel @Inject constructor(
    repository: GameDataRepository
) : BaseDataViewModel<HistoryUiState>(HistoryUiState(), repository) {

    override fun onDataLoaded(currentState: HistoryUiState, data: DailyData): HistoryUiState {
        return currentState.copy(
            history = data.history,
            stats = computeStats(data.history?.pastSlips),
            isLoading = false,
            isRefreshing = false
        )
    }

    override fun onRefreshStarted(currentState: HistoryUiState): HistoryUiState {
        return currentState.copy(isRefreshing = true)
    }

    override fun onRefreshSuccess(currentState: HistoryUiState, data: DailyData): HistoryUiState {
        return currentState.copy(
            history = data.history,
            stats = computeStats(data.history?.pastSlips),
            isRefreshing = false
        )
    }

    override fun onRefreshFailed(currentState: HistoryUiState, error: Throwable): HistoryUiState {
        return currentState.copy(
            isLoading = false,
            isRefreshing = false
        )
    }

    companion object {
        fun computeStats(slips: List<Picks>?): HistoryStats {
            if (slips.isNullOrEmpty()) return HistoryStats()

            val realTimeSlips = slips.filterNot { it.backfilled }
            val simulatedSlipCount = slips.count { it.backfilled }
            val allPicks = realTimeSlips.flatMap { slip ->
                buildList {
                    slip.lock?.let { add(it) }
                    addAll(slip.premium)
                }
            }
            val wins = allPicks.count { it.status?.uppercase() == "WIN" }
            val losses = allPicks.count { it.status?.uppercase() == "LOSS" }
            val totalForecasts = wins + losses
            val winRate = if (totalForecasts > 0) (wins.toDouble() / totalForecasts) * 100.0 else 0.0

            return HistoryStats(
                wins = wins,
                losses = losses,
                totalForecasts = totalForecasts,
                winRate = winRate,
                simulatedSlipCount = simulatedSlipCount
            )
        }
    }
}
