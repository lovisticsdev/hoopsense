package com.lovistics.hoopsense.domain

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale
import kotlin.math.roundToInt

/**
 * Display formatting utilities.
 *
 * All timestamps in the backend JSON are UTC.
 * Every display helper here converts to the device's local timezone.
 */
object FormatUtils {

    // ── Probability / Spread formatting ─────────────────

    /** 0.623 → "62%" */
    fun formatProbability(prob: Double): String {
        return "${(prob * 100).roundToInt()}%"
    }

    /** Model predicted spread: +5.0 → "+5", -3.5 → "-3.5", 0.0 → "PK" */
    fun formatSpread(spread: Double): String {
        return when {
            spread > 0 -> "+${formatHalf(spread)}"
            spread < 0 -> formatHalf(spread)
            else -> "PK"
        }
    }

    private fun formatHalf(value: Double): String {
        return if (value == value.toLong().toDouble()) {
            value.toLong().toString()
        } else {
            "%.1f".format(value)
        }
    }

    // ── Time / Date formatting (UTC → local) ───────────

    /**
     * Parse a UTC ISO-8601 datetime string and display in the user's local timezone.
     *
     * Handles: "...Z", "...+00:00", "...000Z", bare datetime, "... UTC".
     */
    fun formatGameTime(isoTime: String): String {
        val instant = parseUtcInstant(isoTime) ?: return extractTimeFallback(isoTime)
        val local = instant.atZone(ZoneId.systemDefault())
        return local.format(DateTimeFormatter.ofPattern("h:mm a", Locale.getDefault()))
    }

    /**
     * Format a UTC date string ("2026-03-17") → local display like "Mar 16".
     * Anchored at noon UTC to keep stable for most timezones.
     */
    fun formatDateShort(utcDateStr: String): String {
        return try {
            val utcDate = LocalDate.parse(utcDateStr)
            val noonUtc = utcDate.atTime(12, 0).atZone(ZoneOffset.UTC)
            val localDate = noonUtc.withZoneSameInstant(ZoneId.systemDefault()).toLocalDate()
            val month = localDate.format(DateTimeFormatter.ofPattern("MMM", Locale.getDefault()))
            "$month ${localDate.dayOfMonth}"
        } catch (_: Exception) {
            formatDateShortRaw(utcDateStr)
        }
    }

    /** Full datetime display → "Mar 16, 7:30 PM" */
    fun formatDateTimeFull(isoTime: String): String {
        val instant = parseUtcInstant(isoTime) ?: return isoTime
        val local = instant.atZone(ZoneId.systemDefault())
        return local.format(DateTimeFormatter.ofPattern("MMM d, h:mm a", Locale.getDefault()))
    }

    /** Section header: "2026-03-21" → "Saturday, Mar 21" (in user's timezone). */
    fun formatDateHeader(utcDateStr: String): String {
        return try {
            val utcDate = LocalDate.parse(utcDateStr)
            val noonUtc = utcDate.atTime(12, 0).atZone(ZoneOffset.UTC)
            val localDate = noonUtc.withZoneSameInstant(ZoneId.systemDefault()).toLocalDate()
            localDate.format(DateTimeFormatter.ofPattern("EEEE, MMM d", Locale.getDefault()))
        } catch (_: Exception) {
            formatDateShortRaw(utcDateStr)
        }
    }

    /** Card display: UTC ISO time → "Sat, Mar 21 · 7:30 PM" in user's local timezone. */
    fun formatGameDateTime(isoTime: String): String {
        val instant = parseUtcInstant(isoTime) ?: return extractTimeFallback(isoTime)
        val local = instant.atZone(ZoneId.systemDefault())
        return local.format(DateTimeFormatter.ofPattern("EEE, MMM d · h:mm a", Locale.getDefault()))
    }

    /** Check if a UTC date string represents "today" in the user's local timezone. */
    fun isLocalToday(utcDateStr: String): Boolean {
        return try {
            val utcDate = LocalDate.parse(utcDateStr)
            val noonUtc = utcDate.atTime(12, 0).atZone(ZoneOffset.UTC)
            val localDate = noonUtc.withZoneSameInstant(ZoneId.systemDefault()).toLocalDate()
            localDate == LocalDate.now()
        } catch (_: Exception) {
            false
        }
    }

    // ── Internal helpers ────────────────────────────────

    private fun parseUtcInstant(raw: String): Instant? {
        val trimmed = raw.trim()

        try { return ZonedDateTime.parse(trimmed).toInstant() }
        catch (_: DateTimeParseException) { }

        try { return Instant.parse(trimmed) }
        catch (_: DateTimeParseException) { }

        try {
            val cleaned = trimmed.removeSuffix(" UTC").removeSuffix(" utc")
            return LocalDateTime.parse(cleaned).toInstant(ZoneOffset.UTC)
        } catch (_: DateTimeParseException) { }

        return null
    }

    private fun extractTimeFallback(raw: String): String {
        return try {
            raw.substringAfter("T").substringBefore("Z").substringBefore("+").take(5)
        } catch (_: Exception) {
            "TBD"
        }
    }

    private fun formatDateShortRaw(dateStr: String): String {
        return try {
            val parts = dateStr.split("-")
            val month = when (parts[1]) {
                "01" -> "Jan"; "02" -> "Feb"; "03" -> "Mar"; "04" -> "Apr"
                "05" -> "May"; "06" -> "Jun"; "07" -> "Jul"; "08" -> "Aug"
                "09" -> "Sep"; "10" -> "Oct"; "11" -> "Nov"; "12" -> "Dec"
                else -> parts[1]
            }
            "$month ${parts[2].trimStart('0')}"
        } catch (_: Exception) {
            dateStr
        }
    }
}
