"""
Rule-Based Prediction Model
Implements expert-knowledge rules for boat race prediction.
"""

from typing import Any, Dict, List, Optional

from predictor.base_model import BasePredictionModel
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Fraction retained by the house (deducted from probability-based payouts).
_HOUSE_TAKE = 0.25


class RuleBasedModel(BasePredictionModel):
    """Rule-based prediction engine using domain expert knowledge.

    Scoring rules are applied in sequence to each race entry.  The rules
    are additive: each matching rule increases a candidate's score by a
    defined amount.  The final prediction is produced by ranking all
    candidates by their total score.

    Attributes:
        rules: Dictionary of rule parameters that govern scoring thresholds
            and weights.
    """

    _DEFAULT_RULES: Dict[str, float] = {
        "high_win_rate_threshold": 0.50,
        "high_win_rate_score": 50.0,
        "high_speed_threshold": 6.5,
        "high_speed_score": 30.0,
        "good_boat_win_rate_threshold": 0.45,
        "good_boat_score": 20.0,
        "good_recent_form_threshold": 0.60,
        "good_recent_form_score": 25.0,
        "inner_lane_max_position": 3,
        "inner_lane_score": 15.0,
        "top_rank_score": 20.0,
        "flying_penalty_per_count": 10.0,
        "good_engine_threshold": 0.60,
        "good_engine_score": 15.0,
        "good_start_timing_threshold": 0.15,
        "good_start_timing_score": 10.0,
    }

    def __init__(
        self, rules: Optional[Dict[str, float]] = None
    ) -> None:
        """Initialize the rule-based model.

        Args:
            rules: Optional override of the default rule parameters.
        """
        super().__init__(model_name="rule_based_model", version="1.0")
        self.rules = dict(self._DEFAULT_RULES)
        if rules:
            self.rules.update(rules)

    # ------------------------------------------------------------------
    # BasePredictionModel interface
    # ------------------------------------------------------------------

    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate predictions by applying all rules to each entry.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result dictionary.
        """
        entries: List[Dict[str, Any]] = race_data.get("entries", [])
        if not entries:
            return self.empty_prediction()

        scored = sorted(self._score_entries(entries, race_data), key=lambda x: x["score"], reverse=True)

        top3 = [item["id"] for item in scored[:3]]
        top_score = scored[0]["score"] if scored else 0.0
        confidence = min(top_score / 100.0, 1.0)

        return {
            "model": self.model_name,
            "version": self.version,
            "prediction": top3,
            "confidence": confidence,
            "details": {
                "method": "rule_based",
                "scores": scored,
                "rules_applied": list(self.rules.keys()),
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
        """Estimate expected payouts based on predicted order.

        Args:
            race_data: Race information dictionary.

        Returns:
            Prediction result with 'payout' key.
        """
        result = self.predict(race_data)
        confidence = result.get("confidence", 0.0)
        take_complement = 1.0 - _HOUSE_TAKE
        win_payout = round(take_complement / confidence, 1) if confidence > 0 else 0.0
        trifecta_payout = round(take_complement / (confidence ** 3), 0) if confidence > 0 else 0.0
        result["payout"] = {
            "win": win_payout,
            "trifecta": trifecta_payout,
        }
        return result

    def predict_probability(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert rule scores into a probability distribution.

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

        scored = self._score_entries(entries, race_data)
        total_score = sum(max(item["score"], 0.0) for item in scored) or 1.0
        probabilities = {
            item["id"]: round(max(item["score"], 0.0) / total_score, 4)
            for item in scored
        }

        result = self.predict(race_data)
        result["probabilities"] = probabilities
        return result

    # ------------------------------------------------------------------
    # Rule engine
    # ------------------------------------------------------------------

    def _score_entries(
        self,
        entries: List[Dict[str, Any]],
        race_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Apply all scoring rules to each entry.

        Args:
            entries: List of entry dictionaries.
            race_data: Race information dictionary.

        Returns:
            List of dictionaries with 'id', 'score', and 'rules_fired' keys.
        """
        scored = []
        for entry in entries:
            score, rules_fired = self._apply_rules(entry, race_data)
            entry_id = entry.get("player_id") or entry.get("frame_number")
            scored.append({"id": entry_id, "score": score, "rules_fired": rules_fired})
        return scored

    def _apply_rules(
        self,
        entry: Dict[str, Any],
        race_data: Dict[str, Any],
    ) -> tuple:
        """Apply individual scoring rules to a single entry.

        Args:
            entry: Entry dictionary.
            race_data: Race information dictionary.

        Returns:
            Tuple of (total_score, list_of_fired_rule_names).
        """
        score = 0.0
        rules_fired: List[str] = []

        # Rule: high win rate
        win_rate = float(entry.get("win_rate", 0.0))
        if win_rate >= self.rules["high_win_rate_threshold"]:
            score += self.rules["high_win_rate_score"]
            rules_fired.append("high_win_rate")

        # Rule: high exhibition speed
        avg_speed = float(entry.get("avg_speed", 0.0))
        if avg_speed >= self.rules["high_speed_threshold"]:
            score += self.rules["high_speed_score"]
            rules_fired.append("high_speed")

        # Rule: good boat win rate
        boat_win_rate = float(entry.get("boat_win_rate", 0.0))
        if boat_win_rate >= self.rules["good_boat_win_rate_threshold"]:
            score += self.rules["good_boat_score"]
            rules_fired.append("good_boat")

        # Rule: good recent form
        recent_results: List[str] = entry.get("recent_results", [])
        recent_wins = (
            sum(1 for r in recent_results if str(r) == "1") / len(recent_results)
            if recent_results
            else 0.0
        )
        if recent_wins >= self.rules["good_recent_form_threshold"]:
            score += self.rules["good_recent_form_score"]
            rules_fired.append("good_recent_form")

        # Rule: inside lane advantage
        position = int(entry.get("frame_number", entry.get("position", 9)))
        if position <= self.rules["inner_lane_max_position"]:
            score += self.rules["inner_lane_score"]
            rules_fired.append("inner_lane")

        # Rule: top-rank rider
        rank = entry.get("rank", "")
        if rank in ("A1", "A2"):
            score += self.rules["top_rank_score"]
            rules_fired.append("top_rank")

        # Rule: flying start penalty
        flying_count = int(entry.get("flying_count", 0))
        if flying_count > 0:
            score -= flying_count * self.rules["flying_penalty_per_count"]
            rules_fired.append("flying_penalty")

        # Rule: good engine
        engine_rate = float(entry.get("engine_rate", 0.0))
        if engine_rate >= self.rules["good_engine_threshold"]:
            score += self.rules["good_engine_score"]
            rules_fired.append("good_engine")

        # Rule: good start timing (small positive value is ideal)
        start_timing = abs(float(entry.get("avg_start_timing", 1.0)))
        if start_timing <= self.rules["good_start_timing_threshold"]:
            score += self.rules["good_start_timing_score"]
            rules_fired.append("good_start_timing")

        return score, rules_fired

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule_name: str, rule_value: float) -> None:
        """Add or update a rule parameter.

        Args:
            rule_name: Name of the rule parameter.
            rule_value: Numeric value for the rule.
        """
        self.rules[rule_name] = rule_value
        logger.info("Rule updated: %s = %s", rule_name, rule_value)
