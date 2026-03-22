package com.lovistics.hoopsense.ui.screens.history

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.lovistics.hoopsense.data.model.Picks
import com.lovistics.hoopsense.domain.FormatUtils
import com.lovistics.hoopsense.ui.components.PickCard
import com.lovistics.hoopsense.ui.theme.*

@Composable
fun ExpandableDayCard(slip: Picks) {
    var expanded by remember { mutableStateOf(false) }

    val allPicks = buildList {
        slip.lock?.let { add(it) }
        addAll(slip.premium)
    }
    val wins = allPicks.count { it.status?.uppercase() == "WIN" }
    val losses = allPicks.count { it.status?.uppercase() == "LOSS" }
    val pending = allPicks.count { it.status == null || it.status.uppercase() == "PENDING" }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
            .animateContentSize(),
        colors = CardDefaults.cardColors(containerColor = SurfaceCard),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded }
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    FormatUtils.formatDateHeader(slip.date),
                    style = MaterialTheme.typography.titleMedium,
                    color = TextPrimary
                )

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    if (wins + losses > 0) {
                        Text(
                            text = buildRecordSummary(wins, losses, pending),
                            style = MaterialTheme.typography.labelSmall,
                            color = when {
                                wins > losses -> ValueGreen
                                losses > wins -> LossRed
                                else -> TextSecondary
                            }
                        )
                    }
                    Icon(
                        imageVector = if (expanded) Icons.Default.KeyboardArrowUp
                        else Icons.Default.KeyboardArrowDown,
                        contentDescription = "Expand",
                        tint = TextSecondary
                    )
                }
            }

            if (expanded) {
                Column(modifier = Modifier.padding(bottom = 8.dp)) {
                    slip.lock?.let {
                        PickCard(pick = it, isLock = true, startTime = it.startTime)
                    }
                    slip.premium.forEach {
                        PickCard(pick = it, isLock = false, startTime = it.startTime)
                    }
                }
            }
        }
    }
}

private fun buildRecordSummary(wins: Int, losses: Int, pending: Int): String {
    return buildString {
        if (wins > 0) append("${wins}W")
        if (wins > 0 && losses > 0) append(" ")
        if (losses > 0) append("${losses}L")
        if (pending > 0) append(" ${pending}P")
    }
}
