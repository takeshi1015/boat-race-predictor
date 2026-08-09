"""
src/features.py

レースデータから機械学習用の特徴量を生成する。
"""

import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# 艇番が 1 の選手は平均的に有利（インコース）
COURSE_ADVANTAGE = {1: 0.50, 2: 0.15, 3: 0.12, 4: 0.10, 5: 0.08, 6: 0.05}


def load_race_data(csv_path: str = "data/all_races.csv") -> pd.DataFrame:
    """CSV からレースデータを読み込む。"""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"データファイルが見つかりません: {csv_path}")
    df = pd.read_csv(csv_path)
    logger.info("レースデータ読み込み: %d 件 (%s)", len(df), csv_path)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    生レースデータから特徴量を生成する。

    Returns:
        特徴量 DataFrame (各行 = 1艇)。
        ターゲットカラム: `win` (1着かどうか)。
    """
    df = df.copy()

    # 数値型へ変換
    for col in ["venue_code", "race_number", "result_1st", "result_2nd", "result_3rd"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["result_1st", "result_2nd", "result_3rd"]).reset_index(drop=True)

    # 各レースを 6 艇分に展開（ベクトル化）
    n_races = len(df)
    boat_numbers = np.tile(np.arange(1, 7), n_races)  # [1,2,3,4,5,6,1,2,...] length n_races*6

    repeated = df.loc[df.index.repeat(6)].reset_index(drop=True)
    repeated["boat_number"] = boat_numbers

    repeated["win"] = (repeated["result_1st"] == repeated["boat_number"]).astype(int)
    repeated["place"] = (
        (repeated["result_1st"] == repeated["boat_number"]) |
        (repeated["result_2nd"] == repeated["boat_number"])
    ).astype(int)

    repeated["course_advantage"] = repeated["boat_number"].map(COURSE_ADVANTAGE).fillna(0.05)
    repeated["is_inner_course"] = (repeated["boat_number"] <= 2).astype(int)
    repeated["boat_number_norm"] = repeated["boat_number"] / 6.0
    repeated["venue_code_norm"] = repeated["venue_code"] / 24.0
    repeated["race_number_norm"] = repeated["race_number"] / 12.0

    # 会場・艇番ごとの過去勝率を特徴量として追加
    repeated["historical_win_rate"] = repeated.groupby(["venue_code", "boat_number"])["win"].transform("mean")

    logger.info("特徴量生成完了: %d 行 x %d 列", len(repeated), len(repeated.columns))
    return repeated


def get_feature_columns() -> list[str]:
    """モデルに使用する特徴量カラム名を返す。"""
    return [
        "course_advantage",
        "is_inner_course",
        "boat_number_norm",
        "venue_code_norm",
        "race_number_norm",
        "historical_win_rate",
    ]


def prepare_dataset(csv_path: str = "data/all_races.csv") -> tuple[pd.DataFrame, pd.Series]:
    """
    CSV を読み込み、(X, y) を返す。

    Returns:
        X: 特徴量 DataFrame
        y: ターゲット (勝利フラグ)
    """
    df = load_race_data(csv_path)
    features_df = build_features(df)
    feature_cols = get_feature_columns()
    X = features_df[feature_cols].fillna(0)
    y = features_df["win"]
    return X, y


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    X, y = prepare_dataset()
    print("X shape:", X.shape)
    print("y value counts:\n", y.value_counts())
    print(X.head())


if __name__ == "__main__":
    main()
