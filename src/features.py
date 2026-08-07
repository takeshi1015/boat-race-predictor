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

    df = df.dropna(subset=["result_1st", "result_2nd", "result_3rd"])

    # 各レースについて 6 艇分の行を展開する
    rows = []
    for _, race in df.iterrows():
        for boat_no in range(1, 7):
            win = int(race["result_1st"] == boat_no)
            place = int(race["result_1st"] == boat_no or race["result_2nd"] == boat_no)
            rows.append(
                {
                    "date": race.get("date", ""),
                    "venue_code": race["venue_code"],
                    "race_number": race["race_number"],
                    "boat_number": boat_no,
                    "course_advantage": COURSE_ADVANTAGE.get(boat_no, 0.05),
                    "is_inner_course": int(boat_no <= 2),
                    "boat_number_norm": boat_no / 6.0,
                    "venue_code_norm": race["venue_code"] / 24.0,
                    "race_number_norm": race["race_number"] / 12.0,
                    "win": win,
                    "place": place,
                }
            )

    features_df = pd.DataFrame(rows)

    # 会場・艇番ごとの過去勝率を特徴量として追加
    win_rate = (
        features_df.groupby(["venue_code", "boat_number"])["win"]
        .transform("mean")
        .rename("historical_win_rate")
    )
    features_df["historical_win_rate"] = win_rate

    logger.info("特徴量生成完了: %d 行 x %d 列", len(features_df), len(features_df.columns))
    return features_df


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
