package com.lovistics.hoopsense.ui.screens.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovistics.hoopsense.data.model.History
import com.lovistics.hoopsense.data.repository.GameRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HistoryUiState(
    val history: History? = null,
    val isLoading: Boolean = true
)

@HiltViewModel
class HistoryViewModel @Inject constructor(
    private val repository: GameRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(HistoryUiState())
    val uiState = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.dailyDataStream.collect { data ->
                if (data != null) {
                    _uiState.update {
                        it.copy(history = data.history, isLoading = false)
                    }
                }
            }
        }
        viewModelScope.launch {
            repository.getDailyData()
        }
    }
}
