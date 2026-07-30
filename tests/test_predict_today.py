"""
Tests for today's prediction time-filtering and hole-bet features.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from models.ensemble_model import EnsembleModel, _calculate_hole_bets


# ---------------------------------------------------------------------------
# _calculate_hole_bets
# ---------------------------------------------------------------------------

class TestCalculateHoleBets:
    def test_returns_two_bets(self):
        result = _calculate_hole_bets([1, 2, 3])
        assert len(result["bets"]) == 2

    def test_bet_patterns(self):
        result = _calculate_hole_bets([1, 2, 3])
        bets = result["bets"]
        # 2番手が1着
        assert bets[0] == [2, 1, 3]
        # 3番手が1着
        assert bets[1] == [3, 1, 2]

    def test_confidence_values_lower_than_normal(self):
        result = _calculate_hole_bets([1, 2, 3])
        for c in result["confidence"]:
            assert c < 0.5

    def test_two_confidence_entries(self):
        result = _calculate_hole_bets([1, 2, 3])
        assert len(result["confidence"]) == 2

    def test_empty_order_returns_empty(self):
        result = _calculate_hole_bets([])
        assert result["bets"] == []
        assert result["confidence"] == []

    def test_short_order_returns_empty(self):
        result = _calculate_hole_bets([1, 2])
        assert result["bets"] == []


# ---------------------------------------------------------------------------
# EnsembleModel.predict_today — time filtering
# ---------------------------------------------------------------------------

def _make_mock_race(hour_offset: int, race_number: int = 1) -> MagicMock:
    """Return a mock Race object with date offset from now by hour_offset hours."""
    race = MagicMock()
    race.date = datetime.now() + timedelta(hours=hour_offset)
    race.race_number = race_number
    race.weather = "sunny"
    race.water_condition = "calm"
    race.start_time_hour = race.date.hour
    race.place = "戸田"
    race.venue = "戸田"
    race.race_id = f"test_race_{race_number}"
    return race


class TestPredictTodayFiltering:
    def test_future_races_are_included(self):
        future_race = _make_mock_race(hour_offset=2)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[future_race]):
            results = model.predict_today()
        assert len(results) == 1

    def test_past_races_are_excluded(self):
        past_race = _make_mock_race(hour_offset=-1)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[past_race]):
            results = model.predict_today()
        assert len(results) == 0

    def test_mixed_races_only_future_returned(self):
        past_race = _make_mock_race(hour_offset=-2, race_number=1)
        future_race = _make_mock_race(hour_offset=3, race_number=2)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[past_race, future_race]):
            results = model.predict_today()
        assert len(results) == 1
        assert results[0]["race_id"] == "test_race_2"

    def test_time_remaining_minutes_is_present(self):
        future_race = _make_mock_race(hour_offset=1)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[future_race]):
            results = model.predict_today()
        assert len(results) == 1
        assert "time_remaining_minutes" in results[0]

    def test_time_remaining_is_positive_for_future_race(self):
        future_race = _make_mock_race(hour_offset=2)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[future_race]):
            results = model.predict_today()
        assert results[0]["time_remaining_minutes"] > 0

    def test_tomorrow_prediction_has_no_time_remaining(self):
        tomorrow_race = _make_mock_race(hour_offset=26)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[tomorrow_race]):
            results = model.predict_tomorrow()
        assert len(results) == 1
        assert "time_remaining_minutes" not in results[0]


# ---------------------------------------------------------------------------
# Hole bets in prediction output
# ---------------------------------------------------------------------------

class TestHoleBetsInPrediction:
    def test_hole_bets_key_present(self):
        future_race = _make_mock_race(hour_offset=1)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[future_race]):
            results = model.predict_today()
        assert "hole_bets" in results[0]

    def test_hole_bets_has_bets_and_confidence(self):
        future_race = _make_mock_race(hour_offset=1)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[future_race]):
            results = model.predict_today()
        hole = results[0]["hole_bets"]
        assert "bets" in hole
        assert "confidence" in hole

    def test_hole_confidence_lower_than_normal(self):
        future_race = _make_mock_race(hour_offset=1)
        model = EnsembleModel()
        with patch.object(model, "_get_race_data", return_value=[future_race]):
            results = model.predict_today()
        pred = results[0]
        normal_conf = pred["confidence"]
        for hc in pred["hole_bets"]["confidence"]:
            assert hc < normal_conf


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
