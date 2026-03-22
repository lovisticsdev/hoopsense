package com.lovistics.hoopsense.data.util

import java.time.LocalDate
import java.time.ZoneOffset

/**
 * Date utilities for the data layer.
 *
 * Kept separate from FormatUtils (which handles display formatting)
 * so the repository layer doesn't depend on presentation code.
 */
object DateUtils {

    /**
     * Check if a UTC date string ("2026-03-22") matches today in UTC.
     * Used for cache freshness checks where both sides should stay in UTC.
     */
    fun isUtcToday(utcDateStr: String): Boolean {
        return try {
            LocalDate.parse(utcDateStr) == LocalDate.now(ZoneOffset.UTC)
        } catch (_: Exception) {
            false
        }
    }
}
