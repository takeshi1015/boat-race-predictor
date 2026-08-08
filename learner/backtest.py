"""
Backtest Module
Runs past race data through the prediction model and measures accuracy.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


class BacktestResult:
    """Container for backtest results."""

    def __init__(self) -> None:
        self.total_races: int = 0
        self.hits: int = 0
        self.total_payout: float = 0.0
        self.total_bet: float = 0.0
        self.by_confidence: Dict[str, Dict[str, Any]] = {}
        self.by_venue: Dict[str, Dict[str, Any]] = {}
        self.failures: List[Dict[str, Any]] = []
        self.successes: List[Dict[str, Any]] = []

    @property
    def hit_rate(self) -> float:
        """的中率 (hit rate)."""
        return self.hits / self.total_races if self.total_races > 0 else 0.0

    @property
    def recovery_rate(self) -> float:
        """回収率 (recovery rate = payout / bet)."""
        return self.total_payout / self.total_bet if self.total_bet > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_races": self.total_races,
            "hits": self.hits,
            "hit_rate": round(self.hit_rate, 4),
            "hit_rate_pct": f"{self.hit_rate:.1%}",
            "total_payout": round(self.total_payout, 2),
            "total_bet": round(self.total_bet, 2),
            "recovery_rate": round(self.recovery_rate, 4),
            "recovery_rate_pct": f"{self.recovery_rate:.1%}",
            "by_confidence": self.by_confidence,
            "by_venue": self.by_venue,
            "failure_count": len(self.failures),
            "success_count": len(self.successes),
        }


def _confidence_bucket(confidence: float) -> str:
    """Map a confidence value to a human-readable bucket label."""
    if confidence >= 0.80:
        return "high (≥80%)"
    if confidence >= 0.65:
        return "medium (65-80%)"
    if confidence >= 0.50:
        return "low (50-65%)"
    return "very_low (<50%)"


def backtest(
    model: Any,
    past_races: List[Dict[str, Any]],
    bet_amount: float = 100.0,
) -> BacktestResult:
    """Run the prediction model against past race data and measure accuracy.

    Each past race must include an 'actual_result' key with the true finishing
    order (list of player IDs / frame numbers for positions 1st–3rd).

    Args:
        model: Any prediction model object with a ``predict(race_data)`` method
            that returns a dict containing ``prediction`` (list) and
            ``confidence`` (float).
        past_races: List of historical race dicts.  Each must have:
            - 'entries': list of entry dicts (same format as live races)
            - 'actual_result': list of the top-3 finishing IDs/frame numbers
            Optional keys: 'venue', 'race_number', 'odds' (actual payout)
        bet_amount: Uniform bet size per race in yen (default 100).

    Returns:
        BacktestResult with hit rate, recovery rate, and detailed breakdowns.
    """
    result = BacktestResult()

    for race in past_races:
        actual: List[Any] = race.get("actual_result", [])
        if not actual or len(actual) < 3:
            logger.debug("Skipping race without valid actual_result: %s", race.get("race_id"))
            continue

        try:
            pred = model.predict(race)
        except Exception as exc:
            logger.warning("Prediction failed for race %s: %s", race.get("race_id"), exc)
            continue

        predicted: List[Any] = pred.get("prediction", [])
        confidence: float = float(pred.get("confidence", 0.0))
        venue: str = race.get("venue", "unknown")
        odds: float = float(race.get("odds", 10.0))

        is_hit = (len(predicted) >= 3 and list(predicted[:3]) == list(actual[:3]))

        result.total_races += 1
        result.total_bet += bet_amount
        if is_hit:
            result.hits += 1
            payout = bet_amount * odds
            result.total_payout += payout
        else:
            payout = 0.0

        # Track by confidence bucket
        bucket = _confidence_bucket(confidence)
        if bucket not in result.by_confidence:
            result.by_confidence[bucket] = {"total": 0, "hits": 0, "payout": 0.0, "bet": 0.0}
        result.by_confidence[bucket]["total"] += 1
        result.by_confidence[bucket]["bet"] += bet_amount
        if is_hit:
            result.by_confidence[bucket]["hits"] += 1
            result.by_confidence[bucket]["payout"] += payout

        # Track by venue
        if venue not in result.by_venue:
            result.by_venue[venue] = {"total": 0, "hits": 0, "payout": 0.0, "bet": 0.0}
        result.by_venue[venue]["total"] += 1
        result.by_venue[venue]["bet"] += bet_amount
        if is_hit:
            result.by_venue[venue]["hits"] += 1
            result.by_venue[venue]["payout"] += payout

        record = {
            "race_id": race.get("race_id", ""),
            "venue": venue,
            "race_number": race.get("race_number", 0),
            "predicted": predicted,
            "actual": actual,
            "confidence": round(confidence, 4),
            "odds": odds,
            "is_hit": is_hit,
            "payout": round(payout, 2),
        }
        if is_hit:
            result.successes.append(record)
        else:
            result.failures.append(record)

    # Compute derived hit/recovery rates inside each breakdown
    for bucket_data in result.by_confidence.values():
        t = bucket_data["total"]
        h = bucket_data["hits"]
        bucket_data["hit_rate"] = round(h / t, 4) if t > 0 else 0.0
        b = bucket_data["bet"]
        bucket_data["recovery_rate"] = round(bucket_data["payout"] / b, 4) if b > 0 else 0.0

    for venue_data in result.by_venue.values():
        t = venue_data["total"]
        h = venue_data["hits"]
        venue_data["hit_rate"] = round(h / t, 4) if t > 0 else 0.0
        b = venue_data["bet"]
        venue_data["recovery_rate"] = round(venue_data["payout"] / b, 4) if b > 0 else 0.0

    logger.info(
        "Backtest complete: %d races, %d hits, hit_rate=%.2f%%, recovery=%.2f%%",
        result.total_races,
        result.hits,
        result.hit_rate * 100,
        result.recovery_rate * 100,
    )
    return result


def run_backtest_from_db(
    model: Any,
    days: int = 30,
    bet_amount: float = 100.0,
) -> BacktestResult:
    """Load past races from the database and run backtest.

    Args:
        model: Prediction model with a ``predict`` method.
        days: Number of past days to include.
        bet_amount: Uniform bet size per race.

    Returns:
        BacktestResult.
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

            past_races: List[Dict[str, Any]] = []
            for r in races_db:
                result_data = r.result or {}
                actual = [
                    result_data.get("1st"),
                    result_data.get("2nd"),
                    result_data.get("3rd"),
                ]
                if None in actual:
                    continue
                past_races.append(
                    {
                        "race_id": r.race_id,
                        "venue": r.place or r.venue,
                        "race_number": r.race_number,
                        "weather": r.weather or "sunny",
                        "water_condition": r.water_condition or "calm",
                        "wind_speed": r.wind_speed or 0.0,
                        "entries": [],   # Entries not stored in Race; use empty list
                        "actual_result": actual,
                        "odds": 10.0,    # Default odds; actual odds not stored
                    }
                )
        finally:
            session.close()

        logger.info("Loaded %d past races from DB for backtest", len(past_races))
        return backtest(model, past_races, bet_amount=bet_amount)

    except Exception as exc:
        logger.error("run_backtest_from_db failed: %s", exc, exc_info=True)
        return BacktestResult()
