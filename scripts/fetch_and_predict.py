"""Fetch official races, run live predictions, and save them."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from database.db_manager import get_db_manager
from models.xgboost_predictor import XGBoostPredictor
from scrapers.official_scraper import OfficialRaceScraper
from utils.logger import logger


def _save_predictions(predictions: List[dict]) -> int:
    db = get_db_manager()
    session = db.get_session()
    saved_count = 0

    try:
        for prediction in predictions:
            db.add_prediction(
                session,
                {
                    "race_id": prediction["race_id"],
                    "prediction_date": datetime.now(),
                    "prediction_type": "high_confidence" if prediction["confidence"] >= 0.7 else "high_odds",
                    "predicted_order": prediction["predicted_order"],
                    "confidence": prediction["confidence"],
                    "estimated_odds": prediction.get("estimated_odds", 0.0),
                    "model_version": "xgboost-live-v1",
                    "methods_used": ["official_scraper", "xgboost"],
                    "result": None,
                },
            )
            saved_count += 1
    finally:
        session.close()

    return saved_count


def fetch_and_predict(now: datetime | None = None) -> Dict[str, int]:
    """Fetch current races, create predictions, and persist them."""
    reference_now = now or datetime.now()
    scraper = OfficialRaceScraper()
    predictor = XGBoostPredictor()

    today_races = scraper.fetch_today_races(now=reference_now)
    tomorrow_races = scraper.fetch_tomorrow_races(now=reference_now)

    saved_races = scraper.save_races(today_races) + scraper.save_races(tomorrow_races)

    prediction_rows: List[dict] = []
    for race in today_races + tomorrow_races:
        result = predictor.predict({"entries": _default_entries_for_race(), "race_id": race["race_id"]})
        prediction_rows.append(
            {
                "race_id": race["race_id"],
                "predicted_order": result["prediction"],
                "confidence": result["confidence"],
            }
        )

    saved_predictions = _save_predictions(prediction_rows)
    logger.info(
        "Live fetch completed: today=%d tomorrow=%d saved_races=%d saved_predictions=%d",
        len(today_races),
        len(tomorrow_races),
        saved_races,
        saved_predictions,
    )
    return {
        "today_races": len(today_races),
        "tomorrow_races": len(tomorrow_races),
        "saved_races": saved_races,
        "saved_predictions": saved_predictions,
    }


def _default_entries_for_race() -> List[dict]:
    """Return simple placeholder entries for ranking until real entry scraping exists."""
    return [
        {"frame_number": 1, "win_rate": 0.58, "place_rate": 0.72, "boat_win_rate": 0.55, "engine_rate": 0.70, "avg_start_timing": 0.12},
        {"frame_number": 2, "win_rate": 0.46, "place_rate": 0.61, "boat_win_rate": 0.48, "engine_rate": 0.60, "avg_start_timing": 0.14},
        {"frame_number": 3, "win_rate": 0.40, "place_rate": 0.55, "boat_win_rate": 0.44, "engine_rate": 0.57, "avg_start_timing": 0.16},
        {"frame_number": 4, "win_rate": 0.35, "place_rate": 0.49, "boat_win_rate": 0.39, "engine_rate": 0.51, "avg_start_timing": 0.17},
        {"frame_number": 5, "win_rate": 0.31, "place_rate": 0.45, "boat_win_rate": 0.34, "engine_rate": 0.48, "avg_start_timing": 0.18},
        {"frame_number": 6, "win_rate": 0.28, "place_rate": 0.41, "boat_win_rate": 0.30, "engine_rate": 0.45, "avg_start_timing": 0.19},
    ]


def main() -> None:
    summary = fetch_and_predict()
    print(summary)


if __name__ == "__main__":
    main()
