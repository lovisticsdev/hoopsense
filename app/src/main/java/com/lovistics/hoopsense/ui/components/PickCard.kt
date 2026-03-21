package com.lovistics.hoopsense.ui.components

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.lovistics.hoopsense.data.model.Pick
import com.lovistics.hoopsense.domain.FormatUtils
import com.lovistics.hoopsense.domain.NbaConstants
import com.lovistics.hoopsense.ui.theme.*

@Composable
fun PickCard(
    pick: Pick,
    isLock: Boolean = false,
    startTime: String? = null,
    awayName: String? = null,
    homeName: String? = null,
    isBlurred: Boolean = false
) {
    val borderColor = if (isLock) BrandOrange else SurfaceHighlight
    val borderWidth = if (isLock) 2.dp else 1.dp
    val cardShape = RoundedCornerShape(12.dp)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp)
            .border(borderWidth, borderColor, cardShape)
            .animateContentSize(),
        shape = cardShape,
        colors = CardDefaults.cardColors(containerColor = SurfaceCard)
    ) {
        Box(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier
                    .padding(12.dp)
                    .then(if (isBlurred) Modifier.blur(16.dp) else Modifier)
            ) {
                // ── ROW 1: HEADER ──
                PickHeader(pick = pick, isLock = isLock, startTime = startTime)

                Spacer(modifier = Modifier.height(14.dp))

                // ── ROW 2: MATCHUP ──
                if (pick.awayAbbr.isNotEmpty() && pick.homeAbbr.isNotEmpty()) {
                    PickMatchup(pick = pick, awayName = awayName, homeName = homeName)
                    Spacer(modifier = Modifier.height(14.dp))
                }

                // ── ROW 3: THE PICK + WIN PROBABILITY ──
                PickSelection(pick = pick)

                // ── ROW 4: REASONING ──
                if (!pick.reasoning.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(10.dp))
                    HorizontalDivider(color = SurfaceHighlight, thickness = 1.dp)
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        pick.reasoning,
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary
                    )
                }
            }
        }
    }
}

@Composable
private fun PickHeader(pick: Pick, isLock: Boolean, startTime: String?) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(
                text = if (isLock) "LOCK" else "PREMIUM",
                style = MaterialTheme.typography.labelSmall,
                color = if (isLock) BrandOrange else TextMuted
            )
            if (startTime != null) {
                Text(
                    text = "• ${FormatUtils.formatGameTime(startTime)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextSecondary
                )
            }
        }

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            pick.status?.let { status ->
                ResultBadge(status = status)
            }
            ConfidenceBadge(confidence = pick.confidence)
        }
    }
}

@Composable
private fun PickMatchup(pick: Pick, awayName: String?, homeName: String?) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Away team
        Row(verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(
                model = NbaConstants.teamLogoUrl(pick.awayAbbr),
                contentDescription = "${pick.awayAbbr} logo",
                modifier = Modifier.size(36.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Column {
                Text(pick.awayAbbr, style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                if (awayName != null) {
                    Text(awayName, style = MaterialTheme.typography.bodySmall, color = TextSecondary)
                }
            }
        }

        Text("@", style = MaterialTheme.typography.titleMedium, color = TextMuted)

        // Home team
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(horizontalAlignment = Alignment.End) {
                Text(pick.homeAbbr, style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                if (homeName != null) {
                    Text(homeName, style = MaterialTheme.typography.bodySmall, color = TextSecondary)
                }
            }
            Spacer(modifier = Modifier.width(8.dp))
            AsyncImage(
                model = NbaConstants.teamLogoUrl(pick.homeAbbr),
                contentDescription = "${pick.homeAbbr} logo",
                modifier = Modifier.size(36.dp)
            )
        }
    }
}

@Composable
private fun PickSelection(pick: Pick) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(SurfaceDark)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "PICK",
                style = MaterialTheme.typography.labelSmall,
                color = ValueGreen,
                fontWeight = FontWeight.Black
            )
            Spacer(modifier = Modifier.width(10.dp))
            Text(
                text = pick.selection,
                style = MaterialTheme.typography.titleMedium,
                color = TextPrimary
            )
        }
    }
}
