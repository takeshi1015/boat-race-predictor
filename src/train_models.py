"""
Model Training
Trains multiple ML models and saves them to models/
"""

import os
import pickle
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

FEATURE_PATH = "data/features.csv"
MODEL_DIR = "models"


def load_features(path: str = FEATURE_PATH) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} が見つかりません。先に src/features.py を実行してください。"
        )
    df = pd.read_csv(path)
    logger.info("特徴量データ読み込み: %d 行", len(df))
    return df


FEATURE_COLUMNS = [
    "lane_win_rate",
    "lane_position",
    "is_inner_lane",
    "is_outer_lane",
    "venue_race_num",
]

MODELS = {
    "logistic_regression": Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=500, C=1.0, random_state=42)),
    ]),
    "random_forest": RandomForestClassifier(
        n_estimators=100, max_depth=6, random_state=42, n_jobs=-1
    ),
    "gradient_boosting": GradientBoostingClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
    ),
}


def train_all_models(df: pd.DataFrame) -> dict:
    """Train all models and return a dict of {name: model}."""
    df = df.dropna(subset=FEATURE_COLUMNS + ["win"])
    X = df[FEATURE_COLUMNS].values.astype(np.float32)
    y = df["win"].values.astype(int)

    logger.info("学習データ: %d 件 (陽性: %d)", len(y), y.sum())

    trained = {}
    for name, model in MODELS.items():
        logger.info("訓練中: %s", name)
        try:
            scores = cross_val_score(model, X, y, cv=3, scoring="roc_auc")
            logger.info(
                "  CV AUC: %.4f ± %.4f", scores.mean(), scores.std()
            )
            model.fit(X, y)
            trained[name] = model
            logger.info("  訓練完了: %s", name)
        except Exception as exc:
            logger.error("  訓練失敗 %s: %s", name, exc)

    return trained


def save_models(models: dict, model_dir: str = MODEL_DIR) -> None:
    os.makedirs(model_dir, exist_ok=True)
    for name, model in models.items():
        path = os.path.join(model_dir, f"{name}.pkl")
        with open(path, "wb") as f:
            pickle.dump(model, f)
        logger.info("保存: %s", path)


def load_models(model_dir: str = MODEL_DIR) -> dict:
    models = {}
    for fname in os.listdir(model_dir):
        if fname.endswith(".pkl"):
            name = fname[:-4]
            with open(os.path.join(model_dir, fname), "rb") as f:
                models[name] = pickle.load(f)
    logger.info("モデル読み込み: %s", list(models.keys()))
    return models


def main():
    logger.info("=" * 50)
    logger.info("モデル訓練開始")
    logger.info("=" * 50)
    df = load_features()
    models = train_all_models(df)
    save_models(models)
    logger.info("モデル訓練完了: %d モデルを保存", len(models))


if __name__ == "__main__":
    main()
