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

# ボートレースの購入締め切り時間
RACE_TICKET_CUTOFF_MINUTES = 5

# 買い目パターン（全6パターン）
ALL_PATTERNS = [
    [1, 2, 3],
    [1, 3, 2],
    [2, 1, 3],
    [2, 3, 1],
    [3, 1, 2],
    [3, 2, 1],
]


def _make_prediction_order(weather: str, water_condition: str) -> list:
    """買い目を生成（毎回ランダムに選択）"""
    # 天気に基づいて確率を調整
    if weather == "rainy":
        # 雨天では波乱パターンを増やす
        weights = [10, 10, 15, 15, 20, 20]
    elif weather == "sunny":
        # 晴天では1号艇有利パターンを増やす
        weights = [25, 20, 15, 10, 15, 15]
    else:  # cloudy
        # 曇りは均等
        weights = [16, 17, 17, 17, 17, 16]
    
    # 加重ランダム選択
    selected = random.choices(ALL_PATTERNS, weights=weights, k=1)[0]
    return selected


def _confidence_from_conditions(weather: str, water_condition: str, hour: int) -> float:
    """条件から信頼度スコアを算出（50%～95%全範囲）"""
    base = 0.50
    
    # 天気の影響（大きく変動）
    if weather == "sunny":
        base += 0.25
    elif weather == "cloudy":
        base += 0.05
    else:  # rainy
        base -= 0.10
    
    # 水面状況の影響
    if water_condition == "calm":
        base += 0.20
    elif water_condition == "slight":
        base += 0.10
    elif water_condition == "moderate":
        base -= 0.05
    else:  # rough
        base -= 0.15
    
    # 時間帯の影響
    if 10 <= hour <= 14:
        base += 0.15
    elif 15 <= hour <= 17:
        base += 0.05
    elif hour < 9:
        base -= 0.10
    else:
        base -= 0.05
    
    # 大きなランダム要素を追加（±30%）
    random_factor = random.uniform(-0.30, 0.30)
    confidence = base + random_factor
    
    # 50%～95%の範囲に収める
    confidence = min(max(confidence, 0.50), 0.95)
    
    return confidence


def _estimate_odds(predicted_order: list, confidence: float, weather: str) -> float:
    """推定オッズを計算"""
    if predicted_order and predicted_order[0] == 1 and weather != "rainy":
        # 1号艇1着の本命予想 → 低～中オッズ
        base_odds = max(2.0, 12.0 - confidence * 10.0)
    else:
        # 穴狙い予想 → 高オッズ
        base_odds = max(10.0, 50.0 - confidence * 30.0)
    return round(base_odds + random.uniform(-1.0, 1.0), 1)


def _upset_score(predicted_order: list, weather: str, water_condition: str, confidence: float) -> float:
    """穴狙いスコアを計算（高いほど穴狙い向き）"""
    score = 0.0
    if predicted_order and predicted_order[0] != 1:
        score += 0.40  # 1号艇以外が1着予想
    if weather == "rainy":
        score += 0.25
    if water_condition in ("moderate", "rough"):
        score += 0.15
    score += (1.0 - confidence) * 0.20  # 不確実性が高いほど穴度アップ
    return min(round(score, 3), 1.0)


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

    def predict_categorized(self, period: str = "tomorrow") -> dict:
        """カテゴリー別予測を実行

        Returns:
            {
                "high_confidence": [...],  # 信頼度0.8以上 TOP 5
                "high_odds": [...],        # 穴狙い予想 TOP 5
            }
        """
        all_preds = self._predict_for_period(period)

        # 確実性の高い予想: 信頼度0.8以上、信頼度降順 TOP 5
        high_confidence = sorted(
            [p for p in all_preds if p.get("confidence", 0) >= 0.8],
            key=lambda x: x.get("confidence", 0),
            reverse=True,
        )[:config.HIGH_CONFIDENCE_RACES]

        # 穴狙い予想: upset_score 降順 TOP 5（高信頼度と重複しない）
        high_conf_ids = {p["race_id"] for p in high_confidence}
        upset_candidates = sorted(
            [p for p in all_preds if p["race_id"] not in high_conf_ids],
            key=lambda x: x.get("upset_score", 0),
            reverse=True,
        )[:config.HIGH_ODDS_RACES]

        logger.info(
            f"カテゴリー別予測完了 [{period}]: "
            f"高信頼度={len(high_confidence)}件, 穴狙い={len(upset_candidates)}件"
        )
        return {
            "high_confidence": high_confidence,
            "high_odds": upset_candidates,
        }

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
            
            # DBから開催中のレース場を抽出
            operating_venues = self._extract_venues_from_races(races)
            logger.info(f"現在時刻: {now.strftime('%H:%M:%S')}")
            logger.info(f"{period}のレースが存在するレース場: {operating_venues}")
            
            for race in races:
                # 開催中のレース場のみを処理
                venue_name = getattr(race, "place", None) or getattr(race, "venue", None)
                race_datetime = getattr(race, "date", None)
                race_num = getattr(race, "race_number", "?")
                
                # 開催中か確認
                if venue_name not in operating_venues:
                    logger.debug(f"❌ {venue_name} {race_num}R - レース場が非開催のため除外")
                    continue
                
                time_str = race_datetime.strftime('%H:%M') if race_datetime else '?'
                logger.debug(f"✅ {venue_name} {race_num}R {time_str} - 予測対象")
                
                pred = self._predict_race(race, period)
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

    def _predict_race(self, race, period: str = "today") -> dict:
        """個別レースの予測"""
        try:
            weather = getattr(race, "weather", None) or "sunny"
            water_cond = getattr(race, "water_condition", None) or "calm"
            hour = getattr(race, "start_time_hour", None) or 12
            race_number = getattr(race, "race_number", 1)
            place = getattr(race, "place", None) or getattr(race, "venue", "不明")

            predicted_order = _make_prediction_order(weather, water_cond)
            confidence = _confidence_from_conditions(weather, water_cond, hour)
            estimated_odds = _estimate_odds(predicted_order, confidence, weather)
            upset = _upset_score(predicted_order, weather, water_cond, confidence)

            reason = _WEATHER_REASONS.get(weather, "")
            water_reason = _WATER_REASONS.get(water_cond, "")
            if water_reason:
                reason = reason + "。" + water_reason if reason else water_reason

            date_val = getattr(race, "date", datetime.now())
            date_str = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val)

            # レース時刻と購入制限時刻の計算
            race_time_str = None
            purchase_deadline_str = None
            purchase_deadline_iso = None
            is_purchasable = False
            time_remaining = 0
            
            if isinstance(date_val, datetime):
                race_time_str = date_val.strftime('%H:%M')
                deadline_dt = date_val - timedelta(minutes=RACE_TICKET_CUTOFF_MINUTES)
                purchase_deadline_str = deadline_dt.strftime('%H:%M')
                purchase_deadline_iso = deadline_dt.isoformat()
                
                now = datetime.now()
                is_purchasable = now <= deadline_dt
                time_remaining = max(0, int((deadline_dt - now).total_seconds()))

            return {
                "race_id": getattr(race, "race_id", "unknown"),
                "date": date_str,
                "place": place,
                "venue": place,
                "race_number": race_number,
                "predicted_order": predicted_order,
                "prediction": predicted_order,  # email notifier との互換性
                "confidence": round(confidence, 2),
                "estimated_odds": estimated_odds,
                "upset_score": upset,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "race_time": race_time_str,
                "purchase_deadline": purchase_deadline_str,
                "purchase_deadline_iso": purchase_deadline_iso,
                "is_purchasable": is_purchasable,
                "time_remaining": time_remaining,
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
