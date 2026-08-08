"""Fetch official races and run live XGBoost predictions."""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db_manager
from models.xgboost_predictor import XGBoostPredictor
from scrapers.official_scraper import OfficialRaceScraper


LOG_FILE = "logs/predictor.log"
INTERMEDIATE_JSON = "outputs/live_predictions/latest_live_predictions.json"
INTERMEDIATE_CSV = "outputs/live_predictions/latest_live_predictions.csv"


def _get_logger() -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("predictor")
    logger.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith("predictor.log") for h in logger.handlers):
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger


def _save_intermediate(predictions: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(INTERMEDIATE_JSON), exist_ok=True)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "count": len(predictions),
        "predictions": predictions,
    }
    with open(INTERMEDIATE_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(INTERMEDIATE_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["race_id", "venue", "race_number", "predicted_order", "confidence", "top_trifecta", "top_trifecta_probability"],
        )
        writer.writeheader()
        for item in predictions:
            top_trifecta = (item.get("trifecta_probabilities") or [{}])[0]
            writer.writerow(
                {
                    "race_id": item.get("race_id", ""),
                    "venue": item.get("venue", ""),
                    "race_number": item.get("race_number", ""),
                    "predicted_order": "-".join(str(x) for x in item.get("predicted_order", [])),
                    "confidence": item.get("confidence", 0.0),
                    "top_trifecta": top_trifecta.get("combination", ""),
                    "top_trifecta_probability": top_trifecta.get("probability", 0.0),
                }
            )


def _save_predictions_to_db(predictions: List[Dict[str, Any]]) -> int:
    db = get_db_manager()
    session = db.get_session()
    saved = 0
    try:
        for item in predictions:
            db.add_prediction(
                session,
                {
                    "race_id": item.get("race_id"),
                    "prediction_date": datetime.now(),
                    "prediction_type": "live_xgboost",
                    "predicted_order": item.get("predicted_order", []),
                    "confidence": float(item.get("confidence", 0.0)),
                    "estimated_odds": 0.0,
                    "model_version": "xgboost_v1",
                    "methods_used": ["xgboost", "official_scraper"],
                    "result": {
                        "venue": item.get("venue", ""),
                        "race_number": item.get("race_number", 0),
                        "trifecta_probabilities": item.get("trifecta_probabilities", [])[:10],
                    },
                },
            )
            saved += 1
    finally:
        session.close()
    return saved


def run_fetch_and_predict() -> List[Dict[str, Any]]:
    logger = _get_logger()
    logger.info("live prediction pipeline started")

    scraper = OfficialRaceScraper(delay_seconds=0.1, request_timeout=2, max_failures=3)
    predictor = XGBoostPredictor()

    try:
        historical = scraper.fetch_past_results(days=7)
        today_races = scraper.fetch_today_races()
        logger.info("fetched historical=%s today=%s", len(historical), len(today_races))

        predictor.fit(historical)
        predictions = predictor.predict_races(today_races)
        predictions.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)

        _save_intermediate(predictions)
        saved = _save_predictions_to_db(predictions)
        logger.info("saved predictions to db: %s", saved)
        return predictions
    except Exception as exc:
        logger.error("fetch_and_predict failed: %s", exc, exc_info=True)
        return []


def main() -> None:
    preds = run_fetch_and_predict()
    print(f"predictions: {len(preds)}")
    for pred in preds[:10]:
        tag = "★推奨" if pred.get("confidence", 0) >= 0.7 else ""
        order = "-".join(str(x) for x in pred.get("predicted_order", []))
        print(
            f"{pred.get('race_id')} {pred.get('venue')} {pred.get('race_number')}R "
            f"{order} conf={pred.get('confidence', 0):.2f} {tag}"
        )


if __name__ == "__main__":
    main()
