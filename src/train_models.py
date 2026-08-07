"""
src/train_models.py

XGBoost, LightGBM, RandomForest, ExtraTrees の4モデルを訓練して
models/ ディレクトリに保存する。
"""

import logging
import os
import pickle

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = "models"


def _load_xgboost():
    from xgboost import XGBClassifier  # noqa: PLC0415
    return XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )


def _load_lightgbm():
    from lightgbm import LGBMClassifier  # noqa: PLC0415
    return LGBMClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )


def build_model_definitions() -> dict:
    """モデル名 → インスタンス のマッピングを返す。"""
    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        ),
    }

    # XGBoost / LightGBM はインポートに失敗した場合はスキップ
    try:
        models["xgboost"] = _load_xgboost()
    except ImportError:
        logger.warning("xgboost がインストールされていないためスキップします")

    try:
        models["lightgbm"] = _load_lightgbm()
    except ImportError:
        logger.warning("lightgbm がインストールされていないためスキップします")

    return models


def train_and_save(csv_path: str = "data/all_races.csv") -> dict[str, float]:
    """
    全モデルを訓練して models/ に保存する。

    Returns:
        モデル名 → テスト AUC のマッピング。
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from features import prepare_dataset  # noqa: PLC0415

    logger.info("データセット準備中...")
    X, y = prepare_dataset(csv_path)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info("訓練: %d 件 / テスト: %d 件", len(X_train), len(X_test))

    os.makedirs(MODELS_DIR, exist_ok=True)
    results: dict[str, float] = {}

    for name, model in build_model_definitions().items():
        logger.info("モデル訓練中: %s", name)
        try:
            model.fit(X_train, y_train)

            y_pred = model.predict(X_test)
            acc = accuracy_score(y_test, y_pred)

            try:
                y_proba = model.predict_proba(X_test)[:, 1]
                auc = roc_auc_score(y_test, y_proba)
            except Exception:
                auc = acc

            logger.info("  %s  accuracy=%.4f  AUC=%.4f", name, acc, auc)
            results[name] = auc

            save_path = os.path.join(MODELS_DIR, f"{name}.pkl")
            with open(save_path, "wb") as f:
                pickle.dump(model, f)
            logger.info("  保存: %s", save_path)

        except Exception as exc:
            logger.error("  %s 訓練失敗: %s", name, exc)

    logger.info("=" * 40)
    logger.info("全モデル訓練完了")
    for name, auc in results.items():
        logger.info("  %-20s AUC = %.4f", name, auc)
    logger.info("=" * 40)
    return results


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main():
    results = train_and_save()
    print("訓練結果:", results)


if __name__ == "__main__":
    main()
