package com.lovistics.hoopsense.domain

/**
 * Shared NBA constants used across the app.
 */
object NbaConstants {

    private const val LOGO_BASE = "https://a.espncdn.com/i/teamlogos/nba/500/"

    fun teamLogoUrl(abbr: String): String = "${LOGO_BASE}${abbr.lowercase()}.png"
}
