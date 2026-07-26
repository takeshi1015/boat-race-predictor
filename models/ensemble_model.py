"""アンサンブルモデル."""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import config
from database.db_manager import get_db_manager
from database.models import Prediction, Race
from models.ml_model import MachineLearningModel
from models.reinforcement_model import ReinforcementModel
from models.statistical_model import StatisticalLearningModel
from utils.analysis import analyze_miss_causes, calculate_hit_rate
from utils.logger import setup_logger

logger = setup_logger(__name__)


class EnsembleModel:
    """統計 + 機械学習 + 強化学習の簡易アンサンブル."""

    def __init__(self):
        self.db = get_db_manager()
        self.stat_model = StatisticalLearningModel()
        self.ml_model = MachineLearningModel()
        self.rl_model = ReinforcementModel()
        self.model_weights = {
            "neural_network": 0.40,
            "xgboost": 0.35,
            "random_forest": 0.25,
        }
        self._fit_statistical_model()
        logger.info("アンサンブルモデルを初期化")

    def predict_today(self) -> List[Dict]:
        return self._predict_for_date(datetime.now())

    def predict_tomorrow(self) -> List[Dict]:
        return self._predict_for_date(datetime.now() + timedelta(days=1))

    def _predict_for_date(self, target: datetime) -> List[Dict]:
        races = self._get_races_by_date(target)
        logger.info("%sのレースデータ取得: %d件", target.date().isoformat(), len(races))
        predictions = [self._predict_race(race) for race in races]
        return [p for p in predictions if p]

    def _predict_race(self, race: Race) -> Dict:
        stat_scores = self.stat_model.score(race)
        ml_scores = self.ml_model.score(race)
        nn = self._merge(stat_scores, ml_scores, self.model_weights["neural_network"])
        xgb = self._merge(ml_scores, stat_scores, self.model_weights["xgboost"])
        rf = self._merge(stat_scores, ml_scores, self.model_weights["random_forest"])

        final_scores = {}
        for lane in range(1, 7):
            final_scores[lane] = (
                nn.get(lane, 0.0) * self.model_weights["neural_network"]
                + xgb.get(lane, 0.0) * self.model_weights["xgboost"]
                + rf.get(lane, 0.0) * self.model_weights["random_forest"]
            )

        final_scores = self.rl_model.adjust(race, final_scores)
        order = sorted(final_scores, key=lambda lane: final_scores[lane], reverse=True)[:3]
        confidence = self._calc_confidence(final_scores, order)
        reason = self._build_reason(race, order[0], confidence)

        return {
            "race_id": race.race_id,
            "date": race.date.strftime("%Y-%m-%d"),
            "place": race.venue,
            "race_number": race.race_number,
            "prediction": order,
            "recommended_bet": "-".join(map(str, order)),
            "confidence": confidence,
            "purchasable": confidence >= config.CONFIDENCE_THRESHOLD,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }

    def evaluate_performance(self, days: int = 30) -> Dict:
        session = self.db.get_session()
        try:
            cutoff = datetime.now() - timedelta(days=days)
            preds = session.query(Prediction).filter(Prediction.prediction_date >= cutoff).all()
            races = {
                race.race_id: race
                for race in session.query(Race).filter(Race.date >= cutoff).all()
            }
            hit_rate = calculate_hit_rate(preds, races)
            miss_causes = analyze_miss_causes(preds, races)
            return {
                "days": days,
                "total_predictions": len(preds),
                "hit_rate": hit_rate,
                "miss_causes": miss_causes,
            }
        finally:
            session.close()

    def retrain(self, days: int = 30) -> Dict:
        session = self.db.get_session()
        try:
            cutoff = datetime.now() - timedelta(days=days)
            races = session.query(Race).filter(Race.date >= cutoff, Race.result.isnot(None)).all()
            self.stat_model.learn(races)

            recent = session.query(Prediction).filter(Prediction.prediction_date >= cutoff).all()
            for pred in recent:
                race = session.query(Race).filter_by(race_id=pred.race_id).first()
                if not race or not race.result:
                    continue
                actual = int((race.result or {}).get("1st", 0) or 0)
                recommended = (pred.predicted_order or [])[:3]
                self.rl_model.learn(race, recommended, actual)

            self._adjust_weights(session)
            session.commit()
            return {"learned_races": len(races), "updated_predictions": len(recent), "weights": self.model_weights}
        finally:
            session.close()

    def save_prediction_records(self, predictions: List[Dict], prediction_type: str) -> int:
        session = self.db.get_session()
        try:
            saved = 0
            for pred in predictions:
                record = Prediction(
                    race_id=pred["race_id"],
                    prediction_date=datetime.now(),
                    prediction_type=prediction_type,
                    predicted_order=pred["prediction"],
                    confidence=float(pred["confidence"]),
                    estimated_odds=round(max(1.0, 8.0 - pred["confidence"] * 5.0), 2),
                    model_version="ensemble-v1",
                    methods_used=["neural_network", "xgboost", "random_forest"],
                )
                session.add(record)
                saved += 1
            session.commit()
            return saved
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _fit_statistical_model(self):
        session = self.db.get_session()
        try:
            historical = session.query(Race).filter(Race.result.isnot(None)).all()
            self.stat_model.learn(historical)
        finally:
            session.close()

    def _get_races_by_date(self, date_obj: datetime) -> List[Race]:
        session = self.db.get_session()
        try:
            start = datetime.combine(date_obj.date(), datetime.min.time())
            end = datetime.combine(date_obj.date(), datetime.max.time())
            return session.query(Race).filter(Race.date.between(start, end)).order_by(Race.race_number).all()
        finally:
            session.close()

    @staticmethod
    def _merge(primary: Dict[int, float], secondary: Dict[int, float], ratio: float) -> Dict[int, float]:
        result = {}
        for lane in range(1, 7):
            result[lane] = primary.get(lane, 0.0) * ratio + secondary.get(lane, 0.0) * (1.0 - ratio)
        return result

    @staticmethod
    def _calc_confidence(scores: Dict[int, float], order: List[int]) -> float:
        if len(order) < 2:
            return 0.5
        top = scores[order[0]]
        second = scores[order[1]]
        spread = max(0.0, top - second)
        return min(0.7 + (spread * 1.5), 0.95)

    @staticmethod
    def _build_reason(race: Race, top_lane: int, confidence: float) -> str:
        weather = "晴天" if (race.temperature or 0) >= 24 else "曇天"
        water = "良好" if race.water_surface in ("calm", "slight") else "やや荒れ"
        when = {"morning": "午前", "midday": "日中", "evening": "夜間"}.get(race.time_of_day, "通常")
        return f"{weather}で水面状況は{water}。{when}レースで{top_lane}号艇優勢。信頼度{confidence:.2f}。"

    def _adjust_weights(self, session):
        cutoff = datetime.now() - timedelta(days=7)
        recent = session.query(Prediction).filter(Prediction.prediction_date >= cutoff).all()
        if not recent:
            return
        hit_rate = sum(1 for p in recent if (p.result or {}).get("is_hit")) / len(recent)
        if hit_rate < 0.4:
            self.model_weights["neural_network"] = max(0.25, self.model_weights["neural_network"] - 0.05)
            self.model_weights["xgboost"] = min(0.45, self.model_weights["xgboost"] + 0.03)
            self.model_weights["random_forest"] = min(0.35, self.model_weights["random_forest"] + 0.02)
        else:
            self.model_weights["neural_network"] = min(0.5, self.model_weights["neural_network"] + 0.02)
            self.model_weights["xgboost"] = max(0.25, self.model_weights["xgboost"] - 0.01)
            self.model_weights["random_forest"] = max(0.2, self.model_weights["random_forest"] - 0.01)
        self._normalize_weights()

    def _normalize_weights(self):
        total = sum(self.model_weights.values()) or 1.0
        for key in list(self.model_weights.keys()):
            self.model_weights[key] = self.model_weights[key] / total
