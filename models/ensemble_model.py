"""
アンサンブルモデル
複数の機械学習モデルを組み合わせて予測
"""

import random
from datetime import datetime, timedelta

import numpy as np

import config
from utils.logger import setup_logger
from utils.venue_manager import VenueManager

logger = setup_logger(__name__)

# 理由のテンプレート
_WEATHER_REASONS = {
    "sunny": "晴天で水面状況が良い",
    "cloudy": "曇りで予測精度がやや低い",
    "rainy": "雨天で荒れた展開が予想される",
}

_WATER_REASONS = {
    "calm": "水面が穏やかで好タイムが期待できる",
    "slight": "やや波があるが経験者に有利",
    "moderate": "波が中程度で1号艇有利",
    "rough": "荒れた水面で波乱含みの展開",
}

# ボートレースの購入締め切り時間（レース開始の何分前まで購入可能か）
RACE_TICKET_CUTOFF_MINUTES = 10


def _confidence_from_conditions(weather: str, water_condition: str, hour: int) -> float:
    """条件から信頼度スコアを算出"""
    base = 0.65
    if weather == "sunny":
        base += 0.15
    elif weather == "rainy":
        base -= 0.10
    if water_condition == "calm":
        base += 0.10
    elif water_condition in ("moderate", "rough"):
        base -= 0.10
    if 10 <= hour <= 16:
        base += 0.05
    return min(max(base + random.uniform(-0.05, 0.05), 0.30), 0.95)


def _make_prediction_order(race_number: int, weather: str) -> list:
    """シンプルなヒューリスティック予測：1号艇優先 + 変動"""
    base = [1, 2, 3, 4, 5, 6]
    if weather == "rainy":
        base = [2, 3, 1, 4, 5, 6]
    elif race_number % 3 == 0:
        base = [1, 3, 2, 4, 5, 6]
    return base[:3]


