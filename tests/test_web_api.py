"""Integration tests for the Flask web server and REST API."""

import json
import os
from datetime import datetime, timedelta, timezone
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


def test_predictions_today_page_uses_closing_soon_section(client):
    """Today's predictions page should classify closing-soon races instead of past races."""
    response = client.get("/predictions/today")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "購入締切間近" in body
    assert "終了したレース" not in body


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


def test_api_today_races_filters_past_and_sets_status(client, monkeypatch):
    """GET /api/races/today should only return future races with purchase status."""
    import api.routes as api_routes
    import models.ensemble_model as ensemble_model

    fixed_now = datetime(2026, 8, 9, 12, 2, 0, tzinfo=timezone(timedelta(hours=9)))

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    class DummyEnsembleModel:
        def predict_today(self):
            return [
                {
                    "race_id": "past-race",
                    "race_number": 1,
                    "date": (fixed_now - timedelta(minutes=1)).replace(tzinfo=None).isoformat(),
                    "confidence": 0.91,
                },
                {
                    "race_id": "closing-soon-race",
                    "race_number": 2,
                    "date": (fixed_now + timedelta(minutes=4)).replace(tzinfo=None).isoformat(),
                    "confidence": 0.73,
                },
                {
                    "race_id": "available-race",
                    "race_number": 3,
                    "date": (fixed_now + timedelta(minutes=20)).replace(tzinfo=None).isoformat(),
                    "confidence": 0.88,
                },
                {
                    "race_id": "aware-available-race",
                    "race_number": 4,
                    "date": (fixed_now + timedelta(minutes=35)).replace(
                        tzinfo=timezone(timedelta(hours=9))
                    ).isoformat(),
                    "confidence": 0.61,
                },
            ]

    monkeypatch.setattr(api_routes, "datetime", FixedDateTime)
    monkeypatch.setattr(ensemble_model, "EnsembleModel", DummyEnsembleModel)

    response = client.get("/api/races/today")
    assert response.status_code == 200
    data = json.loads(response.data)

    assert data["date"] == "2026-08-09"
    assert data["count"] == 3

    race_ids = [prediction["race_id"] for prediction in data["predictions"]]
    assert "past-race" not in race_ids
    assert race_ids == ["closing-soon-race", "available-race", "aware-available-race"]

    statuses = {prediction["race_id"]: prediction for prediction in data["predictions"]}
    assert statuses["closing-soon-race"]["status"] == "購入締切間近"
    assert statuses["closing-soon-race"]["is_closing_soon"] is True
    assert statuses["closing-soon-race"]["is_purchasable"] is False
    assert statuses["available-race"]["status"] == "購入可能"
    assert statuses["available-race"]["is_closing_soon"] is False
    assert statuses["available-race"]["is_purchasable"] is True
    assert statuses["aware-available-race"]["status"] == "購入可能"
    assert statuses["aware-available-race"]["is_closing_soon"] is False
    assert statuses["aware-available-race"]["is_purchasable"] is True


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
