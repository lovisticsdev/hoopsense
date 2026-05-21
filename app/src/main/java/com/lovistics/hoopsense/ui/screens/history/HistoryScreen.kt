package com.lovistics.hoopsense.ui.screens.history

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.lovistics.hoopsense.ui.components.HoopSenseTopBar
import com.lovistics.hoopsense.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(
    viewModel: HistoryViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val history = uiState.history

    Scaffold(
        topBar = { HoopSenseTopBar() },
        containerColor = DeepSpace
    ) { padding ->

        if (uiState.isLoading) {
            Box(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = BrandOrange)
            }
        } else {
            PullToRefreshBox(
                isRefreshing = uiState.isRefreshing,
                onRefresh = { viewModel.refresh() },
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(12.dp)
                ) {
                    item {
                        StatsGrid(stats = uiState.stats)
                        if (uiState.stats.simulatedSlipCount > 0) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                "Backfilled simulations are shown below but excluded from the primary accuracy record.",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMuted
                            )
                        }
                        Spacer(modifier = Modifier.height(20.dp))
                    }

                    item {
                        Text(
                            "RECENT FORECAST HISTORY",
                            modifier = Modifier.padding(bottom = 8.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = TextSecondary
                        )
                    }

                    if (history?.pastSlips.isNullOrEmpty()) {
                        item {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 32.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    "No history data available yet.\nForecasts will appear after the first daily run.",
                                    color = TextMuted,
                                    style = MaterialTheme.typography.bodySmall,
                                    modifier = Modifier.padding(horizontal = 16.dp)
                                )
                            }
                        }
                    } else {
                        items(history!!.pastSlips) { slip ->
                            ExpandableDayCard(slip = slip)
                        }
                    }
                }
            }
        }
    }
}
