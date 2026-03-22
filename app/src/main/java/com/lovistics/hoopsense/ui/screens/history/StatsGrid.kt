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
import com.lovistics.hoopsense.data.model.Picks
import com.lovistics.hoopsense.ui.theme.*

@Composable
fun StatsGrid(slips: List<Picks>) {
    val allPicks = slips.flatMap { slip ->
        buildList {
            slip.lock?.let { add(it) }
            addAll(slip.premium)
        }
    }
    val wins = allPicks.count { it.status?.uppercase() == "WIN" }
    val losses = allPicks.count { it.status?.uppercase() == "LOSS" }
    val totalBets = wins + losses
    val winRate = if (totalBets > 0) (wins.toDouble() / totalBets) * 100.0 else 0.0

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        StatTile(
            modifier = Modifier.weight(1f),
            title = "RECORD",
            value = "$wins-$losses"
        )
        StatTile(
            modifier = Modifier.weight(1f),
            title = "WIN %",
            value = "%.1f%%".format(winRate),
            isHighlight = winRate > 55.0
        )
        StatTile(
            modifier = Modifier.weight(1f),
            title = "BETS",
            value = "$totalBets"
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
