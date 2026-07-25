"""
Machine Learning Prediction Models
Implements Logistic Regression, Random Forest, and Neural Network for
boat race prediction.
"""

from typing import Any, Dict, List, Optional

import numpy as np

from predictor.base_model import BasePredictionModel
from utils.feature_engineer import FeatureEngineer
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Fraction retained by the house (deducted from probability-based payouts).
_HOUSE_TAKE = 0.25


# ---------------------------------------------------------------------------
# Helpers shared by all ML models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Logistic Regression Predictor
# ---------------------------------------------------------------------------

class LogisticRegressionModel(BasePredictionModel):
    """Logistic Regression model for winner prediction.

    This implementation uses manually specified weights that approximate a
    trained logistic regression.  In production, weights would be loaded
    from a persisted trained model file.
    """

    def __init__(self) -> None:
        super().__init__(model_name="logistic_regression", version="1.0")
        self._feature_engineer = FeatureEngineer()
        # Weights correspond to FEATURE_* indices in feature_engineer.py
        self._weights = np.array(
            [
                0.30,   # win_rate
                0.15,   # place_rate
                0.05,   # payoff_rate
                -0.10,  # avg_start_timing (negative = earlier is better)
                0.20,   # recent_win_rate
                0.05,   # is_top_rider
                -0.08,  # flying_count
                0.10,   # engine_rate
                0.08,   # boat_win_rate
                0.05,   # boat_place_rate
                -0.05,  # exhibition_time (faster = better → lower value)
                -0.05,  # boat_start_timing
                -0.02,  # wind_speed
                -0.02,  # wave_height
                0.01,   # air_temperature
                0.01,   # water_temperature
                -0.05,  # frame_number (inner lane is advantageous)
            ],
            dtype=float,
        )

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
        scores, entries = self._compute_scores(race_data)
        if scores is None or entries is None:
            return self.empty_prediction()

        probabilities = _softmax(scores)
        top3 = _top_n_identifiers(entries, scores, n=3)
        confidence = float(max(probabilities))

        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": top3,
            "confidence": confidence,
            "details": {
                "method": "logistic_regression",
                "probabilities": dict(
                    zip(
                        [e.get("player_id") or e.get("frame_number") for e in entries],
                        probabilities,
                    )
                ),
            },
        }

    def predict_winner(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the winner of the race.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result with 'winner' key.
        """
        result = self.predict(race_data)
        winner = result["prediction"][0] if result["prediction"] else None
        result["winner"] = winner
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
        """Predict expected payout for common bet types.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result with 'payout' key.
        """
        result = self.predict(race_data)
        probs = list(
            result.get("details", {}).get("probabilities", {}).values()
        )
        if probs:
            top_prob = max(probs)
            win_payout = round((1.0 - _HOUSE_TAKE) / top_prob, 1) if top_prob > 0 else 0.0
        else:
            win_payout = 0.0
        result["payout"] = {"win": win_payout}
        return result

    def predict_probability(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict winning probability for each participant.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result with 'probabilities' key.
        """
        result = self.predict(race_data)
        result["probabilities"] = result.get("details", {}).get("probabilities", {})
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_scores(
        self, race_data: Dict[str, Any]
    ) -> tuple:
        """Compute raw logistic scores for each entry.

        Returns:
            Tuple of (scores_list, entries_list) or (None, None) on failure.
        """
        entries: List[Dict[str, Any]] = race_data.get("entries", [])
        if not entries:
            return None, None

        matrix = self._feature_engineer.build_feature_matrix(race_data)
        if matrix is None:
            return None, None

        normed = self._feature_engineer.normalize(matrix)
        scores = (normed @ self._weights).tolist()
        return scores, entries


# ---------------------------------------------------------------------------
# Random Forest Predictor
# ---------------------------------------------------------------------------

class RandomForestModel(BasePredictionModel):
    """Random Forest model for multi-outcome prediction.

    Simulates an ensemble of decision trees by sampling feature subsets
    and averaging their weighted votes.  In production, a trained
    scikit-learn RandomForestClassifier would be loaded instead.
    """

    N_TREES = 10  # number of simulated trees

    def __init__(self) -> None:
        super().__init__(model_name="random_forest", version="1.0")
        self._feature_engineer = FeatureEngineer()
        # Fixed random seed for reproducibility
        self._rng = np.random.default_rng(seed=42)

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
        vote_scores = self._ensemble_votes(normed)
        probabilities = _softmax(vote_scores)
        top3 = _top_n_identifiers(entries, vote_scores, n=3)
        confidence = float(max(probabilities)) if probabilities else 0.0

        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": top3,
            "confidence": confidence,
            "details": {
                "method": "random_forest",
                "n_trees": self.N_TREES,
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
        probs = list(
            result.get("details", {}).get("probabilities", {}).values()
        )
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

    def _ensemble_votes(self, normed: np.ndarray) -> List[float]:
        """Simulate N_TREES trees and average their weighted scores.

        Each tree randomly selects a subset of features and computes a
        weighted sum.  The final score is the mean across all trees.

        Args:
            normed: Normalised feature matrix (n_entries, n_features).

        Returns:
            List of aggregated score values.
        """
        n_features = normed.shape[1]
        accumulated = np.zeros(normed.shape[0])

        for _ in range(self.N_TREES):
            # Select a random subset of features (~sqrt(n_features))
            n_selected = max(1, int(np.sqrt(n_features)))
            selected = self._rng.choice(n_features, size=n_selected, replace=False)
            weights = self._rng.random(n_selected)
            weights /= weights.sum()
            accumulated += normed[:, selected] @ weights

        return (accumulated / self.N_TREES).tolist()


# ---------------------------------------------------------------------------
# Neural Network Predictor
# ---------------------------------------------------------------------------

class NeuralNetworkModel(BasePredictionModel):
    """Neural Network model for complex pattern recognition.

    Implements a simple two-layer feed-forward network with ReLU
    activations in pure NumPy.  In production, a trained Keras/TF model
    would be loaded instead.
    """

    def __init__(self) -> None:
        super().__init__(model_name="neural_network", version="1.0")
        self._feature_engineer = FeatureEngineer()
        # Initialise random weights (fixed seed for reproducibility)
        rng = np.random.default_rng(seed=0)
        n_in = 17   # FEATURE_DIM
        n_h1 = 32   # hidden layer 1 size
        n_h2 = 16   # hidden layer 2 size
        n_out = 1   # scalar output per entry

        self._W1 = rng.standard_normal((n_in, n_h1)) * 0.1
        self._b1 = np.zeros(n_h1)
        self._W2 = rng.standard_normal((n_h1, n_h2)) * 0.1
        self._b2 = np.zeros(n_h2)
        self._W3 = rng.standard_normal((n_h2, n_out)) * 0.1
        self._b3 = np.zeros(n_out)

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
        raw_scores = self._forward(normed).flatten().tolist()
        probabilities = _softmax(raw_scores)
        top3 = _top_n_identifiers(entries, raw_scores, n=3)
        confidence = float(max(probabilities)) if probabilities else 0.0

        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": top3,
            "confidence": confidence,
            "details": {
                "method": "neural_network",
                "architecture": "2-hidden-layer MLP",
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
        probs = list(
            result.get("details", {}).get("probabilities", {}).values()
        )
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

    @staticmethod
    def _relu(x: np.ndarray) -> np.ndarray:
        """Apply the ReLU activation function."""
        return np.maximum(0.0, x)

    def _forward(self, x: np.ndarray) -> np.ndarray:
        """Run the forward pass through the network.

        Args:
            x: Input matrix of shape (n_samples, n_features).

        Returns:
            Output array of shape (n_samples, 1).
        """
        h1 = self._relu(x @ self._W1 + self._b1)
        h2 = self._relu(h1 @ self._W2 + self._b2)
        out = h2 @ self._W3 + self._b3
        return out
