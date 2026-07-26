"""Statistical learning model for race-condition based scoring."""

from collections import defaultdict
from typing import Dict, Iterable


class StatisticalLearningModel:
    """Learn lane tendency from historical results."""

    def __init__(self):
        self._stats = defaultdict(lambda: defaultdict(lambda: {"wins": 0, "total": 0}))

    def learn(self, races: Iterable):
        for race in races:
            result = race.result or {}
            winner = int(result.get("1st", 0) or 0)
            key = self._condition_key(race)
            for lane in range(1, 7):
                self._stats[key][lane]["total"] += 1
                if lane == winner:
                    self._stats[key][lane]["wins"] += 1

    def score(self, race) -> Dict[int, float]:
        key = self._condition_key(race)
        lane_stats = self._stats.get(key, {})
        scores = {}
        for lane in range(1, 7):
            lane_data = lane_stats.get(lane, {"wins": 0, "total": 0})
            total = max(lane_data["total"], 1)
            # Baseline favors inside lane a little when no history exists.
            baseline = max(0.0, 0.20 - ((lane - 1) * 0.02))
            scores[lane] = (lane_data["wins"] / total) + baseline
        return scores

    @staticmethod
    def _condition_key(race) -> str:
        return f"{(race.wind_speed or 0)//3}:{race.water_surface or 'unknown'}:{race.time_of_day or 'unknown'}"
