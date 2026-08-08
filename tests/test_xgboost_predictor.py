"""Tests for models/xgboost_predictor.py."""

import pytest

pytest.importorskip("xgboost")

from models.xgboost_predictor import XGBoostPredictor


def _make_entry(lane: int, base: float):
    return {
        "lane": lane,
        "player_id": f"P{lane}",
        "win_rate": base,
        "motor_rate": base - 0.2,
        "venue_rate": base - 0.1,
    }


def test_predict_race_returns_probabilities_and_confidence():
    predictor = XGBoostPredictor()

    historical = []
    for idx in range(12):
        entries = [_make_entry(l, 6.5 - l * 0.4 + (0.05 * idx)) for l in range(1, 7)]
        historical.append(
            {
                "race_id": f"h{idx}",
                "weather": "sunny" if idx % 2 == 0 else "cloudy",
                "water_surface": "calm",
                "entries": entries,
                "result_order": [1 if idx % 2 == 0 else 2, 3, 4],
            }
        )

    predictor.fit(historical)

    race = {
        "race_id": "20260802_01_01",
        "weather": "sunny",
        "water_surface": "calm",
        "entries": [_make_entry(l, 6.3 - l * 0.35) for l in range(1, 7)],
    }

    result = predictor.predict_race(race)

    assert result["race_id"] == "20260802_01_01"
    assert len(result["player_probabilities"]) == 6
    assert len(result["predicted_order"]) == 3
    assert 0.0 <= result["confidence"] <= 1.0
    assert len(result["trifecta_probabilities"]) > 0
    total = sum(x["probability"] for x in result["trifecta_probabilities"])
    assert 0.99 <= total <= 1.01


def test_fallback_when_no_training_data():
    predictor = XGBoostPredictor()
    predictor.fit([])

    race = {
        "race_id": "race-x",
        "weather": "rainy",
        "water_surface": "rough",
        "entries": [_make_entry(l, 5.0 - l * 0.2) for l in range(1, 7)],
    }

    result = predictor.predict_race(race)
    assert result["predicted_order"]
    assert 0.0 <= result["confidence"] <= 1.0
