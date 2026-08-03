"""
Profit Optimizer
Selects races and bet sizes to maximize recovery rate (回収率).
"""

from typing import Any, Dict, List, Optional, Tuple

from utils.logger import setup_logger

logger = setup_logger(__name__)

# Default thresholds — can be overridden via constructor arguments
DEFAULT_MIN_CONFIDENCE = 0.70    # 信頼度 70% 以上
DEFAULT_MIN_EXPECTED_ODDS = 5.0  # 期待オッズ 5倍以上
DEFAULT_MIN_EXPECTED_VALUE = 1.0 # 期待値 > 1（= オッズ × 的中率 > 投資額）
DEFAULT_MAX_BET_FRACTION = 0.10  # 1レースの最大投資額は総資金の10%
DEFAULT_KELLY_FRACTION = 0.25    # ケリー基準の適用割合（過剰投資防止）


class ProfitOptimizer:
    """Selects races to bet on and determines optimal bet sizes.

    Implements the following decision logic:
      1. 信頼度 ``min_confidence`` 以上
      2. 期待オッズ ``min_expected_odds`` 倍以上
      3. 期待値 = オッズ × 的中率 > ``min_expected_value``（正の期待値）
      4. 資金管理: 1レースの最大投資額を制限
    """

    def __init__(
        self,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_expected_odds: float = DEFAULT_MIN_EXPECTED_ODDS,
        min_expected_value: float = DEFAULT_MIN_EXPECTED_VALUE,
        max_bet_fraction: float = DEFAULT_MAX_BET_FRACTION,
        kelly_fraction: float = DEFAULT_KELLY_FRACTION,
    ) -> None:
        """
        Args:
            min_confidence: Minimum confidence threshold to consider a race.
            min_expected_odds: Minimum estimated odds multiplier.
            min_expected_value: Minimum expected return ratio (EV).
            max_bet_fraction: Maximum fraction of total bankroll per race.
            kelly_fraction: Fraction of the Kelly bet to use (fractional Kelly).
        """
        self.min_confidence = min_confidence
        self.min_expected_odds = min_expected_odds
        self.min_expected_value = min_expected_value
        self.max_bet_fraction = max_bet_fraction
        self.kelly_fraction = kelly_fraction

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_races(
        self,
        predictions: List[Dict[str, Any]],
        bankroll: float = 10_000.0,
    ) -> List[Dict[str, Any]]:
        """Filter and rank races suitable for betting.

        Args:
            predictions: List of prediction dicts.  Each must have:
                - ``confidence`` (float 0–1)
                - ``estimated_odds`` (float, optional; defaults to 10.0)
                Optional: ``race_id``, ``place``, ``race_number``.
            bankroll: Total available funds (yen).

        Returns:
            List of selected race dicts with added ``recommended_bet``
            and ``expected_value`` fields, sorted by expected value
            descending.
        """
        selected: List[Dict[str, Any]] = []

        for pred in predictions:
            analysis = self.evaluate_race(pred, bankroll)
            if analysis["is_recommended"]:
                selected.append(analysis)

        # Sort by expected value descending
        selected.sort(key=lambda x: x["expected_value"], reverse=True)

        logger.info(
            "Race selection: %d / %d races recommended",
            len(selected),
            len(predictions),
        )
        return selected

    def evaluate_race(
        self,
        prediction: Dict[str, Any],
        bankroll: float = 10_000.0,
    ) -> Dict[str, Any]:
        """Evaluate a single race for bet worthiness.

        Args:
            prediction: Single prediction dict.
            bankroll: Total available funds (yen).

        Returns:
            Evaluation dict including ``is_recommended``, ``recommended_bet``,
            ``expected_value``, and the reasons for rejection if applicable.
        """
        confidence: float = float(prediction.get("confidence", 0.0))
        estimated_odds: float = float(prediction.get("estimated_odds", 10.0))

        expected_value = confidence * estimated_odds
        bet_size = self.optimize_bet_size(confidence, estimated_odds, bankroll)

        reasons_rejected: List[str] = []

        if confidence < self.min_confidence:
            reasons_rejected.append(
                f"信頼度 {confidence:.1%} < 最小値 {self.min_confidence:.0%}"
            )
        if estimated_odds < self.min_expected_odds:
            reasons_rejected.append(
                f"オッズ {estimated_odds:.1f}倍 < 最小値 {self.min_expected_odds:.0f}倍"
            )
        if expected_value < self.min_expected_value:
            reasons_rejected.append(
                f"期待値 {expected_value:.2f} < 最小値 {self.min_expected_value:.1f}"
            )

        is_recommended = len(reasons_rejected) == 0

        return {
            "race_id": prediction.get("race_id", ""),
            "place": prediction.get("place", prediction.get("venue", "")),
            "race_number": prediction.get("race_number", 0),
            "predicted_order": prediction.get("predicted_order", prediction.get("prediction", [])),
            "confidence": round(confidence, 4),
            "estimated_odds": round(estimated_odds, 2),
            "expected_value": round(expected_value, 4),
            "recommended_bet": round(bet_size, 0),
            "is_recommended": is_recommended,
            "reasons_rejected": reasons_rejected,
        }

    def optimize_bet_size(
        self,
        confidence: float,
        estimated_odds: float,
        bankroll: float = 10_000.0,
    ) -> float:
        """Determine the optimal bet size using fractional Kelly criterion.

        Kelly formula: f* = (b*p - q) / b
          where b = decimal_odds - 1, p = win probability, q = 1 - p.

        The result is capped at ``max_bet_fraction * bankroll`` to prevent
        ruin from model errors.

        Args:
            confidence: Estimated win probability (0–1).
            estimated_odds: Estimated payout multiplier (e.g. 10.0 = 10x).
            bankroll: Total available funds.

        Returns:
            Recommended bet amount in yen (minimum 0).
        """
        if confidence <= 0 or estimated_odds <= 1:
            return 0.0

        b = estimated_odds - 1.0   # net odds per unit stake
        p = confidence
        q = 1.0 - p

        kelly = (b * p - q) / b
        if kelly <= 0:
            return 0.0

        # Apply fractional Kelly to reduce variance
        fractional_kelly_bet = kelly * self.kelly_fraction * bankroll

        # Hard cap: never risk more than max_bet_fraction of bankroll per race
        max_bet = self.max_bet_fraction * bankroll

        return min(fractional_kelly_bet, max_bet)

    def generate_report(
        self,
        selected_races: List[Dict[str, Any]],
        bankroll: float,
    ) -> Dict[str, Any]:
        """Generate a summary report for the selected races.

        Args:
            selected_races: Output of :meth:`select_races`.
            bankroll: Current bankroll.

        Returns:
            Report dict with total bet, expected return, and per-race details.
        """
        total_bet = sum(r.get("recommended_bet", 0) for r in selected_races)
        weighted_ev = (
            sum(
                r.get("expected_value", 0) * r.get("recommended_bet", 0)
                for r in selected_races
            )
            / total_bet
            if total_bet > 0
            else 0.0
        )

        return {
            "total_races_recommended": len(selected_races),
            "total_bet": round(total_bet, 0),
            "bankroll_remaining": round(bankroll - total_bet, 0),
            "bankroll_utilization": round(total_bet / bankroll, 4) if bankroll > 0 else 0.0,
            "weighted_expected_value": round(weighted_ev, 4),
            "races": selected_races,
        }


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def select_races(
    predictions: List[Dict[str, Any]],
    bankroll: float = 10_000.0,
    **optimizer_kwargs: Any,
) -> List[Dict[str, Any]]:
    """Module-level convenience wrapper around :class:`ProfitOptimizer`.

    Args:
        predictions: List of prediction dicts.
        bankroll: Total available funds.
        **optimizer_kwargs: Forwarded to :class:`ProfitOptimizer`.

    Returns:
        Selected race list from :meth:`ProfitOptimizer.select_races`.
    """
    optimizer = ProfitOptimizer(**optimizer_kwargs)
    return optimizer.select_races(predictions, bankroll=bankroll)
