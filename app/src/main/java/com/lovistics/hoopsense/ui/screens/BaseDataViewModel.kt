package com.lovistics.hoopsense.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovistics.hoopsense.data.model.DailyData
import com.lovistics.hoopsense.domain.repository.GameDataRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Base ViewModel that encapsulates the shared data-loading pattern:
 *   1. Collect from dailyDataStream (for live updates).
 *   2. Trigger initial fetch via getDailyData().
 *   3. Provide a refresh() method with loading/error state management.
 *
 * Subclasses define how DailyData maps to their screen-specific UiState.
 */
abstract class BaseDataViewModel<S>(
    initialState: S,
    private val repository: GameDataRepository,
) : ViewModel() {

    protected val _uiState = MutableStateFlow(initialState)
    val uiState = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.dailyDataStream.collect { data ->
                if (data != null) {
                    _uiState.update { onDataLoaded(it, data) }
                }
            }
        }
        viewModelScope.launch {
            repository.getDailyData().onFailure { error ->
                _uiState.update { onLoadFailed(it, error) }
            }
        }
    }

    /** Non-force fetch — silently refreshes if cache has expired. */
    fun checkFreshness() {
        viewModelScope.launch {
            repository.getDailyData(forceRefresh = false)
        }
    }

    fun refresh() {
        _uiState.update { onRefreshStarted(it) }
        viewModelScope.launch {
            repository.getDailyData(forceRefresh = true)
                .onSuccess { data ->
                    _uiState.update { onRefreshSuccess(it, data) }
                }
                .onFailure { error ->
                    _uiState.update { onRefreshFailed(it, error) }
                }
        }
    }

    /** Map freshly loaded DailyData into this screen's UiState. */
    protected abstract fun onDataLoaded(currentState: S, data: DailyData): S

    /** Mark the UiState as "refresh in progress". */
    protected abstract fun onRefreshStarted(currentState: S): S

    /** Update UiState with successfully refreshed data. */
    protected abstract fun onRefreshSuccess(currentState: S, data: DailyData): S

    /** Update UiState when refresh fails. */
    protected abstract fun onRefreshFailed(currentState: S, error: Throwable): S

    /** Update UiState when initial load fails. Default: delegates to onRefreshFailed. */
    protected open fun onLoadFailed(currentState: S, error: Throwable): S {
        return onRefreshFailed(currentState, error)
    }
}
