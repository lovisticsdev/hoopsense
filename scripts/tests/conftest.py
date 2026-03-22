"""
Shared test fixtures for HoopSense tests.
"""
import pytest


@pytest.fixture
def sample_team_stats():
    """Realistic team stats for a strong team (≈ OKC-level)."""
    return {
        "wins": 50, "losses": 15,
        "pyth_wins": 52, "pyth_losses": 13,
        "mov": 8.5, "sos": 0.5, "srs": 9.0, "nrtg": 8.7,
        "ts_pct": 0.590,
        "off_rating": 118.0, "def_rating": 109.3, "pace": 100.5,
        "efg_pct": 0.560, "tov_pct": 0.125, "orb_pct": 0.280, "ft_rate": 0.270,
        "opp_efg_pct": 0.490, "opp_tov_pct": 0.145, "drb_pct": 0.770, "opp_ft_rate": 0.230,
    }


@pytest.fixture
def sample_weak_stats():
    """Realistic team stats for a weak team (≈ DET-level)."""
    return {
        "wins": 20, "losses": 45,
        "pyth_wins": 18, "pyth_losses": 47,
        "mov": -6.0, "sos": 0.2, "srs": -5.8, "nrtg": -6.2,
        "ts_pct": 0.530,
        "off_rating": 107.0, "def_rating": 113.2, "pace": 99.0,
        "efg_pct": 0.490, "tov_pct": 0.155, "orb_pct": 0.230, "ft_rate": 0.220,
        "opp_efg_pct": 0.540, "opp_tov_pct": 0.120, "drb_pct": 0.710, "opp_ft_rate": 0.280,
    }


@pytest.fixture
def sample_form():
    """Sample form data with last-10, monthly, close games."""
    return {
        "last10_wins": 7, "last10_losses": 3, "last10_games": 10,
        "post_allstar": "12-3",
        "pre_allstar": "38-12",
        "close_games": "6-5",
        "blowouts": "15-3",
        "recent_record": "8-4",
        "monthly": {
            "oct": "3-1", "nov": "10-3", "dec": "9-4",
            "jan": "10-3", "feb": "8-2", "mar": "8-2", "apr": "0-0",
        },
    }


@pytest.fixture
def sample_games():
    """Sample predicted games for pick selection testing."""
    return [
        {
            "id": "1001", "start_time": "2026-03-22T00:00:00Z", "status": "SCHEDULED",
            "home": {"team_id": 1, "abbr": "OKC", "name": "Oklahoma City Thunder"},
            "away": {"team_id": 2, "abbr": "DET", "name": "Detroit Pistons"},
            "prediction": {
                "home_win_prob": 0.95, "away_win_prob": 0.05,
                "predicted_spread": 14.0, "confidence": "LOCK",
            },
        },
        {
            "id": "1002", "start_time": "2026-03-22T01:00:00Z", "status": "SCHEDULED",
            "home": {"team_id": 3, "abbr": "BOS", "name": "Boston Celtics"},
            "away": {"team_id": 4, "abbr": "WAS", "name": "Washington Wizards"},
            "prediction": {
                "home_win_prob": 0.92, "away_win_prob": 0.08,
                "predicted_spread": 12.0, "confidence": "LOCK",
            },
        },
        {
            "id": "1003", "start_time": "2026-03-22T02:00:00Z", "status": "SCHEDULED",
            "home": {"team_id": 5, "abbr": "CLE", "name": "Cleveland Cavaliers"},
            "away": {"team_id": 6, "abbr": "CHA", "name": "Charlotte Hornets"},
            "prediction": {
                "home_win_prob": 0.85, "away_win_prob": 0.15,
                "predicted_spread": 8.0, "confidence": "HIGH",
            },
        },
        {
            "id": "1004", "start_time": "2026-03-22T02:30:00Z", "status": "SCHEDULED",
            "home": {"team_id": 7, "abbr": "MIL", "name": "Milwaukee Bucks"},
            "away": {"team_id": 8, "abbr": "IND", "name": "Indiana Pacers"},
            "prediction": {
                "home_win_prob": 0.70, "away_win_prob": 0.30,
                "predicted_spread": 4.5, "confidence": "MEDIUM",
            },
        },
        {
            "id": "1005", "start_time": "2026-03-22T03:00:00Z", "status": "SCHEDULED",
            "home": {"team_id": 9, "abbr": "LAL", "name": "Los Angeles Lakers"},
            "away": {"team_id": 10, "abbr": "GSW", "name": "Golden State Warriors"},
            "prediction": {
                "home_win_prob": 0.55, "away_win_prob": 0.45,
                "predicted_spread": 1.5, "confidence": "LOW",
            },
        },
    ]


@pytest.fixture
def valid_daily_json(sample_games):
    """A valid nba_daily.json payload."""
    return {
        "metadata": {
            "generated_at": "2026-03-22T12:00:00Z",
            "season": "2025-26",
            "status": "ACTIVE",
            "model_version": "5.0",
            "games_count": len(sample_games),
            "picks_found": 3,
        },
        "games": sample_games,
        "picks": {
            "date": "2026-03-22",
            "lock": {
                "game_id": "1001", "selection": "OKC",
                "home_abbr": "OKC", "away_abbr": "DET",
                "win_prob": 0.95, "confidence": "LOCK",
                "start_time": "2026-03-22T00:00:00Z",
            },
            "premium": [
                {
                    "game_id": "1002", "selection": "BOS",
                    "home_abbr": "BOS", "away_abbr": "WAS",
                    "win_prob": 0.92, "confidence": "LOCK",
                    "start_time": "2026-03-22T01:00:00Z",
                },
                {
                    "game_id": "1003", "selection": "CLE",
                    "home_abbr": "CLE", "away_abbr": "CHA",
                    "win_prob": 0.85, "confidence": "HIGH",
                    "start_time": "2026-03-22T02:00:00Z",
                },
            ],
        },
        "history": {"past_slips": [], "backfilled_dates": []},
    }
