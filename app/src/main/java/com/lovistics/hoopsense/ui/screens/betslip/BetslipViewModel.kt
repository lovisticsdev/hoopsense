package com.lovistics.hoopsense.ui.screens.betslip

import com.lovistics.hoopsense.data.model.DailyData
import com.lovistics.hoopsense.data.model.Game
import com.lovistics.hoopsense.data.model.Metadata
import com.lovistics.hoopsense.data.model.Picks
import com.lovistics.hoopsense.domain.repository.GameDataRepository
import com.lovistics.hoopsense.ui.screens.BaseDataViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.update
import javax.inject.Inject

data class BetslipUiState(
    val picks: Picks? = null,
    val games: List<Game> = emptyList(),
    val gameById: Map<String, Game> = emptyMap(),
    val metadata: Metadata? = null,
    val isPremiumUnlocked: Boolean = false,
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val errorMessage: String? = null
)

@HiltViewModel
class BetslipViewModel @Inject constructor(
    repository: GameDataRepository
) : BaseDataViewModel<BetslipUiState>(BetslipUiState(), repository) {

    override fun onDataLoaded(currentState: BetslipUiState, data: DailyData): BetslipUiState {
        return currentState.copy(
            picks = data.picks,
            games = data.games,
            gameById = data.games.associateBy { it.id },
            metadata = data.metadata,
            isLoading = false,
            isRefreshing = false,
            errorMessage = null
        )
    }

    override fun onRefreshStarted(currentState: BetslipUiState): BetslipUiState {
        return currentState.copy(isRefreshing = true)
    }

    override fun onRefreshSuccess(currentState: BetslipUiState, data: DailyData): BetslipUiState {
        return currentState.copy(
            picks = data.picks,
            games = data.games,
            gameById = data.games.associateBy { it.id },
            metadata = data.metadata,
            isRefreshing = false,
            errorMessage = null
        )
    }

    override fun onRefreshFailed(currentState: BetslipUiState, error: Throwable): BetslipUiState {
        return currentState.copy(
            isLoading = false,
            isRefreshing = false,
            errorMessage = error.message ?: "Something went wrong"
        )
    }

    fun unlockPremium() {
        _uiState.update { it.copy(isPremiumUnlocked = true) }
    }

    fun clearError() {
        _uiState.update { it.copy(errorMessage = null) }
    }
}
