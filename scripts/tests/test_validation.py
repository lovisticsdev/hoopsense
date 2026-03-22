"""Tests for the validation module — schema and consistency checks."""
import sys
import copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from validation import validate_daily_json, confidence_label_for_prob


class TestConfidenceLabelForProb:
    def test_lock(self):
        assert confidence_label_for_prob(0.95) == "LOCK"

    def test_high(self):
        assert confidence_label_for_prob(0.85) == "HIGH"

    def test_medium(self):
        assert confidence_label_for_prob(0.70) == "MEDIUM"

    def test_low(self):
        assert confidence_label_for_prob(0.55) == "LOW"


class TestValidateDailyJson:
    def test_valid_payload(self, valid_daily_json):
        """A well-formed payload should produce zero errors."""
        errors = validate_daily_json(valid_daily_json)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_metadata(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        del data["metadata"]
        errors = validate_daily_json(data)
        assert any("metadata" in e for e in errors)

    def test_missing_games(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        del data["games"]
        errors = validate_daily_json(data)
        assert any("games" in e for e in errors)

    def test_games_not_a_list(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["games"] = "not a list"
        errors = validate_daily_json(data)
        assert any("not a list" in e.lower() for e in errors)

    def test_game_missing_required_keys(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        del data["games"][0]["home"]
        errors = validate_daily_json(data)
        assert any("game[0] missing 'home'" in e for e in errors)

    def test_probability_out_of_range(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["games"][0]["prediction"]["home_win_prob"] = 1.5
        errors = validate_daily_json(data)
        assert any("outside [0.0, 1.0]" in e for e in errors)

    def test_probabilities_dont_sum_to_one(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["games"][0]["prediction"]["home_win_prob"] = 0.80
        data["games"][0]["prediction"]["away_win_prob"] = 0.80
        errors = validate_daily_json(data)
        assert any("sum to" in e for e in errors)

    def test_pick_references_invalid_game(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["picks"]["lock"]["game_id"] = "NONEXISTENT"
        errors = validate_daily_json(data)
        assert any("not in games list" in e for e in errors)

    def test_pick_confidence_mismatch(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        # Lock pick has 0.95 prob but we'll say confidence is "MEDIUM"
        data["picks"]["lock"]["confidence"] = "MEDIUM"
        errors = validate_daily_json(data)
        assert any("confidence=" in e for e in errors)

    def test_no_games_status_not_flagged(self, valid_daily_json):
        """NO_GAMES status with empty games list is valid."""
        data = copy.deepcopy(valid_daily_json)
        data["metadata"]["status"] = "NO_GAMES"
        data["games"] = []
        data["picks"] = None
        errors = validate_daily_json(data)
        assert errors == []

    def test_active_with_no_games_is_error(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["games"] = []
        errors = validate_daily_json(data)
        assert any("ACTIVE but no games" in e for e in errors)

    def test_pick_missing_required_key(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        del data["picks"]["lock"]["selection"]
        errors = validate_daily_json(data)
        assert any("lock missing 'selection'" in e for e in errors)
