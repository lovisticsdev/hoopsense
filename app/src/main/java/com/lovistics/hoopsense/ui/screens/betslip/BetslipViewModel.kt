package com.lovistics.hoopsense.ui.screens.betslip

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovistics.hoopsense.data.model.Game
import com.lovistics.hoopsense.data.model.Metadata
import com.lovistics.hoopsense.data.model.Picks
import com.lovistics.hoopsense.data.repository.GameRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class BetslipUiState(
    val picks: Picks? = null,
    val games: List<Game> = emptyList(),
    val metadata: Metadata? = null,
    val isPremiumUnlocked: Boolean = false,
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class BetslipViewModel @Inject constructor(
    private val repository: GameRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(BetslipUiState())
    val uiState = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.dailyDataStream.collect { data ->
                if (data != null) {
                    _uiState.update {
                        it.copy(
                            picks = data.picks,
                            games = data.games,
                            metadata = data.metadata,
                            isLoading = false,
                            isRefreshing = false,
                            error = null
                        )
                    }
                }
            }
        }
        loadPicks()
    }

    private fun loadPicks() {
        viewModelScope.launch {
            repository.getDailyData().onFailure { e ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = e.message ?: "Failed to load picks"
                    )
                }
            }
        }
    }

    fun checkFreshness() {
        viewModelScope.launch {
            repository.getDailyData(forceRefresh = false)
        }
    }

    fun refresh() {
        _uiState.update { it.copy(isRefreshing = true) }
        viewModelScope.launch {
            repository.getDailyData(forceRefresh = true)
                .onSuccess { data ->
                    _uiState.update {
                        it.copy(
                            picks = data.picks,
                            games = data.games,
                            metadata = data.metadata,
                            isRefreshing = false,
                            error = null
                        )
                    }
                }
                .onFailure { e ->
                    _uiState.update {
                        it.copy(
                            isRefreshing = false,
                            error = e.message ?: "Refresh failed"
                        )
                    }
                }
        }
    }

    fun unlockPremium() {
        _uiState.update { it.copy(isPremiumUnlocked = true) }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
