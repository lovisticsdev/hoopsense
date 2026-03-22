package com.lovistics.hoopsense.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class DailyData(
    val metadata: Metadata,
    val games: List<Game> = emptyList(),
    val picks: Picks? = null,
    val history: History? = null
)

@Serializable
data class Metadata(
    @SerialName("generated_at") val generatedAt: String,
    val season: String,
    val status: String = "ACTIVE",
    @SerialName("model_version") val modelVersion: String = "",
    @SerialName("games_count") val gamesCount: Int = 0,
    @SerialName("picks_found") val picksFound: Int = 0
)

@Serializable
data class Game(
    val id: String,
    @SerialName("start_time") val startTime: String,
    val status: String,
    val home: TeamGameInfo,
    val away: TeamGameInfo,
    val prediction: GamePrediction? = null
)

@Serializable
data class TeamGameInfo(
    @SerialName("team_id") val teamId: Int = 0,
    val abbr: String,
    val name: String
)

@Serializable
data class GamePrediction(
    @SerialName("home_win_prob") val homeWinProb: Double = 0.5,
    @SerialName("away_win_prob") val awayWinProb: Double = 0.5,
    @SerialName("predicted_spread") val predictedSpread: Double = 0.0,
    val confidence: String = "LOW"
)

@Serializable
data class Picks(
    val date: String,
    val lock: Pick? = null,
    val premium: List<Pick> = emptyList()
)

@Serializable
data class Pick(
    @SerialName("game_id") val gameId: String,
    @SerialName("away_abbr") val awayAbbr: String = "",
    @SerialName("home_abbr") val homeAbbr: String = "",
    val selection: String,
    @SerialName("win_prob") val winProb: Double = 0.0,
    val confidence: String = "MEDIUM",
    @SerialName("start_time") val startTime: String? = null,
    val status: String? = null
)

@Serializable
data class History(
    @SerialName("past_slips") val pastSlips: List<Picks> = emptyList()
)
