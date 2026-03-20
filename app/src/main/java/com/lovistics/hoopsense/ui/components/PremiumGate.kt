package com.lovistics.hoopsense.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lovistics.hoopsense.data.model.Game
import com.lovistics.hoopsense.data.model.Pick
import com.lovistics.hoopsense.ui.theme.*

@Composable
fun PremiumGate(
    premiumList: List<Pick>,
    games: List<Game>,
    onUnlock: () -> Unit
) {
    Box(
        modifier = Modifier.fillMaxWidth(),
        contentAlignment = Alignment.Center
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            premiumList.forEach { pick ->
                val game = games.find { it.id == pick.gameId }

                val obscuredPick = pick.copy(
                    selection = "HIDDEN",
                    winProb = 0.5,
                    reasoning = "Upgrade to view full analysis."
                )

                PickCard(
                    pick = obscuredPick,
                    isLock = false,
                    startTime = game?.startTime,
                    awayName = game?.away?.name,
                    homeName = game?.home?.name,
                    isBlurred = true
                )
            }
        }

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier
                .fillMaxWidth(0.85f)
                .clip(RoundedCornerShape(16.dp))
                .background(DeepSpace.copy(alpha = 0.85f))
                .border(1.dp, PremiumGoldDark, RoundedCornerShape(16.dp))
                .padding(24.dp)
        ) {
            Icon(
                Icons.Default.Lock,
                contentDescription = "Locked",
                tint = PremiumGold,
                modifier = Modifier.size(36.dp)
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = "Unlock ${premiumList.size} Premium Picks",
                style = MaterialTheme.typography.titleMedium,
                color = PremiumGold
            )
            Spacer(modifier = Modifier.height(16.dp))
            Button(
                onClick = onUnlock,
                colors = ButtonDefaults.buttonColors(containerColor = PremiumGold),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                Text(
                    "UPGRADE TO FULL SLATE",
                    color = DeepSpace,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelSmall
                )
            }
        }
    }
}
