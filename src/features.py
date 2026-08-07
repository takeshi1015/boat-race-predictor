"""
Feature Engineering
Generates ML features from raw race data in data/all_races.csv
"""

import pandas as pd
import numpy as np
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_PATH = "data/all_races.csv"
FEATURE_PATH = "data/features.csv"


def load_race_data(path: str = DATA_PATH) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} が見つかりません。先に src/scraper.py を実行してください。"
        )
    df = pd.read_csv(path)
    logger.info("レースデータ読み込み: %d 件", len(df))
    return df


def encode_result_column(series: pd.Series) -> pd.Series:
    """Convert result column to numeric, treating non-numeric as NaN."""
    return pd.to_numeric(series, errors="coerce")


def build_venue_win_rates(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each venue compute the historical win rate for each lane (1-6).
    Returns a DataFrame indexed by venue_code with columns lane_1_win_rate ... lane_6_win_rate.
    """
    df = df.copy()
    df["result_1st"] = encode_result_column(df["result_1st"])

    records = []
    for venue_code, group in df.groupby("venue_code"):
        row = {"venue_code": venue_code}
        for lane in range(1, 7):
            wins = (group["result_1st"] == lane).sum()
            total = len(group)
            row[f"lane_{lane}_win_rate"] = wins / total if total > 0 else 1 / 6
        records.append(row)

    return pd.DataFrame(records).set_index("venue_code")


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construct feature matrix from raw race data.
    Each row represents one race entry (one lane at one race).
    """
    logger.info("特徴量生成開始")

    df = df.copy()
    df["result_1st"] = encode_result_column(df["result_1st"])
    df["result_2nd"] = encode_result_column(df["result_2nd"])
    df["result_3rd"] = encode_result_column(df["result_3rd"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "venue_code", "race_number"]).reset_index(drop=True)

    venue_win_rates = build_venue_win_rates(df)

    rows = []
    for _, race in df.iterrows():
        venue_code = race["venue_code"]
        venue_in_index = venue_code in venue_win_rates.index
        vwr = venue_win_rates.loc[venue_code] if venue_in_index else None

        for lane in range(1, 7):
            r1 = race["result_1st"]
            r2 = race["result_2nd"]
            r3 = race["result_3rd"]
            win = int(r1 == lane) if not pd.isna(r1) else 0
            place = int(
                (not pd.isna(r1) and r1 == lane)
                or (not pd.isna(r2) and r2 == lane)
                or (not pd.isna(r3) and r3 == lane)
            )

            lane_win_rate = vwr[f"lane_{lane}_win_rate"] if vwr is not None else 1 / 6

            rows.append({
                "date": race["date"],
                "venue_code": venue_code,
                "race_number": race["race_number"],
                "lane": lane,
                # Features
                "lane_win_rate": lane_win_rate,
                "lane_position": lane,
                "is_inner_lane": int(lane <= 2),
                "is_outer_lane": int(lane >= 5),
                "venue_race_num": race["race_number"] / 12.0,
                # Labels
                "win": win,
                "place": place,
            })

    features_df = pd.DataFrame(rows)
    logger.info("特徴量生成完了: %d 行, %d 列", len(features_df), len(features_df.columns))
    return features_df


def save_features(df: pd.DataFrame, path: str = FEATURE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    logger.info("特徴量保存: %s", path)


def get_feature_columns() -> list:
    return [
        "lane_win_rate",
        "lane_position",
        "is_inner_lane",
        "is_outer_lane",
        "venue_race_num",
    ]


def main():
    logger.info("=" * 50)
    logger.info("特徴量エンジニアリング開始")
    logger.info("=" * 50)
    df = load_race_data()
    features = build_features(df)
    save_features(features)
    logger.info("特徴量エンジニアリング完了")
    return features


if __name__ == "__main__":
    main()
