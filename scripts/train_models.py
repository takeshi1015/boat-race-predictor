"""実レースデータから統計+機械学習モデルを学習するスクリプト。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db_manager
from database.models import Race
from models.ml_ensemble import MLEnsembleModel
from models.statistical_model import StatisticalRaceModel


def build_training_rows(days: int = 30) -> Tuple[np.ndarray, np.ndarray]:
    """Race.result から学習データ行列を作る。"""
    db = get_db_manager()
    session = db.get_session()
    cutoff = datetime.now() - timedelta(days=days)

    x_rows: List[List[float]] = []
    y_rows: List[int] = []

    try:
        races = session.query(Race).filter(Race.date >= cutoff).all()
        for race in races:
            payload = race.result or {}
            entries = payload.get("entries") or []
            order = payload.get("finish_order") or []
            if len(entries) < 3 or len(order) < 1:
                continue

            feature_vec: List[float] = []
            lanes = []
            for lane in range(1, 7):
                entry = next((e for e in entries if int(e.get("lane", 0)) == lane), {})
                feature_vec.extend(
                    [
                        float(entry.get("lane", lane)),
                        float(entry.get("motor_no") or 0),
                        float(race.wind_speed or 0),
                    ]
                )
                lanes.append(lane)

            winner_lane = int(order[0]) if int(order[0]) in lanes else None
            if winner_lane is None:
                continue

            x_rows.append(feature_vec)
            y_rows.append(winner_lane - 1)

    finally:
        session.close()

    if not x_rows:
        return np.empty((0, 18), dtype=float), np.empty((0,), dtype=int)

    return np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int)


def run_training(days: int = 30, output_dir: str = "models/artifacts") -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)

    x, y = build_training_rows(days=days)
    if len(x) < 10:
        return {"trained": False, "reason": "insufficient_training_data", "rows": int(len(x))}

    ensemble = MLEnsembleModel()
    ensemble.fit(x, y)
    cv = ensemble.cross_validate(x, y)

    stat_model = StatisticalRaceModel()

    joblib.dump(ensemble.rf, os.path.join(output_dir, "random_forest.joblib"))
    if ensemble.xgb is not None:
        joblib.dump(ensemble.xgb, os.path.join(output_dir, "xgboost.joblib"))
    joblib.dump(stat_model, os.path.join(output_dir, "statistical_model.joblib"))

    return {
        "trained": True,
        "rows": int(len(x)),
        "metrics": cv,
        "output_dir": output_dir,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train race prediction models")
    parser.add_argument("--days", type=int, default=30, help="過去何日分を使って学習するか")
    parser.add_argument("--output-dir", default="models/artifacts", help="モデル保存先")
    args = parser.parse_args()

    result = run_training(days=args.days, output_dir=args.output_dir)
    print(result)


if __name__ == "__main__":
    main()
