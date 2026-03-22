package com.lovistics.hoopsense.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.lovistics.hoopsense.data.model.Game
import com.lovistics.hoopsense.domain.FormatUtils
import com.lovistics.hoopsense.domain.NbaConstants
import com.lovistics.hoopsense.ui.theme.*

@Composable
fun GameCard(game: Game) {
    val prediction = game.prediction

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCard)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {

            // Header: time + confidence badge (no probabilities)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = FormatUtils.formatGameDateTime(game.startTime),
                    style = MaterialTheme.typography.labelSmall,
                    color = TextSecondary
                )
                if (prediction != null) {
                    ConfidenceBadge(confidence = prediction.confidence)
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Matchup row — HOME vs AWAY
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                TeamColumn(
                    abbr = game.home.abbr,
                    modifier = Modifier.weight(1f),
                    alignment = Alignment.Start
                )

                Text("vs", style = MaterialTheme.typography.titleMedium, color = TextMuted,
                    modifier = Modifier.padding(horizontal = 8.dp))

                TeamColumn(
                    abbr = game.away.abbr,
                    modifier = Modifier.weight(1f),
                    alignment = Alignment.End
                )
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
