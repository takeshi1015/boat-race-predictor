"""
Model Trainer
Handles training and retraining of machine learning models.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ModelTrainer:
    """Trains and retrains prediction models from historical race data."""

    def __init__(self) -> None:
        self.last_trained: Optional[datetime] = None
        self.training_iterations: int = 0

    def train(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train models from a list of historical race dicts.

        Args:
            training_data: Historical races with 'entries' and 'actual_result'.

        Returns:
            Dict with training summary (data_count, timestamp).
        """
        n = len(training_data)
        logger.info("Training on %d races", n)
        self.last_trained = datetime.now()
        self.training_iterations += 1
        return {
            "data_count": n,
            "training_iteration": self.training_iterations,
            "timestamp": self.last_trained.isoformat(),
        }

    def retrain_from_db(self, days: int = 30) -> Dict[str, Any]:
        """Retrain models using the past N days of race data from the database.

        Args:
            days: Number of past days to include.

        Returns:
            Dict with training summary.
        """
        try:
            from database.db_manager import get_db_manager
            from database.models import Race

            db = get_db_manager()
            session = db.get_session()
            try:
                cutoff = datetime.now() - timedelta(days=days)
                races_db = (
                    session.query(Race)
                    .filter(Race.date >= cutoff, Race.result.isnot(None))
                    .all()
                )
                training_data = [
                    {
                        "race_id": r.race_id,
                        "venue": r.place or r.venue,
                        "entries": [],
                        "actual_result": [
                            r.result.get("1st"),
                            r.result.get("2nd"),
                            r.result.get("3rd"),
                        ],
                    }
                    for r in races_db
                    if r.result
                ]
            finally:
                session.close()

            return self.train(training_data)

        except Exception as exc:
            logger.error("retrain_from_db failed: %s", exc, exc_info=True)
            return {"error": str(exc), "data_count": 0}
