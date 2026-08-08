"""
REST API routes for the Boat Race Predictor.

All endpoints are registered on the ``api`` Blueprint defined in
``api/__init__.py`` and mounted at ``/api`` by the Flask application.
"""

import json
from datetime import datetime
from typing import Any, Dict

from flask import Response, jsonify, request

from api import api_bp
from api.utils import (
    load_history,
    load_latest_results,
    results_to_csv_string,
    save_results_csv,
    save_results_json,
)
from main import run_all_predictions
from utils.logger import logger

# ---------------------------------------------------------------------------
# Valid model names accepted by the per-model endpoint
# ---------------------------------------------------------------------------
VALID_MODELS = {
    "logistic_regression",
    "random_forest",
    "neural_network",
    "rule_based",
    "statistical",
    "ensemble",
}

MODEL_INFO: Dict[str, Dict[str, Any]] = {
    "logistic_regression": {
        "name": "Logistic Regression",
        "description": "Weight-vector dot-product over normalized feature vector.",
        "type": "machine_learning",
    },
    "random_forest": {
        "name": "Random Forest",
        "description": "Simulates N decision trees via random feature subsets and averages votes.",
        "type": "machine_learning",
    },
    "neural_network": {
        "name": "Neural Network",
        "description": "Two-hidden-layer MLP implemented in NumPy with ReLU activations.",
        "type": "machine_learning",
    },
    "rule_based": {
        "name": "Rule-Based Model",
        "description": "Additive rule engine with configurable, runtime-updatable thresholds.",
        "type": "rule_based",
    },
    "statistical": {
        "name": "Statistical Model",
        "description": "Weighted composite score with softmax probabilities and inverse-probability payouts.",
        "type": "statistical",
    },
    "ensemble": {
        "name": "Ensemble (Weighted Vote)",
        "description": "Aggregates all model predictions via confidence-weighted majority voting.",
        "type": "ensemble",
    },
}

# ---------------------------------------------------------------------------
# Minimal sample race data used when no race data has been persisted yet
# ---------------------------------------------------------------------------
_SAMPLE_RACE: Dict[str, Any] = {
    "race_id": "demo-001",
    "race_number": 1,
    "location": "Kiryu",
    "wind_speed": 2.0,
    "wave_height": 5.0,
    "air_temperature": 22.0,
    "water_temperature": 20.0,
    "entries": [
        {
            "frame_number": 1,
            "player_id": "P001",
            "win_rate": 0.55,
            "place_rate": 0.70,
            "payoff_rate": 0.50,
            "avg_start_timing": 0.12,
            "recent_results": ["1", "2", "1", "3", "1"],
            "rank": "A1",
            "flying_count": 0,
            "avg_speed": 6.8,
            "boat_win_rate": 0.50,
            "boat_place_rate": 0.65,
            "engine_rate": 0.70,
            "exhibition_time": 6.75,
        },
        {
            "frame_number": 2,
            "player_id": "P002",
            "win_rate": 0.40,
            "place_rate": 0.60,
            "payoff_rate": 0.38,
            "avg_start_timing": 0.18,
            "recent_results": ["2", "1", "3", "2", "4"],
            "rank": "A2",
            "flying_count": 0,
            "avg_speed": 6.6,
            "boat_win_rate": 0.42,
            "boat_place_rate": 0.58,
            "engine_rate": 0.60,
            "exhibition_time": 6.80,
        },
        {
            "frame_number": 3,
            "player_id": "P003",
            "win_rate": 0.30,
            "place_rate": 0.50,
            "payoff_rate": 0.28,
            "avg_start_timing": 0.20,
            "recent_results": ["3", "3", "2", "5", "3"],
            "rank": "B1",
            "flying_count": 1,
            "avg_speed": 6.3,
            "boat_win_rate": 0.35,
            "boat_place_rate": 0.50,
            "engine_rate": 0.50,
            "exhibition_time": 6.90,
        },
    ],
}


def _build_results_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap raw run_all_predictions() output in the standard API envelope.

    Args:
        raw: Dictionary returned by :func:`main.run_all_predictions`.

    Returns:
        API-ready payload with ``timestamp``, ``models``, and ``predictions``.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "models": sorted(raw.keys()),
        "predictions": raw,
    }


# ---------------------------------------------------------------------------
# GET /api/predictions
# ---------------------------------------------------------------------------
@api_bp.route("/predictions", methods=["GET"])
def get_predictions() -> Response:
    """Return the latest prediction results for all models.

    If no persisted results exist, runs the models against sample data.

    Returns:
        JSON response with timestamp, model list, and predictions.
    """
    data = load_latest_results()
    if not data:
        logger.info("No cached results found; running predictions now")
        raw = run_all_predictions(_SAMPLE_RACE)
        data = _build_results_payload(raw)
        save_results_json(data)
    return jsonify(data)


