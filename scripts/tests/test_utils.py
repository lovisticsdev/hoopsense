"""Tests for shared utility functions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import parse_record, record_win_pct, record_total_games, clamp


class TestParseRecord:
    def test_normal_record(self):
        assert parse_record("32-18") == (32, 18)

    def test_zero_record(self):
        assert parse_record("0-0") == (0, 0)

    def test_single_digit(self):
        assert parse_record("5-3") == (5, 3)

    def test_empty_string(self):
        assert parse_record("") == (0, 0)

    def test_invalid_format(self):
        assert parse_record("nan") == (0, 0)

    def test_leading_trailing_whitespace(self):
        """Leading/trailing whitespace on the full string is stripped."""
        assert parse_record("  32-18 ") == (32, 18)

    def test_three_parts(self):
        """Only first two parts matter; extra dashes cause failure."""
        assert parse_record("1-2-3") == (1, 2)


class TestRecordWinPct:
    def test_winning_record(self):
        assert record_win_pct("30-10") == 0.75

    def test_losing_record(self):
        assert record_win_pct("10-30") == 0.25

    def test_even_record(self):
        assert record_win_pct("25-25") == 0.5

    def test_zero_games(self):
        """Zero games returns default 0.5."""
        assert record_win_pct("0-0") == 0.5


class TestRecordTotalGames:
    def test_normal(self):
        assert record_total_games("32-18") == 50

    def test_zero(self):
        assert record_total_games("0-0") == 0


class TestClamp:
    def test_within_range(self):
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_below_minimum(self):
        assert clamp(-5.0, 0.0, 10.0) == 0.0

    def test_above_maximum(self):
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_at_boundaries(self):
        assert clamp(0.0, 0.0, 10.0) == 0.0
        assert clamp(10.0, 0.0, 10.0) == 10.0

    def test_negative_range(self):
        assert clamp(0.5, -1.0, 1.0) == 0.5
        assert clamp(-2.0, -1.0, 1.0) == -1.0
