"""
src/predictor.py

訓練済みモデルを使用してボートレースの着順予想と信頼度スコアを生成する。
"""

import logging
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import COURSE_ADVANTAGE, get_feature_columns  # noqa: E402

logger = logging.getLogger(__name__)

MODELS_DIR = "models"
MODEL_NAMES = ["xgboost", "lightgbm", "random_forest", "extra_trees"]


def _load_models() -> dict:
    """models/ から利用可能なモデルをすべてロードする。"""
    models = {}
    for name in MODEL_NAMES:
        path = os.path.join(MODELS_DIR, f"{name}.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    models[name] = pickle.load(f)
                logger.info("モデルロード: %s", name)
            except Exception as exc:
                logger.warning("モデルロード失敗 %s: %s", name, exc)
    return models


class BoatracePredictor:
    """訓練済みアンサンブルモデルで予想を生成する。"""

    def __init__(self):
        self.models = _load_models()
        if not self.models:
            logger.warning("ロード済みモデルなし。ルールベース予測にフォールバックします。")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict_race(
        self,
        venue_code: int,
        race_number: int,
        n_boats: int = 6,
    ) -> dict:
        """
        1レースの着順予想を返す。

        Returns:
            {
                "venue_code": int,
                "race_number": int,
                "predictions": [{"boat": int, "win_prob": float, "confidence": str}, ...],
                "top3": [int, int, int],
                "confidence_score": float,
                "method": str,
            }
        """
        features = self._build_race_features(venue_code, race_number, n_boats)
        feature_cols = get_feature_columns()
        X = features[feature_cols].fillna(0)

        if self.models:
            win_probs = self._ensemble_predict(X)
            method = "ensemble"
        else:
            win_probs = self._rule_based_predict(n_boats)
            method = "rule_based"

        # 正規化
        total = sum(win_probs)
        if total > 0:
            win_probs = [p / total for p in win_probs]

        boat_probs = sorted(
            [{"boat": i + 1, "win_prob": round(p, 4)} for i, p in enumerate(win_probs)],
            key=lambda x: x["win_prob"],
            reverse=True,
        )

        for entry in boat_probs:
            entry["confidence"] = self._confidence_label(entry["win_prob"])

        top3 = [e["boat"] for e in boat_probs[:3]]
        confidence_score = round(boat_probs[0]["win_prob"], 4) if boat_probs else 0.0

        return {
            "venue_code": venue_code,
            "race_number": race_number,
            "predictions": boat_probs,
            "top3": top3,
            "confidence_score": confidence_score,
            "method": method,
        }

    def predict_today(self, venue_code: int, n_races: int = 12) -> list[dict]:
        """指定会場の全レースを予想する。"""
        return [self.predict_race(venue_code, r) for r in range(1, n_races + 1)]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_race_features(venue_code: int, race_number: int, n_boats: int) -> pd.DataFrame:
        rows = []
        for boat_no in range(1, n_boats + 1):
            rows.append(
                {
                    "boat_number": boat_no,
                    "course_advantage": COURSE_ADVANTAGE.get(boat_no, 0.05),
                    "is_inner_course": int(boat_no <= 2),
                    "boat_number_norm": boat_no / 6.0,
                    "venue_code_norm": venue_code / 24.0,
                    "race_number_norm": race_number / 12.0,
                    "historical_win_rate": COURSE_ADVANTAGE.get(boat_no, 0.05),
                }
            )
        return pd.DataFrame(rows)

    def _ensemble_predict(self, X: pd.DataFrame) -> list[float]:
        """各モデルの予測確率を平均する。"""
        proba_list = []
        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X)[:, 1]
                proba_list.append(proba)
            except Exception as exc:
                logger.debug("モデル %s 予測エラー: %s", name, exc)

        if not proba_list:
            return self._rule_based_predict(len(X))

        stacked = np.stack(proba_list, axis=0)
        return stacked.mean(axis=0).tolist()

    @staticmethod
    def _rule_based_predict(n_boats: int) -> list[float]:
        """インコース有利ルールによる代替予測。"""
        probs = [COURSE_ADVANTAGE.get(i + 1, 0.05) for i in range(n_boats)]
        return probs

    @staticmethod
    def _confidence_label(prob: float) -> str:
        if prob >= 0.35:
            return "高"
        if prob >= 0.20:
            return "中"
        return "低"


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    predictor = BoatracePredictor()
    result = predictor.predict_race(venue_code=3, race_number=1)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
