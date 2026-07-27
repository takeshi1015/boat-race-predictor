"""Prediction performance analysis helpers."""

from collections import Counter
from typing import Dict, Iterable

TEMP_BUCKET_SIZE = 5


def _safe_first_winner(result: Dict) -> int:
    return int((result or {}).get("1st", 0) or 0)


def _safe_first_prediction(predicted_order) -> int:
    return int((predicted_order or [0])[0] or 0)


def calculate_hit_rate(predictions: Iterable, races_by_id: Dict[str, object]) -> float:
    predictions = list(predictions)
    if not predictions:
        return 0.0
    hits = 0
    for pred in predictions:
        race = races_by_id.get(pred.race_id)
        if not race or not race.result:
            continue
        actual_winner = _safe_first_winner(race.result)
        predicted_winner = _safe_first_prediction(pred.predicted_order)
        if actual_winner == predicted_winner:
            hits += 1
    return hits / len(predictions)


def analyze_miss_causes(predictions: Iterable, races_by_id: Dict[str, object]) -> Dict[str, int]:
    causes = Counter()
    for pred in predictions:
        race = races_by_id.get(pred.race_id)
        if not race or not race.result:
            continue
        actual_winner = _safe_first_winner(race.result)
        predicted_winner = _safe_first_prediction(pred.predicted_order)
        if actual_winner == predicted_winner:
            continue
        causes[f"weather_temp_{int(race.temperature or 0)//TEMP_BUCKET_SIZE*TEMP_BUCKET_SIZE}"] += 1
        causes[f"water_{race.water_surface or 'unknown'}"] += 1
        causes[f"time_{race.time_of_day or 'unknown'}"] += 1
    return dict(causes)
