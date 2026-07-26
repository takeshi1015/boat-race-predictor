"""Prediction performance analysis helpers."""

from collections import Counter
from typing import Dict, Iterable


def calculate_hit_rate(predictions: Iterable, races_by_id: Dict[str, object]) -> float:
    predictions = list(predictions)
    if not predictions:
        return 0.0
    hits = 0
    for pred in predictions:
        race = races_by_id.get(pred.race_id)
        if not race or not race.result:
            continue
        actual_winner = int((race.result or {}).get("1st", 0) or 0)
        predicted_winner = int((pred.predicted_order or [0])[0] or 0)
        if actual_winner == predicted_winner:
            hits += 1
    return hits / len(predictions)


def analyze_miss_causes(predictions: Iterable, races_by_id: Dict[str, object]) -> Dict[str, int]:
    causes = Counter()
    for pred in predictions:
        race = races_by_id.get(pred.race_id)
        if not race or not race.result:
            continue
        actual_winner = int((race.result or {}).get("1st", 0) or 0)
        predicted_winner = int((pred.predicted_order or [0])[0] or 0)
        if actual_winner == predicted_winner:
            continue
        causes[f"weather_temp_{int(race.temperature or 0)//5*5}"] += 1
        causes[f"water_{race.water_surface or 'unknown'}"] += 1
        causes[f"time_{race.time_of_day or 'unknown'}"] += 1
    return dict(causes)
