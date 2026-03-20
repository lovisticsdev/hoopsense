package com.lovistics.hoopsense.ui.components

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.lovistics.hoopsense.R
import com.lovistics.hoopsense.ui.theme.*

@Composable
fun HoopSenseTopBar() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(DeepSpace)
            .padding(horizontal = 16.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center
    ) {
        Image(
            painter = painterResource(id = R.drawable.ic_hoopsense_logo),
            contentDescription = "HoopSense Logo",
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .size(40.dp)
                .clip(CircleShape)
        )

        Spacer(modifier = Modifier.width(12.dp))

        Text(
            text = buildAnnotatedString {
                withStyle(style = SpanStyle(color = BrandOrange, fontWeight = FontWeight.Black)) {
                    append("Hoop")
                }
                withStyle(style = SpanStyle(color = TextPrimary, fontWeight = FontWeight.Bold)) {
                    append("Sense")
                }
            },
            style = MaterialTheme.typography.headlineSmall
        )
    }
}