# ---------------------------------------------------------------------------
# GET /api/predictions/<model_name>
# ---------------------------------------------------------------------------
@api_bp.route("/predictions/<string:model_name>", methods=["GET"])
def get_prediction_by_model(model_name: str) -> Response:
    """Return the prediction from a single model.

    Args:
        model_name: One of the valid model identifiers.

    Returns:
        JSON response with the model's prediction, or 404 if unknown.
    """
    if model_name not in VALID_MODELS:
        return jsonify({"error": f"Unknown model '{model_name}'", "valid_models": sorted(VALID_MODELS)}), 404

    data = load_latest_results()
    if not data:
        raw = run_all_predictions(_SAMPLE_RACE)
        data = _build_results_payload(raw)
        save_results_json(data)

    predictions = data.get("predictions", {})
    if model_name not in predictions:
        return jsonify({"error": f"No prediction available for model '{model_name}'"}), 404

    return jsonify({
        "timestamp": data.get("timestamp"),
        "model": model_name,
        "prediction": predictions[model_name],
    })


# ---------------------------------------------------------------------------
# POST /api/predict
# ---------------------------------------------------------------------------
@api_bp.route("/predict", methods=["POST"])
def post_predict() -> Response:
    """Accept race data and return immediate predictions from all models.

    Request body (JSON)::

        {
            "entries": [...],
            "conditions": {...}   // optional
        }

    Returns:
        JSON response with all model predictions, or 400 on bad input.
    """
    body = request.get_json(silent=True)
    if not body or "entries" not in body:
        return jsonify({"error": "Request body must be JSON with an 'entries' key."}), 400

    race_data: Dict[str, Any] = {
        "race_id": body.get("race_id", "api-request"),
        "entries": body["entries"],
    }
    conditions = body.get("conditions", {})
    race_data.update(conditions)

    try:
        raw = run_all_predictions(race_data)
    except Exception as exc:
        logger.error("Prediction failed: %s", exc, exc_info=True)
        return jsonify({"error": "Prediction failed", "detail": str(exc)}), 500

    payload = _build_results_payload(raw)
    save_results_json(payload)
    return jsonify(payload), 200


# ---------------------------------------------------------------------------
# GET /api/predictions/export/csv
# ---------------------------------------------------------------------------
@api_bp.route("/predictions/export/csv", methods=["GET"])
def export_predictions_csv() -> Response:
    """Download the latest predictions as a CSV file.

    Returns:
        CSV file download response.
    """
    data = load_latest_results()
    if not data:
        raw = run_all_predictions(_SAMPLE_RACE)
        data = _build_results_payload(raw)
        save_results_json(data)

    csv_text = results_to_csv_string(data)
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions.csv"},
    )


# ---------------------------------------------------------------------------
# GET /api/predictions/export/json
# ---------------------------------------------------------------------------
@api_bp.route("/predictions/export/json", methods=["GET"])
def export_predictions_json() -> Response:
    """Download the latest predictions as a JSON file.

    Returns:
        JSON file download response.
    """
    data = load_latest_results()
    if not data:
        raw = run_all_predictions(_SAMPLE_RACE)
        data = _build_results_payload(raw)
        save_results_json(data)

    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=predictions.json"},
    )


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------
@api_bp.route("/history", methods=["GET"])
def get_history() -> Response:
    """Return the last 100 prediction history entries.

    Returns:
        JSON array of historical prediction payloads.
    """
    history = load_history(limit=100)
    return jsonify({"count": len(history), "history": history})


# ---------------------------------------------------------------------------
# GET /api/models/info
# ---------------------------------------------------------------------------
@api_bp.route("/models/info", methods=["GET"])
def get_models_info() -> Response:
    """Return metadata about all available prediction models.

    Returns:
        JSON object mapping model identifiers to their metadata.
    """
    return jsonify({"models": MODEL_INFO})


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------
@api_bp.route("/health", methods=["GET"])
def health_check() -> Response:
    """Return a simple health-check response.

    Returns:
        JSON object with status ``ok`` and a current timestamp.
    """
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


