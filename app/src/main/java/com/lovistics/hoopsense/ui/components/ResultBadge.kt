package com.lovistics.hoopsense.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.lovistics.hoopsense.ui.theme.*

@Composable
fun ResultBadge(status: String) {
    val (bgColor, textColor, text) = when {
        status.uppercase() == "WIN" -> Triple(ValueGreenGlow, ValueGreen, "WIN")
        status.uppercase() == "LOSS" -> Triple(LossRedGlow, LossRed, "LOSS")
        else -> Triple(SurfaceHighlight, TextSecondary, "PENDING")
    }

    Text(
        text = text,
        color = textColor,
        style = MaterialTheme.typography.labelSmall,
        modifier = Modifier
            .background(bgColor, RoundedCornerShape(4.dp))
            .padding(horizontal = 6.dp, vertical = 2.dp)
    )
}

@Composable
fun ConfidenceBadge(confidence: String) {
    val (bgColor, textColor) = when (confidence.uppercase()) {
        "HIGH" -> ConfidenceHigh.copy(alpha = 0.15f) to ConfidenceHigh
        "MEDIUM" -> ConfidenceMedium.copy(alpha = 0.15f) to ConfidenceMedium
        else -> ConfidenceLow.copy(alpha = 0.15f) to ConfidenceLow
    }

    Text(
        text = confidence.uppercase(),
        color = textColor,
        style = MaterialTheme.typography.labelSmall,
        modifier = Modifier
            .background(bgColor, RoundedCornerShape(4.dp))
            .padding(horizontal = 6.dp, vertical = 2.dp)
    )
}
