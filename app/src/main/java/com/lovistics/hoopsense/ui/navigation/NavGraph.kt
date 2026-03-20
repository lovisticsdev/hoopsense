package com.lovistics.hoopsense.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.lovistics.hoopsense.ui.screens.betslip.BetslipScreen
import com.lovistics.hoopsense.ui.screens.history.HistoryScreen

@Composable
fun NavGraph(navController: NavHostController) {
    NavHost(navController = navController, startDestination = Screen.Betslip.route) {
        composable(Screen.Betslip.route) {
            BetslipScreen()
        }
        composable(Screen.History.route) {
            HistoryScreen()
        }
    }
}
