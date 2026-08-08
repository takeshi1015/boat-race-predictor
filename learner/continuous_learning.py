"""
Continuous Learning Loop
Daily cycle: predict → collect results → measure accuracy → analyze failures
→ retrain model → deploy if improved.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ContinuousLearning:
    """Daily learning cycle for continuous improvement of prediction accuracy.

    Workflow:
      1. Fetch today's races and predict
      2. After results are available, compare with predictions
      3. Measure accuracy (的中率・回収率)
      4. Analyze failure patterns
      5. Retrain/adjust model weights
      6. Deploy if accuracy improved
    """

    HISTORY_FILE = "outputs/learning_history.json"

    def __init__(
        self,
        model: Any,
        min_improvement: float = 0.001,
        state_file: str = HISTORY_FILE,
    ) -> None:
        """
        Args:
            model: The prediction model (must have ``predict()`` and optionally
                ``retrain()`` methods).
            min_improvement: Minimum increase in hit rate required to deploy
                the retrained model.
            state_file: JSON file path for persisting learning history.
        """
        self.model = model
        self.min_improvement = min_improvement
        self.state_file = state_file

        self._history: List[Dict[str, Any]] = self._load_history()
        self._previous_accuracy: float = self._load_previous_accuracy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def daily_cycle(self) -> Dict[str, Any]:
        """Execute a full daily learning cycle.

        Returns:
            Summary dict describing what happened in this cycle.
        """
        cycle_start = datetime.now()
        logger.info("=== Daily learning cycle started: %s ===", cycle_start.isoformat())

        summary: Dict[str, Any] = {
            "date": cycle_start.date().isoformat(),
            "started_at": cycle_start.isoformat(),
        }

        # 1. Fetch today's races
        today_races = self._fetch_today_races()
        summary["races_today"] = len(today_races)
        logger.info("Step 1: Fetched %d races for today", len(today_races))

        # 2. Predict
        predictions = self._predict_races(today_races)
        summary["predictions_made"] = len(predictions)
        logger.info("Step 2: Made %d predictions", len(predictions))

        # 3. Fetch yesterday's results and compare
        results = self._fetch_yesterday_results()
        summary["results_collected"] = len(results)
        logger.info("Step 3: Collected %d results", len(results))

        # 4. Measure accuracy
        accuracy = self._measure_accuracy(predictions, results)
        summary["accuracy"] = accuracy
        logger.info(
            "Step 4: Accuracy — hit_rate=%.2f%%, recovery=%.2f%%",
            accuracy.get("hit_rate", 0) * 100,
            accuracy.get("recovery_rate", 0) * 100,
        )

        # 5. Analyze failures
        failures = self._build_failure_records(predictions, results)
        failure_analysis = self._analyze_failures(failures)
        summary["failure_analysis"] = failure_analysis
        logger.info(
            "Step 5: Failure analysis — top category: %s",
            failure_analysis.get("top_category"),
        )

        # 6. Retrain model
        retrain_result = self._retrain_model(failures)
        summary["retrain_result"] = retrain_result
        logger.info("Step 6: Retrain result: %s", retrain_result)

        # 7. Deploy if improved
        current_accuracy = accuracy.get("hit_rate", 0.0)
        deployed = self._maybe_deploy(current_accuracy)
        summary["deployed"] = deployed
        self._previous_accuracy = current_accuracy

        # Persist history
        summary["finished_at"] = datetime.now().isoformat()
        self._history.append(summary)
        self._save_history()

        logger.info("=== Daily cycle complete. Deployed: %s ===", deployed)
        return summary

    def get_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Return the learning history for the past N days.

        Args:
            days: Number of days of history to return.

        Returns:
            List of daily cycle summaries (most recent first).
        """
        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
        recent = [h for h in self._history if h.get("date", "") >= cutoff]
        return list(reversed(recent))

    def get_performance_trend(self) -> Dict[str, Any]:
        """Return the accuracy trend over the stored history.

        Returns:
            Dict with ``hit_rate_trend``, ``recovery_rate_trend``, and dates.
        """
        dates, hit_rates, recovery_rates = [], [], []
        for entry in self._history[-30:]:
            dates.append(entry.get("date", ""))
            acc = entry.get("accuracy", {})
            hit_rates.append(acc.get("hit_rate", 0.0))
            recovery_rates.append(acc.get("recovery_rate", 0.0))

        return {
            "dates": dates,
            "hit_rate_trend": hit_rates,
            "recovery_rate_trend": recovery_rates,
            "latest_hit_rate": hit_rates[-1] if hit_rates else 0.0,
            "latest_recovery_rate": recovery_rates[-1] if recovery_rates else 0.0,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_today_races(self) -> List[Dict[str, Any]]:
        """Fetch today's race schedule from the database."""
        try:
            from database.db_manager import get_db_manager
            db = get_db_manager()
            session = db.get_session()
            try:
                races_db = db.get_races_by_date(session, datetime.now())
                races = []
                for r in races_db:
                    races.append(
                        {
                            "race_id": r.race_id,
                            "venue": r.place or r.venue,
                            "race_number": r.race_number,
                            "weather": r.weather or "sunny",
                            "water_condition": r.water_condition or "calm",
                            "wind_speed": r.wind_speed or 0.0,
                            "entries": [],
                        }
                    )
                return races
            finally:
                session.close()
        except Exception as exc:
            logger.warning("Could not fetch today's races from DB: %s", exc)
            return []

    def _predict_races(self, races: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run model predictions over a list of races."""
        predictions = []
        for race in races:
            try:
                pred = self.model.predict(race)
                pred["race_id"] = race.get("race_id", "")
                predictions.append(pred)
            except Exception as exc:
                logger.warning("Prediction failed for race %s: %s", race.get("race_id"), exc)
        return predictions

    def _fetch_yesterday_results(self) -> List[Dict[str, Any]]:
        """Fetch yesterday's race results from the database."""
        try:
            from database.db_manager import get_db_manager
            from database.models import Race
            db = get_db_manager()
            session = db.get_session()
            try:
                yesterday = datetime.now() - timedelta(days=1)
                races_db = db.get_races_by_date(session, yesterday)
                results = []
                for r in races_db:
                    if r.result:
                        results.append(
                            {
                                "race_id": r.race_id,
                                "actual_result": [
                                    r.result.get("1st"),
                                    r.result.get("2nd"),
                                    r.result.get("3rd"),
                                ],
                                "odds": r.result.get("odds", 10.0),
                            }
                        )
                return results
            finally:
                session.close()
        except Exception as exc:
            logger.warning("Could not fetch yesterday's results from DB: %s", exc)
            return []

    def _measure_accuracy(
        self,
        predictions: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compare predictions to results and compute accuracy metrics."""
        result_map = {r["race_id"]: r for r in results}
        hits = 0
        total = 0
        total_payout = 0.0
        total_bet = 0.0
        bet_per_race = 100.0

        for pred in predictions:
            race_id = pred.get("race_id", "")
            result = result_map.get(race_id)
            if not result:
                continue
            actual = result.get("actual_result", [])
            if not actual or None in actual:
                continue
            predicted = pred.get("prediction", [])
            total += 1
            total_bet += bet_per_race
            if list(predicted[:3]) == list(actual[:3]):
                hits += 1
                total_payout += bet_per_race * float(result.get("odds", 10.0))

        hit_rate = hits / total if total > 0 else 0.0
        recovery_rate = total_payout / total_bet if total_bet > 0 else 0.0

        return {
            "total_evaluated": total,
            "hits": hits,
            "hit_rate": round(hit_rate, 4),
            "recovery_rate": round(recovery_rate, 4),
        }

    def _build_failure_records(
        self,
        predictions: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build failure records by joining predictions with results."""
        result_map = {r["race_id"]: r for r in results}
        failures = []

        for pred in predictions:
            race_id = pred.get("race_id", "")
            result = result_map.get(race_id)
            if not result:
                continue
            actual = result.get("actual_result", [])
            predicted = pred.get("prediction", [])
            if list(predicted[:3]) != list(actual[:3]):
                failures.append(
                    {
                        "race_id": race_id,
                        "predicted": predicted,
                        "actual": actual,
                        "confidence": pred.get("confidence", 0.0),
                        "details": pred.get("details", {}),
                    }
                )
        return failures

    def _analyze_failures(
        self, failures: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Run failure analysis using the failure analyzer module."""
        try:
            from learner.failure_analyzer import analyze_failures
            return analyze_failures(failures)
        except Exception as exc:
            logger.warning("Failure analysis error: %s", exc)
            return {"total_failures": len(failures), "categories": {}, "improvement_plan": []}

    def _retrain_model(
        self, failures: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Retrain the model using the failure information.

        If the model exposes a ``retrain()`` method, call it.
        Otherwise return a no-op result.
        """
        try:
            if hasattr(self.model, "retrain"):
                return self.model.retrain()
            return {"status": "skipped", "reason": "model does not support retrain()"}
        except Exception as exc:
            logger.warning("Retrain failed: %s", exc)
            return {"status": "error", "detail": str(exc)}

    def _maybe_deploy(self, current_accuracy: float) -> bool:
        """Deploy the updated model if accuracy has improved.

        Args:
            current_accuracy: Hit rate from the latest evaluation.

        Returns:
            True if the model was deployed.
        """
        if current_accuracy > self._previous_accuracy + self.min_improvement:
            logger.info(
                "Accuracy improved: %.4f → %.4f. Deploying updated model.",
                self._previous_accuracy,
                current_accuracy,
            )
            return True
        logger.debug(
            "No deployment: current=%.4f, previous=%.4f (threshold +%.4f)",
            current_accuracy,
            self._previous_accuracy,
            self.min_improvement,
        )
        return False

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load persisted history from the state file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as fh:
                    return json.load(fh)
        except Exception as exc:
            logger.debug("Could not load history file %s: %s", self.state_file, exc)
        return []

    def _save_history(self) -> None:
        """Persist the learning history to the state file."""
        try:
            os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as fh:
                json.dump(self._history, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("Could not save history file %s: %s", self.state_file, exc)

    def _load_previous_accuracy(self) -> float:
        """Return the most recent recorded hit rate from history."""
        for entry in reversed(self._history):
            acc = entry.get("accuracy", {})
            hr = acc.get("hit_rate")
            if hr is not None:
                return float(hr)
        return 0.0
