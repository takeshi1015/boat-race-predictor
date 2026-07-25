"""
Base Prediction Model
Abstract base class that all prediction models must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BasePredictionModel(ABC):
    """Abstract base class for all boat race prediction models.

    Every concrete prediction model must inherit from this class and
    implement the abstract methods defined below.  The interface is
    intentionally minimal so that models can be composed by the
    ensemble predictor without knowing their internal implementation.

    Attributes:
        model_name: Human-readable name of the model.
        version: Version string for the model implementation.
    """

    def __init__(self, model_name: str, version: str = "1.0") -> None:
        """Initialise the base model.

        Args:
            model_name: Human-readable name of the model.
            version: Version string (default '1.0').
        """
        self.model_name = model_name
        self.version = version

    # ------------------------------------------------------------------
    # Abstract interface – must be implemented by subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate predictions for a single race.

        Args:
            race_data: Dictionary containing race information, conditions,
                and participant entries.

        Returns:
            Prediction result dictionary with at minimum the following keys:

            * ``model`` (str): Name of the model.
            * ``version`` (str): Model version.
            * ``prediction`` (list): Ordered list of predicted positions or
              participant identifiers (1st, 2nd, 3rd …).
            * ``confidence`` (float): Overall confidence in the prediction
              in the range [0.0, 1.0].
            * ``details`` (dict): Additional model-specific information.
        """

    @abstractmethod
    def predict_winner(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the winner (1st place) of a race.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result dictionary with ``winner`` key containing the
            predicted winner's identifier.
        """

    @abstractmethod
    def predict_order(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the top-3 finishing order.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result dictionary with ``order`` key containing an
            ordered list of the top-3 predicted identifiers.
        """

    @abstractmethod
    def predict_payout(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the expected payout / return for each bet type.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result dictionary with ``payout`` key mapping bet
            type names to expected return values.
        """

    @abstractmethod
    def predict_probability(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict winning probabilities for each participant.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result dictionary with ``probabilities`` key mapping
            participant identifiers to probability values in [0.0, 1.0].
        """

    # ------------------------------------------------------------------
    # Concrete helpers available to all subclasses
    # ------------------------------------------------------------------

    def empty_prediction(self) -> Dict[str, Any]:
        """Return a standardised empty prediction result.

        Returns:
            Dictionary with all required keys set to safe defaults.
        """
        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": [],
            "confidence": 0.0,
            "details": {},
        }

    @staticmethod
    def _scores_to_probabilities(scores: List[float]) -> List[float]:
        """Convert raw scores to a probability distribution via softmax.

        Args:
            scores: List of raw numerical scores (higher is better).

        Returns:
            List of probabilities that sum to 1.0 (or an empty list).
        """
        if not scores:
            return []

        import math

        max_score = max(scores)
        exps = [math.exp(s - max_score) for s in scores]
        total = sum(exps)
        return [e / total for e in exps]

    @staticmethod
    def _rank_to_positions(
        entries: List[Dict[str, Any]], scores: List[float]
    ) -> List[Any]:
        """Return entry identifiers ordered from highest to lowest score.

        Args:
            entries: List of entry dictionaries (each must have a unique key).
            scores: Corresponding score for each entry (same length).

        Returns:
            List of entry identifiers (``player_id`` or ``frame_number``)
            sorted by descending score.
        """
        paired = list(zip(scores, entries))
        paired.sort(key=lambda x: x[0], reverse=True)
        result = []
        for _, entry in paired:
            identifier = entry.get("player_id") or entry.get("frame_number")
            result.append(identifier)
        return result
