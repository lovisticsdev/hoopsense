"""Tests for the validation module — schema and consistency checks."""
import sys
import copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import confidence_from_prob
from validation import validate_daily_json


class TestConfidenceFromProb:
    def test_lock(self):
        assert confidence_from_prob(0.95) == "LOCK"

    def test_high(self):
        assert confidence_from_prob(0.85) == "HIGH"

    def test_medium(self):
        assert confidence_from_prob(0.70) == "MEDIUM"

    def test_low(self):
        assert confidence_from_prob(0.55) == "LOW"


class TestValidateDailyJson:
    def test_valid_payload(self, valid_daily_json):
        errors = validate_daily_json(valid_daily_json)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_metadata(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        del data["metadata"]
        assert any("metadata" in e for e in validate_daily_json(data))

    def test_missing_games(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        del data["games"]
        assert any("games" in e for e in validate_daily_json(data))

    def test_games_not_a_list(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["games"] = "not a list"
        assert any("not a list" in e.lower() for e in validate_daily_json(data))

    def test_game_missing_required_keys(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        del data["games"][0]["home"]
        assert any("game[0] missing 'home'" in e for e in validate_daily_json(data))

    def test_probability_out_of_range(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["games"][0]["prediction"]["home_win_prob"] = 1.5
        assert any("outside [0.0, 1.0]" in e for e in validate_daily_json(data))

    def test_probabilities_dont_sum_to_one(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["games"][0]["prediction"]["home_win_prob"] = 0.80
        data["games"][0]["prediction"]["away_win_prob"] = 0.80
        assert any("sum to" in e for e in validate_daily_json(data))

    def test_pick_references_invalid_game(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["picks"]["lock"]["game_id"] = "NONEXISTENT"
        assert any("not in games list" in e for e in validate_daily_json(data))

    def test_pick_confidence_mismatch(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["picks"]["lock"]["confidence"] = "MEDIUM"
        assert any("confidence=" in e for e in validate_daily_json(data))

    def test_no_games_status_not_flagged(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["metadata"]["status"] = "NO_GAMES"
        data["games"] = []
        data["picks"] = None
        assert validate_daily_json(data) == []

    def test_active_with_no_games_is_error(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        data["games"] = []
        assert any("ACTIVE but no games" in e for e in validate_daily_json(data))

    def test_pick_missing_required_key(self, valid_daily_json):
        data = copy.deepcopy(valid_daily_json)
        del data["picks"]["lock"]["selection"]
        assert any("lock missing 'selection'" in e for e in validate_daily_json(data))