# ---------------------------------------------------------------------------
# GET /api/races/today
# ---------------------------------------------------------------------------
@api_bp.route("/races/today", methods=["GET"])
def get_today_races() -> Response:
    """Return today's race predictions from the database.

    Returns:
        JSON array of race predictions.
    """
    try:
        from database.db_manager import get_db_manager
        from database.models import Prediction
        db = get_db_manager()
        session = db.get_session()
        try:
            today_str = datetime.now().strftime("%Y%m%d")
            live_rows = session.query(Prediction).filter(
                Prediction.prediction_type == "live_xgboost",
                Prediction.race_id.like(f"{today_str}%"),
            ).order_by(Prediction.confidence.desc()).all()

            if live_rows:
                predictions = []
                for row in live_rows:
                    meta = row.result or {}
                    predictions.append(
                        {
                            "race_id": row.race_id,
                            "date": row.prediction_date.isoformat() if row.prediction_date else datetime.now().isoformat(),
                            "place": meta.get("venue", ""),
                            "venue": meta.get("venue", ""),
                            "race_number": meta.get("race_number", 0),
                            "predicted_order": row.predicted_order or [],
                            "confidence": float(row.confidence or 0.0),
                            "reason": "XGBoost live prediction",
                            "is_recommended": float(row.confidence or 0.0) >= 0.7,
                        }
                    )
                predictions.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
                return jsonify({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "count": len(predictions),
                    "predictions": predictions,
                })
        finally:
            session.close()

        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        predictions = model.predict_today()
        predictions.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
        for pred in predictions:
            pred["is_recommended"] = float(pred.get("confidence", 0.0)) >= 0.7
        return jsonify({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "count": len(predictions),
            "predictions": predictions,
        })
    except Exception as exc:
        logger.error("Today race predictions failed: %s", exc, exc_info=True)
        return jsonify({"error": "予測の取得に失敗しました", "predictions": []}), 500


# ---------------------------------------------------------------------------
# GET /api/races/tomorrow
# ---------------------------------------------------------------------------
@api_bp.route("/races/tomorrow", methods=["GET"])
def get_tomorrow_races() -> Response:
    """Return tomorrow's race predictions from the database.

    Returns:
        JSON array of race predictions.
    """
    try:
        from datetime import timedelta
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        predictions = model.predict_tomorrow()
        tomorrow = datetime.now() + timedelta(days=1)
        return jsonify({
            "date": tomorrow.strftime("%Y-%m-%d"),
            "count": len(predictions),
            "predictions": predictions,
        })
    except Exception as exc:
        logger.error("Tomorrow race predictions failed: %s", exc, exc_info=True)
        return jsonify({"error": "翌日予測の取得に失敗しました", "predictions": []}), 500


# ---------------------------------------------------------------------------
# GET /api/analysis
# ---------------------------------------------------------------------------
@api_bp.route("/analysis", methods=["GET"])
def get_analysis() -> Response:
    """Return performance analysis metrics.

    Returns:
        JSON object with accuracy, precision, recall, and other metrics.
    """
    try:
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        metrics = model.evaluate_performance()
        return jsonify({
            "timestamp": datetime.now().isoformat(),
            "period_days": 30,
            "metrics": metrics,
        })
    except Exception as exc:
        logger.error("Analysis failed: %s", exc, exc_info=True)
        return jsonify({"error": "分析の取得に失敗しました"}), 500


# ---------------------------------------------------------------------------
# POST /api/retrain
# ---------------------------------------------------------------------------
@api_bp.route("/retrain", methods=["POST"])
def post_retrain() -> Response:
    """Trigger model retraining.

    Returns:
        JSON object with retraining results.
    """
    try:
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        result = model.retrain()
        # Remove any internal error keys before sending to client
        safe_result = {k: v for k, v in result.items() if k != "エラー"}
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "result": safe_result,
        })
    except Exception as exc:
        logger.error("Retraining failed: %s", exc, exc_info=True)
        return jsonify({"error": "再学習に失敗しました"}), 500


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------
@api_bp.route("/stats", methods=["GET"])
def get_stats() -> Response:
    """Return overall statistics.

    Returns:
        JSON object with hit rate, recovery rate, and total predictions.
    """
    try:
        from database.db_manager import get_db_manager
        from database.models import Prediction
        db = get_db_manager()
        session = db.get_session()
        try:
            hit_rate_30 = db.calculate_hit_rate(session, days=30)
            hit_rate_7 = db.calculate_hit_rate(session, days=7)
            recovery_rate = db.calculate_recovery_rate(session, days=30)
            total = session.query(Prediction).count()
            return jsonify({
                "timestamp": datetime.now().isoformat(),
                "hit_rate_30d": round(hit_rate_30, 4),
                "hit_rate_7d": round(hit_rate_7, 4),
                "recovery_rate_30d": round(recovery_rate, 4),
                "total_predictions": total,
            })
        finally:
            session.close()
    except Exception as exc:
        logger.error("Stats failed: %s", exc, exc_info=True)
        return jsonify({"error": "統計情報の取得に失敗しました"}), 500
