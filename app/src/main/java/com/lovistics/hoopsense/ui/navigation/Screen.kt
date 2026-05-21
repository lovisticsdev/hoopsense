package com.lovistics.hoopsense.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Star
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(val route: String, val title: String, val icon: ImageVector) {
    object Betslip : Screen("forecasts", "Forecasts", Icons.Default.Star)
    object History : Screen("history", "Accuracy", Icons.Default.DateRange)
}
