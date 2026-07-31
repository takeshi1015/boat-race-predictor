"""
アンサンブルモデル
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List

import config
from utils.logger import setup_logger
from utils.venue_manager import VenueManager

logger = setup_logger(__name__)

# ボートレースの購入締め切り時間（レース開始の何分前まで購入可能か）
RACE_TICKET_CUTOFF_MINUTES = 10


def _is_race_purchasable(race_datetime: datetime) -> bool:
    """レースが現在購入可能か判定。"""
    now = datetime.now()
    cutoff_time = race_datetime - timedelta(minutes=RACE_TICKET_CUTOFF_MINUTES)
    return now <= cutoff_time


class EnsembleModel:
    """複数モデルのアンサンブル予測"""

    def __init__(self):
        self.model_weights = {
            "statistical": 0.35,
            "ml": 0.40,
            "rule_based": 0.25,
        }
        self.weights_file = os.path.join(config.OUTPUTS_DIR, "model_weights.json")
        self.venue_manager = VenueManager()
        self._load_weights()
        self._normalize_weights()
        logger.info("アンサンブルモデルを初期化")

    def predict_today(self):
        """当日の予測を実行"""
        logger.info("当日予測を開始")
        return self._predict_for_period("today")

    def predict_tomorrow(self):
        """翌日の予測を実行"""
        logger.info("翌日予測を開始")
        return self._predict_for_period("tomorrow")

    def _predict_for_period(self, period: str) -> list:
        """指定期間のレースを予測"""
        try:
            races = self._get_race_data(period)
            logger.info(f"{period}のレースデータ取得: {len(races)}件")
            if not races:
                logger.warning(f"{period}のレースデータがありません")
                return []

            now = datetime.now()
            if period == "today":
                operating_venues = set(self.venue_manager.get_operating_venues_today() or [])
            else:
                operating_venues = set(self.venue_manager.get_operating_venues_tomorrow() or [])

            if not operating_venues:
                operating_venues = set(self._extract_venues_from_races(races))

            logger.info(f"現在時刻: {now.strftime('%H:%M:%S')}")
            logger.info(f"{period}の開催レース場: {sorted(list(operating_venues))}")

            predictions = []
            for race in races:
                venue_name = getattr(race, "place", None) or getattr(race, "venue", None)
                if venue_name not in operating_venues:
                    logger.debug(f"❌ {venue_name} {race.race_number}R - 非開催のため除外")
                    continue

                race_datetime = getattr(race, "date", None)
                if period == "today" and race_datetime and not _is_race_purchasable(race_datetime):
                    logger.debug(
                        f"❌ {venue_name} {race.race_number}R {race_datetime.strftime('%H:%M')} - 購入締切後のため除外"
                    )
                    continue

                pred = self._predict_race(race, period)
                if pred:
                    predictions.append(pred)

            self._save_predictions(predictions, period)
            logger.info(f"{period}予測完了: {len(predictions)}件")
            return predictions
        except Exception as e:
            logger.error(f"{period}予測エラー: {e}", exc_info=True)
            return []

    def _extract_venues_from_races(self, races: list) -> list:
        """レースデータから開催中のレース場を抽出"""
        venues = set()
        for race in races:
            venue_name = getattr(race, "place", None) or getattr(race, "venue", None)
            if venue_name:
                venues.add(venue_name)
        return sorted(list(venues))

    def _predict_race(self, race, period: str) -> dict:
        """個別レースの予測"""
        try:
            weather = getattr(race, "weather", None) or "sunny"
            water_cond = getattr(race, "water_condition", None) or "calm"
            hour = getattr(race, "start_time_hour", None) or 12
            race_number = getattr(race, "race_number", 1)
            place = getattr(race, "place", None) or getattr(race, "venue", "不明")
            race_datetime = getattr(race, "date", datetime.now())

            scores = self._build_lane_scores(
                weather=weather,
                water_condition=water_cond,
                hour=hour,
                race_number=race_number,
                wind_speed=float(getattr(race, "wind_speed", 0.0) or 0.0),
                temperature=float(getattr(race, "temperature", 20.0) or 20.0),
            )

            ranked = sorted(range(6), key=lambda i: scores[i], reverse=True)
            predicted_order = [i + 1 for i in ranked[:3]]
            confidence = self._confidence_from_scores(scores, weather, water_cond)

            reason = f"{place} {race_number}R: 1号艇軸を基本に、気象・水面条件で補正"
            if weather == "rainy" or water_cond == "rough":
                reason += "（荒天補正あり）"

            date_str = race_datetime.isoformat() if hasattr(race_datetime, "isoformat") else str(race_datetime)
            is_purchasable = True if period != "today" else _is_race_purchasable(race_datetime)

            return {
                "race_id": getattr(race, "race_id", "unknown"),
                "date": date_str,
                "place": place,
                "venue": place,
                "race_number": race_number,
                "predicted_order": predicted_order,
                "confidence": round(confidence, 3),
                "reason": reason,
                "is_purchasable": is_purchasable,
                "ticket_cutoff_minutes": RACE_TICKET_CUTOFF_MINUTES,
                "methods_used": ["statistical", "ml", "rule_based"],
                "model_weights": {k: round(v, 3) for k, v in self.model_weights.items()},
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"レース予測エラー: {e}", exc_info=True)
            return None

    def _build_lane_scores(
        self,
        weather: str,
        water_condition: str,
        hour: int,
        race_number: int,
        wind_speed: float,
        temperature: float,
    ) -> List[float]:
        base = [1.00, 0.86, 0.74, 0.62, 0.52, 0.44]
        stat_scores = base[:]
        if weather == "rainy":
            stat_scores = [0.95, 0.88, 0.78, 0.66, 0.56, 0.48]
        if water_condition in ("moderate", "rough"):
            stat_scores = [s - 0.05 for s in stat_scores]
            stat_scores[1] += 0.02
            stat_scores[2] += 0.03

        ml_bias = (16 - abs(13 - hour)) / 16.0
        temp_bias = max(min((temperature - 20.0) / 20.0, 0.3), -0.3)
        wind_penalty = min(wind_speed / 20.0, 0.25)
        ml_scores = [
            0.78 + ml_bias * 0.10 - wind_penalty * 0.30 + temp_bias * 0.05,
            0.74 + ml_bias * 0.08 - wind_penalty * 0.20 + temp_bias * 0.04,
            0.71 + ml_bias * 0.07 - wind_penalty * 0.15 + temp_bias * 0.03,
            0.68 + ml_bias * 0.06 - wind_penalty * 0.12 + temp_bias * 0.02,
            0.65 + ml_bias * 0.05 - wind_penalty * 0.10 + temp_bias * 0.02,
            0.62 + ml_bias * 0.04 - wind_penalty * 0.08 + temp_bias * 0.01,
        ]

        cycle = race_number % 6
        rule_scores = [0.55, 0.53, 0.51, 0.49, 0.47, 0.45]
        if cycle == 0:
            rule_scores[2] += 0.05
            rule_scores[1] += 0.03
        elif cycle in (1, 2):
            rule_scores[0] += 0.06
        else:
            rule_scores[1] += 0.04
            rule_scores[2] += 0.02

        final_scores = []
        for i in range(6):
            score = (
                stat_scores[i] * self.model_weights["statistical"]
                + ml_scores[i] * self.model_weights["ml"]
                + rule_scores[i] * self.model_weights["rule_based"]
            )
            final_scores.append(score)
        return final_scores

    def _confidence_from_scores(self, scores: List[float], weather: str, water_condition: str) -> float:
        ranked = sorted(scores, reverse=True)
        if len(ranked) < 3:
            return 0.3
        spread = max(ranked[0] - ranked[2], 0.0)
        condition_penalty = 0.0
        if weather == "rainy":
            condition_penalty += 0.05
        if water_condition in ("moderate", "rough"):
            condition_penalty += 0.04
        confidence = 0.55 + min(spread * 1.5, 0.35) - condition_penalty
        return min(max(confidence, 0.3), 0.95)

    def _save_predictions(self, predictions: List[dict], period: str) -> None:
        if not predictions:
            return
        try:
            from database.db_manager import get_db_manager

            db = get_db_manager()
            session = db.get_session()
            try:
                for pred in predictions:
                    pred_data = {
                        "race_id": pred["race_id"],
                        "prediction_date": datetime.now(),
                        "prediction_type": period,
                        "predicted_order": pred["predicted_order"],
                        "confidence": float(pred["confidence"]),
                        "estimated_odds": round(self._estimate_odds(pred["predicted_order"]), 2),
                        "model_version": "ensemble-2.0",
                        "methods_used": pred.get("methods_used", []),
                    }
                    db.add_prediction(session, pred_data)
            finally:
                session.close()
        except Exception as e:
            logger.error(f"予測保存エラー: {e}", exc_info=True)

    def _estimate_odds(self, predicted_order: List[int]) -> float:
        if not predicted_order or len(predicted_order) < 3:
            return 12.0
        base = 16.0
        for lane in predicted_order[:3]:
            if lane <= 2:
                base *= 0.88
            elif lane >= 5:
                base *= 1.12
            else:
                base *= 1.0
        return max(base, 3.0)

    def _get_race_data(self, period: str) -> list:
        """データベースからレースデータを取得"""
        try:
            from database.db_manager import get_db_manager

            db = get_db_manager()
            session = db.get_session()
            try:
                target_date = datetime.now() if period == "today" else datetime.now() + timedelta(days=1)
                races = db.get_races_by_date(session, target_date)
                return list(races)
            finally:
                session.close()
        except Exception as e:
            logger.error(f"レースデータ取得エラー: {e}", exc_info=True)
            return []

    def evaluate_performance(self) -> dict:
        """実レース結果に基づいてパフォーマンスを評価"""
        try:
            from database.db_manager import get_db_manager
            from database.models import Prediction, Race

            db = get_db_manager()
            session = db.get_session()
            try:
                db.sync_prediction_results_from_races(session, days=60)

                cutoff = datetime.now() - timedelta(days=30)
                predictions = session.query(Prediction).filter(
                    Prediction.prediction_date >= cutoff
                ).all()

                race_map = {
                    race.race_id: race
                    for race in session.query(Race).filter(Race.date >= cutoff).all()
                }

                evaluated = []
                for pred in predictions:
                    result = pred.result or {}
                    actual_order = result.get("actual_order")
                    if not isinstance(actual_order, list) or len(actual_order) < 3:
                        continue
                    predicted_order = pred.predicted_order or []
                    if not isinstance(predicted_order, list) or len(predicted_order) < 3:
                        continue
                    evaluated.append((pred, actual_order))

                total = len(evaluated)
                if total == 0:
                    return self._empty_metrics()

                trifecta_hits = sum(1 for pred, actual in evaluated if pred.result and pred.result.get("is_hit"))
                first_place_hits = sum(1 for pred, actual in evaluated if pred.predicted_order[0] == actual[0])
                total_payout = sum(float((pred.result or {}).get("actual_odds", 0.0)) for pred, _ in evaluated)

                trifecta_hit_rate = trifecta_hits / total
                first_place_hit_rate = first_place_hits / total
                recovery_rate = total_payout / total

                precision = trifecta_hit_rate
                recall = first_place_hit_rate
                f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

                venue_stats: Dict[str, Dict[str, float]] = {}
                time_stats: Dict[str, Dict[str, float]] = {"morning": {"total": 0, "hits": 0}, "midday": {"total": 0, "hits": 0}, "evening": {"total": 0, "hits": 0}}
                for pred, _ in evaluated:
                    race = race_map.get(pred.race_id)
                    venue = (race.place or race.venue) if race else "不明"
                    venue_stats.setdefault(venue, {"total": 0, "hits": 0})
                    venue_stats[venue]["total"] += 1
                    if pred.result and pred.result.get("is_hit"):
                        venue_stats[venue]["hits"] += 1

                    hour = getattr(race, "start_time_hour", 12) if race else 12
                    slot = "morning" if hour < 12 else ("midday" if hour < 17 else "evening")
                    time_stats[slot]["total"] += 1
                    if pred.result and pred.result.get("is_hit"):
                        time_stats[slot]["hits"] += 1

                venue_performance = {
                    k: round(v["hits"] / v["total"], 4) if v["total"] else 0.0
                    for k, v in venue_stats.items()
                }
                time_performance = {
                    k: round(v["hits"] / v["total"], 4) if v["total"] else 0.0
                    for k, v in time_stats.items()
                }

                return {
                    "accuracy": trifecta_hit_rate,
                    "precision": precision,
                    "recall": recall,
                    "f1_score": f1_score,
                    "first_place_hit_rate": first_place_hit_rate,
                    "trifecta_hit_rate": trifecta_hit_rate,
                    "recovery_rate": recovery_rate,
                    "total_predictions": total,
                    "hits": trifecta_hits,
                    "misses": total - trifecta_hits,
                    "venue_performance": venue_performance,
                    "time_slot_performance": time_performance,
                }
            finally:
                session.close()
        except Exception as e:
            logger.error(f"パフォーマンス評価エラー: {e}", exc_info=True)
            return self._empty_metrics()

    def retrain(self) -> dict:
        """実績に応じて重みを再調整して永続化"""
        try:
            metrics = self.evaluate_performance()
            total = int(metrics.get("total_predictions", 0))
            first_rate = float(metrics.get("first_place_hit_rate", 0.0))
            trifecta_rate = float(metrics.get("trifecta_hit_rate", 0.0))
            recovery = float(metrics.get("recovery_rate", 0.0))

            if total == 0:
                return {"学習データ数": 0, "メッセージ": "評価可能な実績データがありません"}

            if first_rate < 0.45:
                self.model_weights["statistical"] += 0.04
            if trifecta_rate < 0.25:
                self.model_weights["ml"] += 0.05
            if recovery < 1.0:
                self.model_weights["rule_based"] -= 0.03
            elif recovery > 1.4:
                self.model_weights["rule_based"] += 0.02

            self._normalize_weights()
            self._save_weights()

            logger.info(f"再学習完了: {total}件, 1着={first_rate:.1%}, 3連単={trifecta_rate:.1%}")
            return {
                "学習データ数": total,
                "1着的中率": f"{first_rate:.1%}",
                "3連単一致率": f"{trifecta_rate:.1%}",
                "回収率": round(recovery, 3),
                "更新後の重み": {k: round(v, 4) for k, v in self.model_weights.items()},
            }
        except Exception as e:
            logger.error(f"再学習エラー: {e}", exc_info=True)
            return {"エラー": str(e)}

    def _load_weights(self) -> None:
        try:
            if not os.path.exists(self.weights_file):
                return
            with open(self.weights_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for key in ("statistical", "ml", "rule_based"):
                val = loaded.get(key)
                if isinstance(val, (int, float)):
                    self.model_weights[key] = float(val)
        except Exception as e:
            logger.warning(f"重み読み込み失敗: {e}")

    def _save_weights(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.weights_file), exist_ok=True)
            with open(self.weights_file, "w", encoding="utf-8") as f:
                json.dump(self.model_weights, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"重み保存失敗: {e}")

    def _normalize_weights(self) -> None:
        for key in list(self.model_weights.keys()):
            self.model_weights[key] = max(0.10, float(self.model_weights[key]))
        total = sum(self.model_weights.values()) or 1.0
        for key in list(self.model_weights.keys()):
            self.model_weights[key] = self.model_weights[key] / total

    def _empty_metrics(self) -> dict:
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "first_place_hit_rate": 0.0,
            "trifecta_hit_rate": 0.0,
            "recovery_rate": 0.0,
            "total_predictions": 0,
            "hits": 0,
            "misses": 0,
            "venue_performance": {},
            "time_slot_performance": {},
        }


if __name__ == "__main__":
    model = EnsembleModel()
    today_pred = model.predict_today()
    print(f"当日予測: {len(today_pred)}件")
