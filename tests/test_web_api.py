"""Integration tests for the Flask web server and REST API."""

import json
import os
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app


@pytest.fixture
def client():
    """Create a Flask test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Web dashboard
# ---------------------------------------------------------------------------

def test_app_starts_without_errors():
    """Flask app should be created without raising any exceptions."""
    app = create_app()
    assert app is not None


def test_dashboard_loads(client):
    """GET / should return the web dashboard with HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

def test_api_predictions_returns_json(client):
    """GET /api/predictions should return valid JSON with expected keys."""
    response = client.get("/api/predictions")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "timestamp" in data
    assert "predictions" in data
    predictions = data["predictions"]
    assert isinstance(predictions, dict)
    assert len(predictions) > 0
    for model_name, result in predictions.items():
        assert "prediction" in result
        assert "confidence" in result
        confidence = result["confidence"]
        assert isinstance(confidence, (int, float))
        assert 0.0 <= confidence <= 1.0


def test_api_health(client):
    """GET /api/health should return status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data.get("status") == "ok"
    assert "timestamp" in data


def test_api_models_info(client):
    """GET /api/models/info should return model metadata."""
    response = client.get("/api/models/info")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "models" in data


def test_api_races_today_returns_real_races(client):
    """GET /api/races/today should return persisted race data."""
    race = SimpleNamespace(
        race_id="20260809_01_01",
        date="2026-08-09T08:40:00",
        venue="桐生",
        place="桐生",
        race_number=1,
        weather="sunny",
        water_condition="calm",
        water_surface="calm",
        wind_speed=2.0,
        temperature=28.0,
        humidity=70.0,
        number_of_boats=6,
        start_time_hour=8,
        time_of_day="morning",
        result=None,
    )
    with patch("scripts.fetch_real_races.ensure_race_data", return_value=[race]):
        response = client.get("/api/races/today")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 1
    assert data["races"][0]["race_id"] == "20260809_01_01"
    assert data["races"][0]["place"] == "桐生"


def test_api_predictions_today_returns_predictions(client):
    """GET /api/predictions/today should return today's predictions."""
    predictions = [
        {
            "race_id": "20260809_01_01",
            "place": "桐生",
            "race_number": 1,
            "predicted_order": [1, 2, 3],
            "confidence": 0.82,
            "is_purchasable": True,
        }
    ]
    with patch("models.ensemble_model.EnsembleModel.predict_today", return_value=predictions):
        response = client.get("/api/predictions/today")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 1
    assert data["predictions"][0]["race_id"] == "20260809_01_01"
    assert data["predictions"][0]["confidence"] == 0.82


def test_export_json(client):
    """GET /api/predictions/export/json should trigger a JSON file download."""
    response = client.get("/api/predictions/export/json")
    assert response.status_code == 200
    assert "application/json" in response.content_type
    content_disposition = response.headers.get("Content-Disposition", "")
    assert "attachment" in content_disposition
    assert "predictions.json" in content_disposition


def test_export_csv(client):
    """GET /api/predictions/export/csv should trigger a CSV file download."""
    response = client.get("/api/predictions/export/csv")
    assert response.status_code == 200
    assert "text/csv" in response.content_type
    content_disposition = response.headers.get("Content-Disposition", "")
    assert "attachment" in content_disposition
    assert "predictions.csv" in content_disposition


def test_post_predict(client):
    """POST /api/predict should accept race data and return predictions."""
    race_data = {
        "entries": [
            {
                "frame_number": 1,
                "player_id": "P001",
                "win_rate": 0.55,
                "place_rate": 0.70,
                "payoff_rate": 0.50,
                "avg_start_timing": 0.12,
                "recent_results": ["1", "2", "1"],
                "rank": "A1",
                "flying_count": 0,
                "avg_speed": 6.8,
                "boat_win_rate": 0.50,
                "boat_place_rate": 0.65,
                "engine_rate": 0.70,
                "exhibition_time": 6.75,
            },
        ]
    }
    response = client.post(
        "/api/predict",
        data=json.dumps(race_data),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "predictions" in data


def test_post_predict_invalid_body(client):
    """POST /api/predict with missing entries key should return 400."""
    response = client.post(
        "/api/predict",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# File export via CLI helper
# ---------------------------------------------------------------------------

@pytest.fixture
def output_dirs(tmp_path, monkeypatch):
    """Fixture that configures temporary output directories for export tests."""
    import config as cfg

    outputs_dir = str(tmp_path / "outputs")
    history_dir = str(tmp_path / "outputs" / "history")
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr(cfg, "OUTPUTS_HISTORY_DIR", history_dir)
    return outputs_dir, history_dir


def test_run_all_models_demo_saves_json(output_dirs):
    """_run_all_models_demo(export='json') should write valid results.json."""
    outputs_dir, history_dir = output_dirs

    from main import _run_all_models_demo

    _run_all_models_demo(export="json")

    json_path = os.path.join(outputs_dir, "results.json")
    assert os.path.exists(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "timestamp" in data
    assert "models" in data
    assert "predictions" in data
    assert len(data["predictions"]) > 0

    history_files = [f for f in os.listdir(history_dir) if f.endswith(".json")]
    assert len(history_files) >= 1


def test_run_all_models_demo_saves_csv(output_dirs):
    """_run_all_models_demo(export='csv') should write valid results.csv."""
    outputs_dir, _ = output_dirs

    from main import _run_all_models_demo

    _run_all_models_demo(export="csv")

    csv_path = os.path.join(outputs_dir, "results.csv")
    assert os.path.exists(csv_path)

    with open(csv_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "timestamp" in content
    assert "model" in content
    assert "prediction" in content
    assert "confidence" in content
    lines = [l for l in content.splitlines() if l.strip()]
    assert len(lines) >= 2  # header + at least one data row


def test_run_all_models_demo_saves_all(output_dirs):
    """_run_all_models_demo(export='all') should write both json and csv."""
    outputs_dir, _ = output_dirs

    from main import _run_all_models_demo

    _run_all_models_demo(export="all")

    assert os.path.exists(os.path.join(outputs_dir, "results.json"))
    assert os.path.exists(os.path.join(outputs_dir, "results.csv"))