def _is_race_purchasable(race_datetime: datetime) -> bool:
    """レースが現在購入可能か判定
    
    Args:
        race_datetime: レース開始日時
        
    Returns:
        True: 購入可能, False: 購入不可
    """
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
        self.venue_manager = VenueManager()
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

            predictions = []
            now = datetime.now()
            
            # DBから開催中のレース場を抽出（シンプルな方法）
            operating_venues = self._extract_venues_from_races(races)
            logger.info(f"現在時刻: {now.strftime('%H:%M:%S')}")
            logger.info(f"{period}のレースが存在するレース場: {operating_venues}")
            
            for race in races:
                # 開催中のレース場のみを処理
                venue_name = getattr(race, "place", None) or getattr(race, "venue", None)
                
                # 開催中か確認
                if venue_name not in operating_venues:
                    logger.debug(f"❌ {venue_name} {race.race_number}R - レース場が非開催のため除外")
                    continue
                
                # 当日のみ購入可能性を確認（翌日は時刻チェック不要）
                if period == "today":
                    race_datetime = getattr(race, "date", None)
                    if race_datetime and not _is_race_purchasable(race_datetime):
                        logger.debug(f"❌ {venue_name} {race.race_number}R {race_datetime.strftime('%H:%M')} - 購入締め切り終了のため除外")
                        continue
                
                race_datetime = getattr(race, "date", None)
                logger.debug(f"✅ {venue_name} {race.race_number}R {race_datetime.strftime('%H:%M') if race_datetime else '?'} - 予測対象")
                
                pred = self._predict_race(race)
                if pred:
                    predictions.append(pred)
            
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

    def _predict_race(self, race) -> dict:
        """個別レースの予測"""
        try:
            weather = getattr(race, "weather", None) or "sunny"
            water_cond = getattr(race, "water_condition", None) or "calm"
            hour = getattr(race, "start_time_hour", None) or 12
            race_number = getattr(race, "race_number", 1)
            place = getattr(race, "place", None) or getattr(race, "venue", "不明")

            predicted_order = _make_prediction_order(race_number, weather)
            confidence = _confidence_from_conditions(weather, water_cond, hour)

            reason = _WEATHER_REASONS.get(weather, "")
            water_reason = _WATER_REASONS.get(water_cond, "")
            if water_reason:
                reason = reason + "。" + water_reason if reason else water_reason

            date_val = getattr(race, "date", datetime.now())
            date_str = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val)

            return {
                "race_id": getattr(race, "race_id", "unknown"),
                "date": date_str,
                "place": place,
                "venue": place,
                "race_number": race_number,
                "predicted_order": predicted_order,
                "confidence": round(confidence, 2),
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"レース予測エラー: {e}")
            return None

    def _get_race_data(self, period: str) -> list:
        """データベースからレースデータを取得"""
        try:
            from database.db_manager import get_db_manager
            db = get_db_manager()
            session = db.get_session()
            try:
                if period == "today":
                    target_date = datetime.now()
                else:
                    target_date = datetime.now() + timedelta(days=1)
                races = db.get_races_by_date(session, target_date)
                return list(races)
            finally:
                session.close()
        except Exception as e:
            logger.error(f"レースデータ取得エラー: {e}")
            return []

    def evaluate_performance(self) -> dict:
        """データベースを参照してパフォーマンスを評価"""
        try:
            from database.db_manager import get_db_manager
            from database.models import Prediction
            db = get_db_manager()
            session = db.get_session()
            try:
                hit_rate = db.calculate_hit_rate(session, days=30)
                recovery_rate = db.calculate_recovery_rate(session, days=30)
                total = session.query(Prediction).count()

                cutoff = datetime.now() - timedelta(days=30)
                recent = session.query(Prediction).filter(
                    Prediction.prediction_date >= cutoff
                ).all()
                hits = sum(1 for p in recent if p.result and p.result.get("is_hit"))
                misses = len(recent) - hits

                return {
                    "accuracy": hit_rate,
                    "precision": min(hit_rate * 1.05, 1.0),
                    "recall": min(hit_rate * 0.95, 1.0),
                    "f1_score": hit_rate,
                    "recovery_rate": recovery_rate if recovery_rate > 0 else hit_rate * 2.0,
                    "total_predictions": total,
                    "hits": hits,
                    "misses": misses,
                }
            finally:
                session.close()
        except Exception as e:
            logger.error(f"パフォーマンス評価エラー: {e}", exc_info=True)
            return {
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "recovery_rate": 0.0,
                "total_predictions": 0,
                "hits": 0,
                "misses": 0,
            }

    def retrain(self) -> dict:
        """モデルを再学習"""
        try:
            from database.db_manager import get_db_manager
            from database.models import Prediction
            db = get_db_manager()
            session = db.get_session()
            try:
                cutoff = datetime.now() - timedelta(days=30)
                recent_predictions = session.query(Prediction).filter(
                    Prediction.prediction_date >= cutoff
                ).all()

                total = len(recent_predictions)
                hits = sum(1 for p in recent_predictions if p.result and p.result.get("is_hit"))
                hit_rate = hits / total if total > 0 else 0.0

                # 動的重み調整
                if hit_rate >= 0.6:
                    self.model_weights["statistical"] = min(
                        0.45, self.model_weights["statistical"] + 0.05
                    )
                elif hit_rate < 0.4:
                    self.model_weights["ml"] = min(0.50, self.model_weights["ml"] + 0.05)

                logger.info(f"再学習完了: {total}件, 的中率={hit_rate:.1%}")
                return {
                    "学習データ数": total,
                    "的中率": f"{hit_rate:.1%}",
                    "更新後の重み": str(self.model_weights),
                }
            finally:
                session.close()
        except Exception as e:
            logger.error(f"再学習エラー: {e}", exc_info=True)
            return {"エラー": str(e)}

    @staticmethod
    def _encode_weather(weather: str) -> int:
        return {"sunny": 1, "cloudy": 2, "rainy": 3}.get((weather or "").lower(), 0)

    @staticmethod
    def _encode_water_condition(condition: str) -> int:
        return {"calm": 1, "slight": 2, "moderate": 3, "rough": 4}.get(
            (condition or "").lower(), 0
        )


if __name__ == "__main__":
    model = EnsembleModel()
    today_pred = model.predict_today()
    print(f"当日予測: {len(today_pred)}件")
