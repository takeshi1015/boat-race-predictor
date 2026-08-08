"""XGBoost predictor for live boat-race trifecta probabilities."""

from __future__ import annotations

import itertools
import logging
import os
from typing import Any, Dict, List

import numpy as np
from xgboost import XGBClassifier


def _get_logger() -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("predictor")
    logger.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith("predictor.log") for h in logger.handlers):
        handler = logging.FileHandler("logs/predictor.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger


class XGBoostPredictor:
    """Train on past 7-day races and predict today's trifecta probabilities."""

    def __init__(self):
        self.logger = _get_logger()
        self.model = XGBClassifier(
            n_estimators=60,
            max_depth=3,
            learning_rate=0.1,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
            n_jobs=1,
        )
        self.is_trained = False

    def fit(self, historical_races: List[Dict[str, Any]]) -> None:
        x_rows: List[List[float]] = []
        y_rows: List[int] = []

        for race in historical_races:
            result_order = race.get("result_order") or []
            if len(result_order) < 1:
                continue
            winner_lane = result_order[0]
            for entry in race.get("entries", []):
                x_rows.append(self._entry_features(entry, race))
                y_rows.append(1 if entry.get("lane") == winner_lane else 0)

        if len(x_rows) < 8 or len(set(y_rows)) < 2:
            self.logger.warning("insufficient training data for xgboost; fallback scoring will be used")
            self.is_trained = False
            return

        x_train = np.array(x_rows, dtype=float)
        y_train = np.array(y_rows, dtype=int)
        self.model.fit(x_train, y_train)
        self.is_trained = True

    def predict_races(self, races: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.predict_race(race) for race in races if race.get("entries")]

    def predict_race(self, race: Dict[str, Any]) -> Dict[str, Any]:
        entries = race.get("entries", [])
        if len(entries) < 3:
            return {
                "race_id": race.get("race_id", "unknown"),
                "venue": race.get("venue_code", ""),
                "race_number": race.get("race_number", 0),
                "predicted_order": [],
                "player_probabilities": [],
                "trifecta_probabilities": [],
                "confidence": 0.0,
            }

        probs = self._predict_player_probabilities(entries, race)
        player_probs = sorted(probs, key=lambda x: x["probability"], reverse=True)

        trifecta = self._calc_trifecta_probabilities(player_probs)
        confidence = 0.0
        if len(player_probs) >= 2:
            confidence = max(0.0, player_probs[0]["probability"] - player_probs[1]["probability"])

        return {
            "race_id": race.get("race_id", "unknown"),
            "venue": race.get("venue_code", ""),
            "race_number": race.get("race_number", 0),
            "predicted_order": [p["lane"] for p in player_probs[:3]],
            "player_probabilities": player_probs,
            "trifecta_probabilities": trifecta,
            "confidence": float(round(min(confidence, 1.0), 4)),
        }

    def _predict_player_probabilities(self, entries: List[Dict[str, Any]], race: Dict[str, Any]) -> List[Dict[str, Any]]:
        scores = []
        if self.is_trained:
            x = np.array([self._entry_features(entry, race) for entry in entries], dtype=float)
            model_scores = self.model.predict_proba(x)[:, 1]
            scores = model_scores.tolist()
        else:
            # fallback: use weighted feature score
            scores = [
                0.5 * float(entry.get("win_rate", 0.0))
                + 0.3 * float(entry.get("motor_rate", 0.0))
                + 0.2 * float(entry.get("venue_rate", 0.0))
                for entry in entries
            ]

        probabilities = self._softmax(scores)
        return [
            {
                "lane": int(entry.get("lane", idx + 1)),
                "player_id": str(entry.get("player_id", f"unknown_{idx+1}")),
                "probability": float(round(probabilities[idx], 6)),
            }
            for idx, entry in enumerate(entries)
        ]

    def _entry_features(self, entry: Dict[str, Any], race: Dict[str, Any]) -> List[float]:
        return [
            float(entry.get("win_rate", 0.0)),
            float(entry.get("motor_rate", 0.0)),
            float(entry.get("venue_rate", 0.0)),
            float(self._encode_weather(race.get("weather", "unknown"))),
            float(self._encode_water(race.get("water_surface", "unknown"))),
        ]

    def _calc_trifecta_probabilities(self, player_probs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        trifecta_raw: List[Dict[str, Any]] = []
        eps = 1e-9
        for a, b, c in itertools.permutations(player_probs, 3):
            p1 = a["probability"]
            p2 = b["probability"] / max(1.0 - p1, eps)
            p3 = c["probability"] / max(1.0 - p1 - b["probability"], eps)
            prob = max(0.0, p1 * p2 * p3)
            trifecta_raw.append(
                {
                    "combination": f"{a['lane']}-{b['lane']}-{c['lane']}",
                    "probability": prob,
                }
            )

        total = sum(item["probability"] for item in trifecta_raw) or 1.0
        normalized = [
            {
                "combination": item["combination"],
                "probability": float(round(item["probability"] / total, 6)),
            }
            for item in trifecta_raw
        ]
        normalized.sort(key=lambda x: x["probability"], reverse=True)
        return normalized

    @staticmethod
    def _softmax(scores: List[float]) -> np.ndarray:
        if not scores:
            return np.array([], dtype=float)
        arr = np.array(scores, dtype=float)
        arr = arr - np.max(arr)
        exp = np.exp(arr)
        den = np.sum(exp)
        if den <= 0:
            return np.full_like(exp, 1.0 / len(exp))
        return exp / den

    @staticmethod
    def _encode_weather(weather: str) -> int:
        return {"sunny": 0, "cloudy": 1, "rainy": 2, "unknown": 3}.get(str(weather).lower(), 3)

    @staticmethod
    def _encode_water(water: str) -> int:
        return {"calm": 0, "slight": 1, "moderate": 2, "rough": 3, "unknown": 4}.get(str(water).lower(), 4)
