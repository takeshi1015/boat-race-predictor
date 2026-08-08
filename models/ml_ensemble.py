"""XGBoost / RandomForest のアンサンブル予測モデル。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - xgboost が未導入でも劣化運転
    XGBClassifier = None


@dataclass(frozen=True)
class EnsembleWeights:
    statistical: float = 0.30
    xgboost: float = 0.35
    random_forest: float = 0.35


class MLEnsembleModel:
    """3連単向けの簡易アンサンブルモデル。"""

    def __init__(self, weights: Optional[EnsembleWeights] = None, random_state: int = 42) -> None:
        self.weights = weights or EnsembleWeights()
        self.random_state = random_state
        self.rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=2,
            random_state=random_state,
        )
        self.xgb = (
            XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="multi:softprob",
                eval_metric="mlogloss",
                random_state=random_state,
            )
            if XGBClassifier is not None
            else None
        )
        self._n_classes = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        if len(x) == 0:
            raise ValueError("Training data is empty")

        self.rf.fit(x, y)
        if self.xgb is not None:
            self.xgb.fit(x, y)
        self._n_classes = len(np.unique(y))

    def predict_top3(self, x: np.ndarray, statistical_scores: Optional[np.ndarray] = None) -> Dict[str, List[int] | float]:
        if self._n_classes is None:
            raise RuntimeError("Model is not trained")

        rf_prob = self.rf.predict_proba(x)[0]
        xgb_prob = self.xgb.predict_proba(x)[0] if self.xgb is not None else rf_prob

        if statistical_scores is None:
            stat_prob = np.zeros_like(rf_prob)
        else:
            stat_prob = self._normalize(np.asarray(statistical_scores, dtype=float))

        merged = (
            self.weights.statistical * stat_prob
            + self.weights.xgboost * xgb_prob
            + self.weights.random_forest * rf_prob
        )
        merged = self._normalize(merged)

        top3 = np.argsort(merged)[::-1][:3] + 1
        confidence = float(np.max(merged))
        return {
            "prediction": top3.tolist(),
            "confidence": confidence,
            "probabilities": merged.tolist(),
        }

    def cross_validate(self, x: np.ndarray, y: np.ndarray, cv: int = 3) -> Dict[str, float]:
        rf_scores = cross_val_score(self.rf, x, y, cv=cv, scoring="accuracy")
        xgb_scores = (
            cross_val_score(self.xgb, x, y, cv=cv, scoring="accuracy")
            if self.xgb is not None
            else rf_scores
        )
        return {
            "rf_accuracy_mean": float(np.mean(rf_scores)),
            "xgb_accuracy_mean": float(np.mean(xgb_scores)),
        }

    @staticmethod
    def _normalize(arr: np.ndarray) -> np.ndarray:
        total = np.sum(arr)
        if total <= 0:
            return np.full_like(arr, fill_value=1.0 / len(arr), dtype=float)
        return arr / total
