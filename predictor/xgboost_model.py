"""
XGBoost Prediction Model
Gradient boosting model for high-accuracy boat race prediction.
"""

from typing import Any, Dict, List, Optional

import numpy as np

from predictor.base_model import BasePredictionModel
from utils.feature_engineer import FeatureEngineer
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Fraction retained by the house (deducted from probability-based payouts).
_HOUSE_TAKE = 0.25


def _softmax(scores: List[float]) -> List[float]:
    """Return a probability vector from a list of raw scores (softmax)."""
    arr = np.array(scores, dtype=float)
    shifted = arr - arr.max()
    exps = np.exp(shifted)
    return (exps / exps.sum()).tolist()


def _top_n_identifiers(
    entries: List[Dict[str, Any]], scores: List[float], n: int = 3
) -> List[Any]:
    """Return the identifiers of the top-n entries by score."""
    paired = sorted(zip(scores, entries), key=lambda x: x[0], reverse=True)
    result = []
    for _, entry in paired[:n]:
        result.append(entry.get("player_id") or entry.get("frame_number"))
    return result


class XGBoostModel(BasePredictionModel):
    """XGBoost-inspired gradient boosting model for boat race prediction.

    Implements gradient boosting through sequential residual fitting using
    additive weak learners.  In production, a trained XGBoost/LightGBM model
    would be loaded from disk.  This implementation simulates the behaviour
    with deterministic pseudo-trees based on feature importance weights.
    """

    N_ESTIMATORS = 50   # number of boosting rounds
    LEARNING_RATE = 0.1
    MAX_DEPTH = 4

    # Feature importance weights (approximate what XGBoost would learn)
    # Tuned based on boat race domain knowledge
    _FEATURE_IMPORTANCES = np.array(
        [
            0.22,   # win_rate            – most informative
            0.12,   # place_rate
            0.04,   # payoff_rate
            0.08,   # avg_start_timing    – start penalty matters
            0.16,   # recent_win_rate     – recent form
            0.04,   # is_top_rider
            0.06,   # flying_count        – risk factor
            0.07,   # engine_rate
            0.06,   # boat_win_rate
            0.04,   # boat_place_rate
            0.04,   # exhibition_time
            0.03,   # boat_start_timing
            0.01,   # wind_speed
            0.01,   # wave_height
            0.01,   # air_temperature
            0.01,   # water_temperature
            0.00,   # frame_number        – lane advantage handled separately
        ],
        dtype=float,
    )

    # Lane (frame_number) advantage for inner positions (1=best, 6=worst)
    _LANE_ADVANTAGE = {1: 0.15, 2: 0.10, 3: 0.05, 4: 0.00, 5: -0.05, 6: -0.10}

    def __init__(self) -> None:
        super().__init__(model_name="xgboost", version="1.0")
        self._feature_engineer = FeatureEngineer()
        # Normalize feature importance weights so they sum to 1
        total = self._FEATURE_IMPORTANCES.sum()
        if total > 0:
            self._weights = self._FEATURE_IMPORTANCES / total
        else:
            n = len(self._FEATURE_IMPORTANCES)
            self._weights = np.ones(n) / n

    # ------------------------------------------------------------------
    # BasePredictionModel interface
    # ------------------------------------------------------------------

    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a full prediction for the race.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result dictionary.
        """
        entries = race_data.get("entries", [])
        if not entries:
            return self.empty_prediction()

        matrix = self._feature_engineer.build_feature_matrix(race_data)
        if matrix is None:
            return self.empty_prediction()

        normed = self._feature_engineer.normalize(matrix)
        scores = self._boost(normed, entries)
        probabilities = _softmax(scores)
        top3 = _top_n_identifiers(entries, scores, n=3)
        confidence = float(max(probabilities)) if probabilities else 0.0

        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": top3,
            "confidence": confidence,
            "details": {
                "method": "gradient_boosting",
                "n_estimators": self.N_ESTIMATORS,
                "learning_rate": self.LEARNING_RATE,
                "feature_importances": dict(
                    zip(
                        [
                            "win_rate", "place_rate", "payoff_rate",
                            "avg_start_timing", "recent_win_rate", "is_top_rider",
                            "flying_count", "engine_rate", "boat_win_rate",
                            "boat_place_rate", "exhibition_time", "boat_start_timing",
                            "wind_speed", "wave_height", "air_temperature",
                            "water_temperature", "frame_number",
                        ],
                        self._weights.tolist(),
                    )
                ),
                "probabilities": dict(
                    zip(
                        [e.get("player_id") or e.get("frame_number") for e in entries],
                        probabilities,
                    )
                ),
            },
        }

    def predict_winner(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        result = self.predict(race_data)
        result["winner"] = result["prediction"][0] if result["prediction"] else None
        return result

    def predict_order(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        result = self.predict(race_data)
        result["order"] = result["prediction"][:3]
        return result

    def predict_payout(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        result = self.predict(race_data)
        probs = list(result.get("details", {}).get("probabilities", {}).values())
        top_prob = max(probs) if probs else 0.0
        win_payout = round((1.0 - _HOUSE_TAKE) / top_prob, 1) if top_prob > 0 else 0.0
        result["payout"] = {"win": win_payout}
        return result

    def predict_probability(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        result = self.predict(race_data)
        result["probabilities"] = result.get("details", {}).get("probabilities", {})
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _boost(self, normed: np.ndarray, entries: List[Dict[str, Any]]) -> List[float]:
        """Simulate gradient boosting over N_ESTIMATORS rounds.

        Each round computes a base score from a random feature subset weighted
        by feature importances, then adds the residual correction scaled by the
        learning rate.

        Args:
            normed: Normalised feature matrix (n_entries, n_features).
            entries: List of entry dictionaries (used for lane advantage).

        Returns:
            Final boosted score list per entry.
        """
        n_entries = normed.shape[0]
        scores = np.zeros(n_entries)

        # Initial prediction from feature importances
        base_score = normed @ self._weights
        scores += base_score

        # Gradient boosting rounds – simulate residual correction
        rng = np.random.default_rng(seed=7)
        for _ in range(self.N_ESTIMATORS):
            n_feat = normed.shape[1]
            n_sel = max(1, int(np.sqrt(n_feat)))
            selected = rng.choice(n_feat, size=n_sel, replace=False)
            w = self._weights[selected]
            w = w / w.sum() if w.sum() > 0 else np.ones(n_sel) / n_sel
            residual = normed[:, selected] @ w - scores / (scores.max() + 1e-9)
            scores += self.LEARNING_RATE * residual

        # Apply lane advantage bonus
        for i, entry in enumerate(entries):
            frame = int(entry.get("frame_number", 0))
            scores[i] += self._LANE_ADVANTAGE.get(frame, 0.0)

        return scores.tolist()
