"""
結果検証と学習モジュール

終了したレースの予測を実結果と比較し、信頼度グループ別の的中率を分析して
モデルの重みを動的に調整する。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


def verify_predictions() -> Dict[str, int]:
    """
    終了したレースの予測を実結果と比較して的中フラグを更新する。

    Returns:
        dict: {"verified": int, "hits": int, "misses": int}
    """
    logger.info("[learning] 予測検証を開始")
    try:
        from database.db_manager import get_db_manager
        from database.models import Prediction

        db = get_db_manager()
        session = db.get_session()
        try:
            cutoff = datetime.now() - timedelta(hours=1)
            predictions = (
                session.query(Prediction)
                .filter(
                    Prediction.prediction_date <= cutoff,
                    Prediction.result.is_(None),
                )
                .all()
            )

            verified = hits = misses = 0
            for pred in predictions:
                race_result = db.get_race_result(session, pred.race_id)
                if race_result is None:
                    continue

                actual_order = [
                    race_result.first_place,
                    race_result.second_place,
                    race_result.third_place,
                ]
                predicted_order = pred.predicted_order or []

                is_hit = actual_order == predicted_order[:3]
                payoff = 0
                if is_hit and race_result.payoff_trifecta:
                    payoff = race_result.payoff_trifecta

                pred.result = {
                    "is_hit": is_hit,
                    "actual_order": actual_order,
                    "actual_odds": payoff,
                }
                verified += 1
                if is_hit:
                    hits += 1
                else:
                    misses += 1

            session.commit()
            logger.info(f"[learning] 検証完了: {verified}件 (的中 {hits}件 / 外れ {misses}件)")
            return {"verified": verified, "hits": hits, "misses": misses}
        finally:
            session.close()
    except Exception as exc:
        logger.error(f"[learning] 予測検証エラー: {exc}", exc_info=True)
        return {"verified": 0, "hits": 0, "misses": 0}


def calculate_accuracy_by_confidence() -> Dict[str, float]:
    """
    信頼度グループ別の的中率を算出する。

    Returns:
        dict: グループ名 → 的中率
        例: {"50-60%": 0.10, "60-70%": 0.15, ..., "90%+": 0.35}
    """
    logger.info("[learning] 信頼度グループ別の的中率を計算")
    try:
        from database.db_manager import get_db_manager
        from database.models import Prediction

        db = get_db_manager()
        session = db.get_session()
        try:
            cutoff = datetime.now() - timedelta(days=30)
            predictions = (
                session.query(Prediction)
                .filter(
                    Prediction.prediction_date >= cutoff,
                    Prediction.result.isnot(None),
                )
                .all()
            )

            buckets: Dict[str, list] = {
                "50-60%": [],
                "60-70%": [],
                "70-80%": [],
                "80-90%": [],
                "90%+": [],
            }

            for pred in predictions:
                c = pred.confidence or 0.0
                if c < 0.50:
                    continue
                is_hit = pred.result.get("is_hit", False) if pred.result else False
                if c < 0.60:
                    buckets["50-60%"].append(is_hit)
                elif c < 0.70:
                    buckets["60-70%"].append(is_hit)
                elif c < 0.80:
                    buckets["70-80%"].append(is_hit)
                elif c < 0.90:
                    buckets["80-90%"].append(is_hit)
                else:
                    buckets["90%+"].append(is_hit)

            result = {}
            for label, hits_list in buckets.items():
                if hits_list:
                    result[label] = round(sum(hits_list) / len(hits_list), 4)
                else:
                    result[label] = 0.0

            logger.info(f"[learning] グループ別的中率: {result}")
            return result
        finally:
            session.close()
    except Exception as exc:
        logger.error(f"[learning] 的中率計算エラー: {exc}", exc_info=True)
        return {}


def retrain_model() -> Dict[str, object]:
    """
    過去 30 日の的中データに基づいてモデル重みを動的に調整する。

    Returns:
        dict: 調整結果サマリー
    """
    logger.info("[learning] モデル再学習を開始")
    try:
        from models.ensemble_model import EnsembleModel

        model = EnsembleModel()
        result = model.retrain()
        logger.info(f"[learning] 再学習完了: {result}")
        return result
    except Exception as exc:
        logger.error(f"[learning] モデル再学習エラー: {exc}", exc_info=True)
        return {"エラー": str(exc)}
