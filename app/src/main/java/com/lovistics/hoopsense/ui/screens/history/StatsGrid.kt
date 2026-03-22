package com.lovistics.hoopsense.ui.screens.history

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.lovistics.hoopsense.ui.theme.*

/**
 * Displays pre-computed aggregate stats (wins, losses, win rate, total bets).
 * Receives a [HistoryStats] from the ViewModel — no computation in the composable.
 */
@Composable
fun StatsGrid(stats: HistoryStats) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        StatTile(
            modifier = Modifier.weight(1f),
            title = "RECORD",
            value = "${stats.wins}-${stats.losses}"
        )
        StatTile(
            modifier = Modifier.weight(1f),
            title = "WIN %",
            value = "%.1f%%".format(stats.winRate),
            isHighlight = stats.winRate > 55.0
        )
        StatTile(
            modifier = Modifier.weight(1f),
            title = "BETS",
            value = "${stats.totalBets}"
        )
    }
}

@Composable
private fun StatTile(
    modifier: Modifier = Modifier,
    title: String,
    value: String,
    isHighlight: Boolean = false
) {
    val valueColor = if (isHighlight) ValueGreen else TextPrimary
    val bgColor = if (isHighlight) ValueGreenGlow else SurfaceCard
    val borderColor = if (isHighlight) ValueGreen.copy(alpha = 0.3f) else SurfaceHighlight

    Column(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(bgColor)
            .border(1.dp, borderColor, RoundedCornerShape(8.dp))
            .padding(vertical = 12.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(title, style = MaterialTheme.typography.labelSmall, color = TextMuted)
        Spacer(modifier = Modifier.height(2.dp))
        Text(value, style = MaterialTheme.typography.titleMedium, color = valueColor)
    }
}
