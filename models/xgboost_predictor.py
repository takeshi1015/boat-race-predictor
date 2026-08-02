"""Minimal XGBoost-based predictor for live race pipelines."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - fallback when xgboost is unavailable
    XGBClassifier = None


class XGBoostPredictor:
    """Small self-contained predictor that ranks lanes with XGBoost."""

    def __init__(self) -> None:
        self.model = None
        if XGBClassifier is not None:
            self.model = XGBClassifier(
                n_estimators=8,
                max_depth=2,
                learning_rate=0.2,
                subsample=1.0,
                colsample_bytree=1.0,
                random_state=42,
                eval_metric="logloss",
            )
            train_x = np.array(
                [
                    [1, 0.58, 0.72, 0.55, 0.70, 0.12],
                    [2, 0.46, 0.61, 0.48, 0.60, 0.14],
                    [3, 0.40, 0.55, 0.44, 0.57, 0.16],
                    [4, 0.35, 0.49, 0.39, 0.51, 0.17],
                    [5, 0.31, 0.45, 0.34, 0.48, 0.18],
                    [6, 0.28, 0.41, 0.30, 0.45, 0.19],
                ]
            )
            train_y = np.array([1, 1, 0, 0, 0, 0])
            self.model.fit(train_x, train_y)

    def _entry_features(self, entry: Dict[str, Any]) -> List[float]:
        return [
            float(entry.get("frame_number", 6)),
            float(entry.get("win_rate", 0.0)),
            float(entry.get("place_rate", 0.0)),
            float(entry.get("boat_win_rate", 0.0)),
            float(entry.get("engine_rate", 0.0)),
            float(entry.get("avg_start_timing", 0.2)),
        ]

    def _score_entry(self, entry: Dict[str, Any]) -> float:
        features = np.array([self._entry_features(entry)])
        if self.model is not None:
            return float(self.model.predict_proba(features)[0][1])

        frame_number = float(entry.get("frame_number", 6))
        return max(0.05, 0.8 - (frame_number * 0.08))

    def predict(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        entries = race_data.get("entries", [])
        ranked = sorted(
            (
                {
                    "frame_number": int(entry.get("frame_number", 0)),
                    "score": self._score_entry(entry),
                }
                for entry in entries
            ),
            key=lambda item: item["score"],
            reverse=True,
        )
        top_scores = [item["score"] for item in ranked[:3]]
        confidence = sum(top_scores) / len(top_scores) if top_scores else 0.0

        return {
            "model": "xgboost",
            "prediction": [item["frame_number"] for item in ranked[:3]],
            "confidence": round(min(confidence, 0.95), 2),
            "details": {"scores": ranked},
        }
