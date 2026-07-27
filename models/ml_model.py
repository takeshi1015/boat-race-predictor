"""Lightweight ML-style scoring model (deterministic heuristic)."""

from typing import Dict


class MachineLearningModel:
    """Pseudo ensemble of NN/XGBoost/RF style scoring."""

    def score(self, race) -> Dict[int, float]:
        weather = (race.tide or "").lower()
        wind = float(race.wind_speed or 0)
        temp = float(race.temperature or 20)
        time_bias = {"morning": 0.03, "midday": 0.0, "evening": -0.01}.get(race.time_of_day, 0.0)

        scores: Dict[int, float] = {}
        for lane in range(1, 7):
            lane_base = max(0.01, 1.0 - (lane - 1) * 0.13)
            wind_penalty = (wind / 20.0) * (lane / 6.0)
            tide_bonus = 0.03 if weather == "high" and lane <= 2 else 0.0
            temp_bonus = 0.02 if 18 <= temp <= 28 else -0.01
            scores[lane] = lane_base - wind_penalty + tide_bonus + temp_bonus + time_bias
        return scores
