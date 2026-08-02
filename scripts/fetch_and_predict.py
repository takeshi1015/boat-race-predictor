"""
取得→予測パイプライン

公式サイトから当日のレースデータを取得し、購入可能なレースのみを予測・表示する。

使用方法:
    python scripts/fetch_and_predict.py

または main.py から:
    python main.py --mode predict-live
"""

import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import setup_logger

logger = setup_logger(__name__)

# 信頼度しきい値（70%以上を推奨とする）
RECOMMENDATION_THRESHOLD = 0.70
# 購入締め切り猶予（分）
PURCHASE_CUTOFF_MINUTES = 10


def run_fetch_and_predict() -> list:
    """
    公式サイトから当日のレースを取得し、購入可能なレースを予測して返す

    Returns:
        購入可能なレースの予測結果リスト
    """
    now = datetime.now()
    logger.info("=" * 60)
    logger.info(f"ライブ予測開始: {now.strftime('%Y-%m-%d %H:%M:%S')} (JST)")
    logger.info("=" * 60)

    # Step 1: 公式サイトから開催中の会場を取得
    open_venue_codes = _fetch_open_venues(now)
    if not open_venue_codes:
        logger.warning("本日開催中の会場が見つかりません（フォールバック: DB使用）")

    # Step 2: DBからレースデータを取得し購入可能なレースを絞り込む
    purchasable_races = _get_purchasable_races(now)

    # Step 3: 各レースを予測
    predictions = _predict_races(purchasable_races, now)

    # Step 4: 結果を表示
    _display_results(predictions, now)

    return predictions


def _fetch_open_venues(now: datetime) -> list:
    """公式サイトから開催中の会場コードを取得"""
    try:
        from scrapers.official_scraper import OfficialScraper
        scraper = OfficialScraper()
        codes = scraper.get_today_open_venues(now)
        scraper.close()
        if codes:
            logger.info(f"✅ 公式サイトから開催会場取得: {len(codes)}場")
        return codes
    except Exception as e:
        logger.error(f"開催会場取得エラー: {e}")
        return []


def _get_purchasable_races(now: datetime) -> list:
    """DBから当日レースを取得し、購入可能なレースのみを返す"""
    try:
        from database.db_manager import get_db_manager
        from models.xgboost_predictor import is_race_purchasable

        db = get_db_manager()
        session = db.get_session()
        try:
            races = db.get_races_by_date(session, now)
            purchasable = []
            total = 0
            skipped = 0

            for race in races:
                total += 1
                race_dt = getattr(race, "date", None)
                if not isinstance(race_dt, datetime):
                    skipped += 1
                    continue

                if is_race_purchasable(race_dt, now):
                    purchasable.append(race)
                else:
                    venue = getattr(race, "place", "") or getattr(race, "venue", "")
                    race_num = getattr(race, "race_number", "?")
                    logger.debug(
                        f"スキップ: {venue} {race_num}R {race_dt.strftime('%H:%M')}"
                        " (購入締切済み)"
                    )
                    skipped += 1

            logger.info(
                f"レース取得: 合計{total}件 → 購入可能{len(purchasable)}件"
                f" (スキップ{skipped}件)"
            )
            return purchasable
        finally:
            session.close()

    except Exception as e:
        logger.error(f"レースデータ取得エラー: {e}", exc_info=True)
        return []


def _predict_races(races: list, now: datetime) -> list:
    """各レースを予測"""
    if not races:
        return []

    try:
        from models.ensemble_model import (
            EnsembleModel,
            _make_prediction_order,
            _confidence_from_conditions,
            _WEATHER_REASONS,
            _WATER_REASONS,
            RACE_TICKET_CUTOFF_MINUTES,
        )
        from datetime import timedelta

        predictions = []
        for race in races:
            try:
                weather = getattr(race, "weather", None) or "sunny"
                water_cond = getattr(race, "water_condition", None) or "calm"
                hour = getattr(race, "start_time_hour", None) or 12
                race_number = getattr(race, "race_number", 1)
                place = getattr(race, "place", None) or getattr(race, "venue", "不明")
                race_dt = getattr(race, "date", now)

                predicted_order = _make_prediction_order(race_number, weather)
                confidence = _confidence_from_conditions(weather, water_cond, hour)

                reason = _WEATHER_REASONS.get(weather, "")
                water_reason = _WATER_REASONS.get(water_cond, "")
                if water_reason:
                    reason = reason + "。" + water_reason if reason else water_reason

                deadline_dt = race_dt - timedelta(minutes=RACE_TICKET_CUTOFF_MINUTES)
                time_until_start = max(0.0, (race_dt - now).total_seconds() / 60)
                time_remaining = max(0, int((deadline_dt - now).total_seconds()))

                predictions.append({
                    "race_id": getattr(race, "race_id", "unknown"),
                    "place": place,
                    "venue": place,
                    "race_number": race_number,
                    "start_time": race_dt.strftime("%H:%M") if isinstance(race_dt, datetime) else "?",
                    "predicted_order": predicted_order,
                    "confidence": round(confidence, 2),
                    "reason": reason,
                    "is_purchasable": True,
                    "is_recommended": confidence >= RECOMMENDATION_THRESHOLD,
                    "time_until_start_minutes": round(time_until_start, 1),
                    "time_remaining": time_remaining,
                    "purchase_deadline": deadline_dt.strftime("%H:%M"),
                })
            except Exception as e:
                logger.error(f"個別レース予測エラー: {e}")

        # 発走時刻でソート（近い順）
        predictions.sort(key=lambda p: p.get("time_until_start_minutes", float("inf")))
        return predictions

    except Exception as e:
        logger.error(f"予測処理エラー: {e}", exc_info=True)
        return []


def _display_results(predictions: list, now: datetime) -> None:
    """予測結果をコンソールに表示"""
    print()
    print("今日のレース（購入可能）")
    print("=" * 40)
    print(f"現在時刻: {now.strftime('%H:%M')}")
    print()

    if not predictions:
        print("購入可能なレースはありません")
        print()
        return

    # 会場ごとにグループ化
    venues: dict = {}
    for pred in predictions:
        venue = pred.get("place") or pred.get("venue") or "不明"
        if venue not in venues:
            venues[venue] = []
        venues[venue].append(pred)

    recommended = [p for p in predictions if p.get("is_recommended")]
    not_recommended = [p for p in predictions if not p.get("is_recommended")]

    for venue, venue_preds in venues.items():
        print(f"【{venue}競艇場】")
        for pred in venue_preds:
            race_num = pred.get("race_number", "?")
            start_time = pred.get("start_time", "?")
            minutes = pred.get("time_until_start_minutes", 0)
            conf = pred.get("confidence", 0)
            conf_pct = int(conf * 100)
            order = pred.get("predicted_order", [])
            order_str = "→".join(str(n) for n in order) if order else "-"

            stars = ""
            if conf >= 0.80:
                stars = " ⭐⭐⭐"
            elif conf >= 0.70:
                stars = " ⭐⭐"
            elif conf >= 0.60:
                stars = " ⭐"

            print(
                f"  R{race_num}: {start_time} 発走予定（あと{minutes:.0f}分）"
            )
            print(f"    信頼度: {conf_pct}%{stars}")
            print(f"    予想: {order_str}")

        print()

    print("=" * 40)
    print(f"購入推奨（70%以上）: {len(recommended)}件")
    print(f"参考情報（70%未満）: {len(not_recommended)}件")
    print()


def main():
    """メインエントリーポイント"""
    predictions = run_fetch_and_predict()
    return 0 if predictions is not None else 1


if __name__ == "__main__":
    sys.exit(main())
