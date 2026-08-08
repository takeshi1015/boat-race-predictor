"""統計分析ベースの実運用向け予測モデル。"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev
from typing import Any, Dict, List


@dataclass(frozen=True)
class StatisticalWeights:
    recent_win_rate: float = 0.30
    motor_recent_rate: float = 0.25
    venue_rate: float = 0.20
    lane_bias: float = 0.15
    weather_water_score: float = 0.10


class StatisticalRaceModel:
    """統計量から 0-100 スコア・信頼度を算出する。"""

    def __init__(self, weights: StatisticalWeights | None = None) -> None:
        self.weights = weights or StatisticalWeights()

    def score_entries(self, race_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        entries = race_data.get("entries", [])
        if not entries:
            return []

        weather_factor = self._weather_water_factor(race_data)
        scored: List[Dict[str, Any]] = []
        for entry in entries:
            lane = int(entry.get("lane") or entry.get("frame_number") or 6)
            score = (
                self.weights.recent_win_rate * self._clip(entry.get("recent_5_win_rate", 0.0))
                + self.weights.motor_recent_rate * self._clip(entry.get("motor_recent_10_rate", 0.0))
                + self.weights.venue_rate * self._clip(entry.get("venue_win_rate", 0.0))
                + self.weights.lane_bias * self._lane_bias(lane)
                + self.weights.weather_water_score * weather_factor
            ) * 100.0

            scored.append(
                {
                    "player_id": entry.get("player_id"),
                    "lane": lane,
                    "score": round(max(0.0, min(score, 100.0)), 2),
                }
            )

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        scored = self.score_entries(race_data)
        if not scored:
            return {"prediction": [], "confidence": 0.0, "scores": []}

        top3 = [item["player_id"] for item in scored[:3]]
        values = [item["score"] for item in scored]
        dispersion = pstdev(values) if len(values) > 1 else 0.0
        confidence = self._confidence_from_dispersion(dispersion)

        probs = self._softmax(values)
        for idx, item in enumerate(scored):
            item["hit_probability"] = round(probs[idx], 4)

        return {
            "prediction": top3,
            "confidence": round(confidence, 4),
            "scores": scored,
        }

    @staticmethod
    def _clip(value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(numeric, 1.0))

    @staticmethod
    def _lane_bias(lane: int) -> float:
        lane_scores = {1: 1.0, 2: 0.88, 3: 0.78, 4: 0.68, 5: 0.58, 6: 0.50}
        return lane_scores.get(lane, 0.45)

    @staticmethod
    def _weather_water_factor(race_data: Dict[str, Any]) -> float:
        weather = str(race_data.get("weather", "")).lower()
        water = str(race_data.get("water_condition", "")).lower()

        weather_score = {"sunny": 1.0, "cloudy": 0.8, "rainy": 0.55}.get(weather, 0.7)
        water_score = {"calm": 1.0, "slight": 0.82, "moderate": 0.65, "rough": 0.45}.get(water, 0.7)
        return (weather_score + water_score) / 2.0

    @staticmethod
    def _confidence_from_dispersion(dispersion: float) -> float:
        # スコア分散が大きいほど上位と下位の差が明確 = 信頼度高
        raw = dispersion / 22.0
        return max(0.0, min(raw, 1.0))

    @staticmethod
    def _softmax(values: List[float]) -> List[float]:
        if not values:
            return []
        max_val = max(values)
        exps = [pow(2.718281828, v - max_val) for v in values]
        total = sum(exps)
        if total == 0:
            return [0.0 for _ in values]
        return [v / total for v in exps]
