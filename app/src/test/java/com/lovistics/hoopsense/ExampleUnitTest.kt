package com.lovistics.hoopsense

import com.lovistics.hoopsense.data.model.Pick
import com.lovistics.hoopsense.data.model.Picks
import com.lovistics.hoopsense.ui.screens.history.HistoryViewModel
import org.junit.Assert.assertEquals
import org.junit.Test

class HistoryStatsTest {
    @Test
    fun computeStats_excludesBackfilledSlipsFromPrimaryRecord() {
        val real = Picks(
            date = "2026-03-20",
            lock = Pick(gameId = "1", selection = "BOS", status = "WIN"),
            premium = listOf(Pick(gameId = "2", selection = "NYK", status = "LOSS")),
            backfilled = false
        )
        val simulated = Picks(
            date = "2026-03-19",
            lock = Pick(gameId = "3", selection = "LAL", status = "WIN"),
            backfilled = true
        )

        val stats = HistoryViewModel.computeStats(listOf(real, simulated))

        assertEquals(1, stats.wins)
        assertEquals(1, stats.losses)
        assertEquals(2, stats.totalForecasts)
        assertEquals(50.0, stats.winRate, 0.001)
        assertEquals(1, stats.simulatedSlipCount)
    }
}
