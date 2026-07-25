"""Integration tests for the Flask web server and REST API."""

import json
import os
import pytest

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
    """POST /api/predict with missing entries should return 400."""
    response = client.post(
        "/api/predict",
        data=json.dumps({"conditions": {}}),
        content_type="application/json",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# File export via CLI helper
# ---------------------------------------------------------------------------

def test_run_all_models_demo_saves_json(tmp_path, monkeypatch):
    """_run_all_models_demo(export='json') should write results.json."""
    import config as cfg

    outputs_dir = str(tmp_path / "outputs")
    history_dir = str(tmp_path / "outputs" / "history")
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr(cfg, "OUTPUTS_HISTORY_DIR", history_dir)

    from main import _run_all_models_demo

    _run_all_models_demo(export="json")

    assert os.path.exists(os.path.join(outputs_dir, "results.json"))
    assert len(os.listdir(history_dir)) >= 1


def test_run_all_models_demo_saves_csv(tmp_path, monkeypatch):
    """_run_all_models_demo(export='csv') should write results.csv."""
    import config as cfg

    outputs_dir = str(tmp_path / "outputs")
    history_dir = str(tmp_path / "outputs" / "history")
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr(cfg, "OUTPUTS_HISTORY_DIR", history_dir)

    from main import _run_all_models_demo

    _run_all_models_demo(export="csv")

    assert os.path.exists(os.path.join(outputs_dir, "results.csv"))


def test_run_all_models_demo_saves_all(tmp_path, monkeypatch):
    """_run_all_models_demo(export='all') should write both json and csv."""
    import config as cfg

    outputs_dir = str(tmp_path / "outputs")
    history_dir = str(tmp_path / "outputs" / "history")
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr(cfg, "OUTPUTS_HISTORY_DIR", history_dir)

    from main import _run_all_models_demo

    _run_all_models_demo(export="all")

    assert os.path.exists(os.path.join(outputs_dir, "results.json"))
    assert os.path.exists(os.path.join(outputs_dir, "results.csv"))
