package com.lovistics.hoopsense.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.lovistics.hoopsense.data.model.Game
import com.lovistics.hoopsense.domain.FormatUtils
import com.lovistics.hoopsense.domain.NbaConstants
import com.lovistics.hoopsense.ui.theme.*

@Composable
fun GameCard(game: Game) {
    val prediction = game.prediction
    val homeProb = prediction?.homeWinProb ?: 0.5
    val awayProb = prediction?.awayWinProb ?: 0.5
    val spread = prediction?.predictedSpread ?: 0.0

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCard)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {

            // Header: time + confidence
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = FormatUtils.formatGameTime(game.startTime),
                    style = MaterialTheme.typography.labelSmall,
                    color = TextSecondary
                )
                if (prediction != null) {
                    ConfidenceBadge(confidence = prediction.confidence)
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Matchup row
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                TeamColumn(
                    abbr = game.away.abbr,
                    modifier = Modifier.weight(1f),
                    alignment = Alignment.Start
                )

                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(horizontal = 8.dp)
                ) {
                    Text("@", style = MaterialTheme.typography.titleMedium, color = TextMuted)
                    if (spread != 0.0) {
                        Text(
                            text = FormatUtils.formatSpread(spread),
                            style = MaterialTheme.typography.labelSmall,
                            color = TextSecondary
                        )
                    }
                }

                TeamColumn(
                    abbr = game.home.abbr,
                    modifier = Modifier.weight(1f),
                    alignment = Alignment.End
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            if (prediction != null) {
                ProbabilityBar(homeProb = homeProb, awayProb = awayProb)
            }
        }
    }
}

@Composable
private fun TeamColumn(
    abbr: String,
    modifier: Modifier = Modifier,
    alignment: Alignment.Horizontal
) {
    Column(
        modifier = modifier,
        horizontalAlignment = alignment
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (alignment == Alignment.Start) {
                TeamLogo(abbr = abbr)
                Spacer(modifier = Modifier.width(6.dp))
            }

            Text(abbr, style = MaterialTheme.typography.titleMedium, color = TextPrimary)

            if (alignment == Alignment.End) {
                Spacer(modifier = Modifier.width(6.dp))
                TeamLogo(abbr = abbr)
            }
        }
    }
}

@Composable
private fun TeamLogo(abbr: String, size: Int = 28) {
    AsyncImage(
        model = NbaConstants.teamLogoUrl(abbr),
        contentDescription = "$abbr logo",
        modifier = Modifier.size(size.dp)
    )
}

@Composable
private fun ProbabilityBar(homeProb: Double, awayProb: Double) {
    val homePct = (homeProb * 100).toInt()
    val awayPct = (awayProb * 100).toInt()

    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = "${awayPct}%",
                style = MaterialTheme.typography.labelSmall,
                color = ProbBarAway,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "${homePct}%",
                style = MaterialTheme.typography.labelSmall,
                color = ProbBarHome,
                fontWeight = FontWeight.Bold
            )
        }
        Spacer(modifier = Modifier.height(3.dp))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(4.dp)
                .clip(RoundedCornerShape(2.dp))
        ) {
            Box(
                modifier = Modifier
                    .weight(awayProb.toFloat().coerceAtLeast(0.05f))
                    .fillMaxHeight()
                    .background(ProbBarAway)
            )
            Spacer(modifier = Modifier.width(2.dp))
            Box(
                modifier = Modifier
                    .weight(homeProb.toFloat().coerceAtLeast(0.05f))
                    .fillMaxHeight()
                    .background(ProbBarHome)
            )
        }
    }
}
