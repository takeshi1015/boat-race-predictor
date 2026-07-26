"""Q-learning style reinforcement adjustments for lane scores."""

from collections import defaultdict
from typing import Dict


class ReinforcementModel:
    """Maintain lane rewards by condition and apply score adjustments."""

    def __init__(self):
        self._q = defaultdict(lambda: defaultdict(float))
        self.alpha = 0.15

    def adjust(self, race, scores: Dict[int, float]) -> Dict[int, float]:
        key = self._state_key(race)
        adjusted = dict(scores)
        for lane in range(1, 7):
            adjusted[lane] = adjusted.get(lane, 0.0) + self._q[key][lane]
        return adjusted

    def learn(self, race, recommended_order, actual_winner: int):
        key = self._state_key(race)
        for lane in recommended_order[:3]:
            reward = 1.0 if int(lane) == int(actual_winner) else -0.3
            self._q[key][int(lane)] = self._q[key][int(lane)] + self.alpha * (
                reward - self._q[key][int(lane)]
            )

    @staticmethod
    def _state_key(race) -> str:
        return f"{race.water_surface or 'unknown'}:{race.time_of_day or 'unknown'}:{int(race.wind_speed or 0)//2}"
