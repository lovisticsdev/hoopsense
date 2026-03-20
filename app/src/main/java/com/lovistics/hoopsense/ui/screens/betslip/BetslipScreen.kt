package com.lovistics.hoopsense.ui.screens.betslip

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.lovistics.hoopsense.ui.components.GameCard
import com.lovistics.hoopsense.ui.components.HoopSenseTopBar
import com.lovistics.hoopsense.ui.components.PickCard
import com.lovistics.hoopsense.ui.components.PremiumGate
import com.lovistics.hoopsense.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BetslipScreen(
    viewModel: BetslipViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner) {
        lifecycleOwner.lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            viewModel.checkFreshness()
        }
    }

    LaunchedEffect(uiState.error) {
        val error = uiState.error
        if (error != null && uiState.picks != null) {
            snackbarHostState.showSnackbar(
                message = error,
                actionLabel = "DISMISS",
                duration = SnackbarDuration.Short
            )
            viewModel.clearError()
        }
    }

    Scaffold(
        topBar = { HoopSenseTopBar() },
        snackbarHost = {
            SnackbarHost(hostState = snackbarHostState) { data ->
                Snackbar(
                    snackbarData = data,
                    containerColor = SurfaceCard,
                    contentColor = TextSecondary,
                    actionColor = BrandOrange
                )
            }
        },
        containerColor = DeepSpace
    ) { padding ->

        when {
            uiState.isLoading -> LoadingState(modifier = Modifier.padding(padding))

            uiState.error != null && uiState.picks == null -> {
                ErrorState(
                    error = uiState.error ?: "Unknown error",
                    onRetry = { viewModel.refresh() },
                    modifier = Modifier.padding(padding)
                )
            }

            else -> {
                PullToRefreshBox(
                    isRefreshing = uiState.isRefreshing,
                    onRefresh = { viewModel.refresh() },
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                ) {
                    BetslipContent(
                        uiState = uiState,
                        onUnlockPremium = { viewModel.unlockPremium() }
                    )
                }
            }
        }
    }
}

@Composable
private fun LoadingState(modifier: Modifier = Modifier) {
    Box(
        modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(color = BrandOrange)
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                "Loading today's slate…",
                color = TextSecondary,
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}

@Composable
private fun ErrorState(error: String, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    Box(
        modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(32.dp)
        ) {
            Text(
                "Something went wrong",
                style = MaterialTheme.typography.titleMedium,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                error,
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(20.dp))
            OutlinedButton(
                onClick = onRetry,
                colors = ButtonDefaults.outlinedButtonColors(contentColor = BrandOrange)
            ) {
                Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text("Retry")
            }
        }
    }
}

@Composable
private fun BetslipContent(uiState: BetslipUiState, onUnlockPremium: () -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 100.dp)
    ) {
        uiState.metadata?.let { meta ->
            if (meta.modelVersion.isNotEmpty()) {
                item {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "${meta.gamesCount} games today",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextMuted
                        )
                        Text(
                            text = "v${meta.modelVersion}",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextMuted,
                            modifier = Modifier
                                .background(SurfaceHighlight, RoundedCornerShape(4.dp))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
            }
        }

        if (uiState.games.isNotEmpty()) {
            item {
                Text(
                    "TODAY'S GAMES",
                    modifier = Modifier.padding(start = 12.dp, top = 4.dp, bottom = 6.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = TextSecondary
                )
            }

            item {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(0.dp)
                ) {
                    items(uiState.games) { game ->
                        Box(modifier = Modifier.width(300.dp)) {
                            GameCard(game = game)
                        }
                    }
                }
            }
        }

        uiState.picks?.lock?.let { lock ->
            item {
                Text(
                    "FREE PLAY",
                    modifier = Modifier.padding(start = 12.dp, top = 20.dp, bottom = 4.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = BrandOrange
                )
                val game = uiState.games.find { it.id == lock.gameId }
                PickCard(
                    pick = lock,
                    isLock = true,
                    startTime = game?.startTime,
                    awayName = game?.away?.name,
                    homeName = game?.home?.name
                )
            }
        }

        item {
            Text(
                "PREMIUM PICKS",
                modifier = Modifier.padding(start = 12.dp, top = 24.dp, bottom = 4.dp),
                style = MaterialTheme.typography.labelSmall,
                color = TextSecondary
            )
        }

        val premiumList = uiState.picks?.premium ?: emptyList()

        if (uiState.isPremiumUnlocked) {
            items(premiumList) { pick ->
                val game = uiState.games.find { it.id == pick.gameId }
                PickCard(
                    pick = pick,
                    isLock = false,
                    startTime = game?.startTime,
                    awayName = game?.away?.name,
                    homeName = game?.home?.name
                )
            }
        } else if (premiumList.isNotEmpty()) {
            item {
                PremiumGate(
                    premiumList = premiumList,
                    games = uiState.games,
                    onUnlock = onUnlockPremium
                )
            }
        }

        if (uiState.picks == null && uiState.games.isEmpty()) {
            item {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(48.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        "No games scheduled today.\nCheck back tomorrow.",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMuted,
                        textAlign = TextAlign.Center
                    )
                }
            }
        }
    }
}
