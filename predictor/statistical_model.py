"""
Statistical Prediction Model
Uses historical statistics and probability theory for boat race prediction.
"""

from typing import Any, Dict, List, Optional

import numpy as np

from predictor.base_model import BasePredictionModel
from utils.feature_engineer import FeatureEngineer
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Fraction retained by the house (deducted from probability-based payouts).
_HOUSE_TAKE = 0.25

# Weights used for the composite statistical score
_SCORE_WEIGHTS: Dict[str, float] = {
    "win_rate": 0.30,
    "place_rate": 0.15,
    "payoff_rate": 0.10,
    "avg_speed": 0.15,
    "recent_win_rate": 0.15,
    "boat_win_rate": 0.10,
    "engine_rate": 0.05,
}


class StatisticalModel(BasePredictionModel):
    """Statistical analysis-based prediction engine.

    Combines historical win/place rates, recent form, and boat/engine
    performance into a single composite score using weighted summation.
    Probabilities are estimated via score normalisation (softmax), and
    payouts are derived from the inverse of predicted probabilities.
    """

    def __init__(self) -> None:
        """Initialise the statistical model."""
        super().__init__(model_name="statistical_model", version="1.0")
        self._feature_engineer = FeatureEngineer()

    # ------------------------------------------------------------------
    # BasePredictionModel interface
    # ------------------------------------------------------------------

    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate predictions using statistical scoring.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result dictionary.
        """
        entries: List[Dict[str, Any]] = race_data.get("entries", [])
        if not entries:
            return self.empty_prediction()

        scored = sorted(self._compute_scores(entries), key=lambda x: x["score"], reverse=True)

        top3 = [item["id"] for item in scored[:3]]

        # Confidence is proportional to the gap between top-1 and top-3
        if len(scored) >= 3:
            gap = scored[0]["score"] - scored[2]["score"]
            confidence = min(gap / 50.0, 1.0)
        else:
            confidence = 0.0

        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": top3,
            "confidence": confidence,
            "details": {
                "method": "statistical_analysis",
                "scores": scored,
                "weights": _SCORE_WEIGHTS,
            },
        }

    def predict_winner(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the race winner.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result with 'winner' key.
        """
        result = self.predict(race_data)
        result["winner"] = result["prediction"][0] if result["prediction"] else None
        return result

    def predict_order(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the top-3 finishing order.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result with 'order' key.
        """
        result = self.predict(race_data)
        result["order"] = result["prediction"][:3]
        return result

    def predict_payout(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate expected payouts from predicted probabilities.

        The payout for a given bet type is estimated as the reciprocal of the
        predicted probability, adjusted by the house take (assumed 25%).

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result with 'payout' key mapping bet types to values.
        """
        result = self.predict_probability(race_data)
        probabilities = result.get("probabilities", {})

        if not probabilities:
            result["payout"] = {}
            return result

        values = list(probabilities.values())
        top_prob = max(values) if values else 0.0
        sorted_values = sorted(values, reverse=True)
        top_2_prob = (
            top_prob * sorted_values[1]
            if len(sorted_values) >= 2
            else 0.0
        )
        top_3_prob = (
            top_prob * sorted_values[1] * sorted_values[2]
            if len(sorted_values) >= 3
            else 0.0
        )

        house_take = _HOUSE_TAKE

        def _payout(prob: float) -> float:
            return round((1.0 - house_take) / prob, 1) if prob > 0 else 0.0

        result["payout"] = {
            "win": _payout(top_prob),
            "exacta": _payout(top_2_prob),
            "trifecta": _payout(top_3_prob),
        }
        return result

    def predict_probability(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate winning probability for each participant.

        Probabilities are produced by applying softmax to the raw composite
        scores, so they sum to 1.0 across all participants.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result with 'probabilities' key.
        """
        entries: List[Dict[str, Any]] = race_data.get("entries", [])
        if not entries:
            result = self.empty_prediction()
            result["probabilities"] = {}
            return result

        scored = self._compute_scores(entries)
        raw_scores = [item["score"] for item in scored]
        probs = self._scores_to_probabilities(raw_scores)

        probabilities = {
            item["id"]: round(prob, 4)
            for item, prob in zip(scored, probs)
        }

        result = self.predict(race_data)
        result["probabilities"] = probabilities
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_scores(
        self, entries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Compute composite statistical score for each entry.

        Args:
            entries: List of entry dictionaries.

        Returns:
            List of scored entry dictionaries with 'id' and 'score'.
        """
        scored = []
        for entry in entries:
            score = self._composite_score(entry)
            entry_id = entry.get("player_id") or entry.get("frame_number")
            scored.append({"id": entry_id, "score": score})
        return scored

    @staticmethod
    def _composite_score(entry: Dict[str, Any]) -> float:
        """Compute weighted composite score for a single entry.

        Args:
            entry: Entry dictionary with rider and boat statistics.

        Returns:
            Composite score (higher is better).
        """
        win_rate = float(entry.get("win_rate", 0.0))
        place_rate = float(entry.get("place_rate", 0.0))
        payoff_rate = float(entry.get("payoff_rate", 0.0))
        avg_speed_raw = float(entry.get("avg_speed", 0.0))
        avg_speed = min(avg_speed_raw / 10.0, 1.0)  # normalise to [0, 1]

        recent_results: List[str] = entry.get("recent_results", [])
        recent_win_rate = (
            sum(1 for r in recent_results if str(r) == "1") / len(recent_results)
            if recent_results
            else 0.0
        )

        boat_win_rate = float(entry.get("boat_win_rate", 0.0))
        engine_rate = float(entry.get("engine_rate", 0.0))

        score = (
            _SCORE_WEIGHTS["win_rate"] * win_rate * 100
            + _SCORE_WEIGHTS["place_rate"] * place_rate * 100
            + _SCORE_WEIGHTS["payoff_rate"] * payoff_rate * 100
            + _SCORE_WEIGHTS["avg_speed"] * avg_speed * 100
            + _SCORE_WEIGHTS["recent_win_rate"] * recent_win_rate * 100
            + _SCORE_WEIGHTS["boat_win_rate"] * boat_win_rate * 100
            + _SCORE_WEIGHTS["engine_rate"] * engine_rate * 100
        )

        return score
