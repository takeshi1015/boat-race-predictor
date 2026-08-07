"""
Predictor
Loads trained models and generates race predictions.
"""

import os
import pickle
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MODEL_DIR = "models"
FEATURE_COLUMNS = [
    "lane_win_rate",
    "lane_position",
    "is_inner_lane",
    "is_outer_lane",
    "venue_race_num",
]


def load_models(model_dir: str = MODEL_DIR) -> dict:
    """Load all pickled models from model_dir.

    Note: Only load models from a trusted, access-controlled directory.
    Pickle deserialization can execute arbitrary code if the files are tampered with.
    """
    if not os.path.isdir(model_dir) or not os.listdir(model_dir):
        raise FileNotFoundError(
            f"{model_dir} にモデルが見つかりません。先に src/train_models.py を実行してください。"
        )
    models = {}
    for fname in os.listdir(model_dir):
        if fname.endswith(".pkl"):
            name = fname[:-4]
            with open(os.path.join(model_dir, fname), "rb") as f:
                models[name] = pickle.load(f)
    logger.info("モデル読み込み: %s", list(models.keys()))
    return models


def build_race_features(
    venue_code: int,
    race_number: int,
    lane_win_rates: Dict[int, float] | None = None,
) -> pd.DataFrame:
    """
    Build a feature DataFrame for one race (6 lanes).

    Parameters
    ----------
    venue_code : int
        Venue code (1-24).
    race_number : int
        Race number (1-12).
    lane_win_rates : dict, optional
        Pre-computed win rates per lane {1: 0.3, 2: 0.2, ...}.
        Defaults to uniform distribution.
    """
    if lane_win_rates is None:
        lane_win_rates = {lane: 1 / 6 for lane in range(1, 7)}

    rows = []
    for lane in range(1, 7):
        rows.append({
            "lane": lane,
            "lane_win_rate": lane_win_rates.get(lane, 1 / 6),
            "lane_position": lane,
            "is_inner_lane": int(lane <= 2),
            "is_outer_lane": int(lane >= 5),
            "venue_race_num": race_number / 12.0,
        })
    return pd.DataFrame(rows)


def predict_race(
    models: dict,
    venue_code: int,
    race_number: int,
    lane_win_rates: Dict[int, float] | None = None,
) -> List[Dict[str, Any]]:
    """
    Predict finish order for a single race.

    Returns a list of dicts sorted by predicted win probability (descending).
    """
    features_df = build_race_features(venue_code, race_number, lane_win_rates)
    X = features_df[FEATURE_COLUMNS].values.astype(np.float32)

    # Collect win-probability scores from each model
    all_probs = []
    for name, model in models.items():
        try:
            proba = model.predict_proba(X)
            # Index 1 = probability of win
            win_proba = proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]
            all_probs.append(win_proba)
        except Exception as exc:
            logger.warning("モデル %s の予測失敗: %s", name, exc)

    if not all_probs:
        # Fallback: uniform
        ensemble = np.ones(6) / 6
    else:
        ensemble = np.mean(all_probs, axis=0)

    # Build result list
    results = []
    for idx, row in enumerate(features_df.itertuples(index=False)):
        results.append({
            "lane": int(row.lane),
            "win_probability": float(ensemble[idx]),
        })
    results.sort(key=lambda r: r["win_probability"], reverse=True)

    # Assign predicted ranks
    for rank, r in enumerate(results, start=1):
        r["predicted_rank"] = rank

    return results


def format_prediction(
    venue_code: int,
    race_number: int,
    predictions: List[Dict[str, Any]],
) -> str:
    lines = [
        f"【予想】場コード {venue_code:02d} / {race_number}R",
        f"{'順位':>4}  {'艇番':>4}  {'勝率':>8}",
        "-" * 25,
    ]
    for p in predictions:
        lines.append(
            f"{p['predicted_rank']:>4}  {p['lane']:>4}  {p['win_probability']:>8.4f}"
        )
    return "\n".join(lines)


def main():
    logger.info("=" * 50)
    logger.info("予想生成開始")
    logger.info("=" * 50)

    models = load_models()

    # Demo: predict a few races
    demo_races = [
        (12, 1),   # 住之江 1R
        (22, 6),   # 福岡 6R
        (4, 12),   # 平和島 12R
    ]

    for venue_code, race_number in demo_races:
        preds = predict_race(models, venue_code, race_number)
        print()
        print(format_prediction(venue_code, race_number, preds))

    logger.info("予想生成完了")


if __name__ == "__main__":
    main()
