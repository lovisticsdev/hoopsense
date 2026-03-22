"""Tests for the prediction engine — spread model, confidence tiers, power scores."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import spread_to_prob, DEFAULT_WIN_PROB
from prediction_engine import (
    confidence_from_prob,
    calculate_power_score,
    calculate_full_power_score,
    find_best_picks,
)


class TestSpreadToProb:
    """Verify the logistic spread→probability model against known calibration points."""

    def test_zero_spread_is_fifty(self):
        """Even matchup → coin flip."""
        assert abs(spread_to_prob(0.0) - 0.50) < 0.001

    def test_positive_spread_favors_home(self):
        """Home-favored spread → prob > 0.50."""
        assert spread_to_prob(7.0) > 0.70

    def test_negative_spread_favors_away(self):
        """Away-favored spread → prob < 0.50."""
        assert spread_to_prob(-7.0) < 0.30

    def test_large_spread_near_certain(self):
        """Very large spread → near 1.0 but not exactly 1.0."""
        prob = spread_to_prob(20.0)
        assert 0.99 < prob < 1.0

    def test_symmetry(self):
        """spread_to_prob(+x) + spread_to_prob(-x) ≈ 1.0."""
        for spread in [1, 3, 5, 7, 10, 15]:
            total = spread_to_prob(spread) + spread_to_prob(-spread)
            assert abs(total - 1.0) < 0.001

    def test_calibration_at_seven(self):
        """At +7 spread, verify model output matches base-10 logistic (K=5.5)."""
        prob = spread_to_prob(7.0)
        # With base-10 logistic K=5.5: 1/(1+10^(-7/5.5)) ≈ 0.949
        assert 0.94 < prob < 0.96

    def test_calibration_at_eleven(self):
        """At +11 spread, verify model output is near-certain."""
        prob = spread_to_prob(11.0)
        # With base-10 logistic K=5.5: 1/(1+10^(-11/5.5)) = 1/(1+0.01) ≈ 0.99
        assert 0.98 < prob < 1.0


class TestConfidenceFromProb:
    """Verify confidence tier boundaries exactly."""

    def test_lock_threshold(self):
        assert confidence_from_prob(0.90) == "LOCK"
        assert confidence_from_prob(0.95) == "LOCK"
        assert confidence_from_prob(1.0) == "LOCK"

    def test_high_threshold(self):
        assert confidence_from_prob(0.80) == "HIGH"
        assert confidence_from_prob(0.85) == "HIGH"
        assert confidence_from_prob(0.899) == "HIGH"

    def test_medium_threshold(self):
        assert confidence_from_prob(0.65) == "MEDIUM"
        assert confidence_from_prob(0.70) == "MEDIUM"
        assert confidence_from_prob(0.799) == "MEDIUM"

    def test_low_threshold(self):
        assert confidence_from_prob(0.50) == "LOW"
        assert confidence_from_prob(0.60) == "LOW"
        assert confidence_from_prob(0.649) == "LOW"

    def test_boundary_is_inclusive(self):
        """Each threshold is >= (inclusive lower bound)."""
        assert confidence_from_prob(0.90) == "LOCK"
        assert confidence_from_prob(0.80) == "HIGH"
        assert confidence_from_prob(0.65) == "MEDIUM"


class TestCalculatePowerScore:
    def test_returns_float(self, sample_team_stats):
        score = calculate_power_score(sample_team_stats)
        assert isinstance(score, float)

    def test_strong_team_positive(self, sample_team_stats):
        """A strong team (SRS=9.0) should have a clearly positive power score."""
        score = calculate_power_score(sample_team_stats)
        assert score > 3.0

    def test_weak_team_negative(self, sample_weak_stats):
        """A weak team (SRS=-5.8) should have a clearly negative power score."""
        score = calculate_power_score(sample_weak_stats)
        assert score < -1.0

    def test_empty_stats_returns_zero(self):
        assert calculate_power_score({}) == 0.0
        assert calculate_power_score(None) == 0.0

    def test_excludes_form(self, sample_team_stats):
        """Base power score should NOT include form trajectory."""
        base = calculate_power_score(sample_team_stats)
        full = calculate_full_power_score(sample_team_stats, {
            "last10_wins": 10, "last10_losses": 0, "last10_games": 10,
            "post_allstar": "0-0", "close_games": "0-0", "monthly": {},
        })
        # Full score with strong form should differ from base
        assert full != base


class TestFindBestPicks:
    def test_returns_strongs_when_enough(self, sample_games):
        """When ≥3 STRONGs exist, return only them."""
        # sample_games has 2 LOCKs and 1 HIGH — need 3+ LOCKs
        extra_lock = {
            "id": "1006", "start_time": "2026-03-22T04:00:00Z", "status": "SCHEDULED",
            "home": {"team_id": 11, "abbr": "DEN", "name": "Denver Nuggets"},
            "away": {"team_id": 12, "abbr": "POR", "name": "Portland Trail Blazers"},
            "prediction": {
                "home_win_prob": 0.91, "away_win_prob": 0.09,
                "predicted_spread": 11.5, "confidence": "LOCK",
            },
        }
        games = sample_games + [extra_lock]
        picks = find_best_picks(games)
        assert len(picks) == 3
        assert all(p["win_prob"] >= 0.90 for p in picks)

    def test_fills_with_solids_when_not_enough_strongs(self, sample_games):
        """When <3 STRONGs, fill remaining with SOLIDs up to MIN_PICKS."""
        picks = find_best_picks(sample_games)
        assert len(picks) >= 3  # MIN_PICKS
        # First two are LOCKs (0.95, 0.92), third is HIGH (0.85)
        assert picks[0]["win_prob"] >= 0.90
        assert picks[1]["win_prob"] >= 0.90
        assert picks[2]["win_prob"] >= 0.80

    def test_never_surfaces_below_high(self, sample_games):
        """Nothing below HIGH_CONFIDENCE_PROB (0.80) should appear."""
        picks = find_best_picks(sample_games)
        for pick in picks:
            assert pick["win_prob"] >= 0.80

    def test_empty_games(self):
        """No games → no picks."""
        assert find_best_picks([]) == []

    def test_no_qualifying_games(self):
        """All games below threshold → empty picks."""
        low_games = [
            {
                "id": "2001", "start_time": "2026-03-22T00:00:00Z", "status": "SCHEDULED",
                "home": {"team_id": 1, "abbr": "LAL", "name": "Lakers"},
                "away": {"team_id": 2, "abbr": "GSW", "name": "Warriors"},
                "prediction": {
                    "home_win_prob": 0.55, "away_win_prob": 0.45,
                    "predicted_spread": 1.5, "confidence": "LOW",
                },
            },
        ]
        picks = find_best_picks(low_games)
        assert picks == []

    def test_sorted_by_probability(self, sample_games):
        """Picks should be sorted highest probability first."""
        picks = find_best_picks(sample_games)
        probs = [p["win_prob"] for p in picks]
        assert probs == sorted(probs, reverse=True)
