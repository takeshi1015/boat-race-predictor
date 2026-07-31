"""ボートレース公式サイトから実レースデータ/結果を取得するスクリプト。"""

import logging
import os
import sys
from datetime import datetime, timedelta

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db_manager
from database.models import Race
from utils.official_data_client import OfficialDataClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BoatraceDataFetcher:
    """公式データクライアントの薄いラッパー。"""

    def __init__(self):
        self.client = OfficialDataClient(timeout=10)

    def fetch_races_for_date(self, target_date: datetime = None) -> list:
        """指定日のレースデータを公式サイトから取得。"""
        if target_date is None:
            target_date = datetime.now()
        logger.info(f"📥 {target_date.strftime('%Y年%m月%d日')} のレースデータを取得中...")
        races = self.client.fetch_races_for_date(target_date)
        logger.info(f"📊 合計 {len(races)}件のレースを取得")
        return races

    def fetch_results_for_date(self, target_date: datetime = None) -> list:
        """指定日の実結果を公式サイトから取得。"""
        if target_date is None:
            target_date = datetime.now()
        logger.info(f"📥 {target_date.strftime('%Y年%m月%d日')} のレース結果を取得中...")
        results = self.client.fetch_race_results(target_date)
        logger.info(f"📊 合計 {len(results)}件のレース結果を取得")
        return results


def save_races_to_db(races: list) -> int:
    """レースデータをDBに保存"""
    if not races:
        logger.warning("保存するレースがありません")
        return 0


def save_results_to_db(results: list) -> int:
    """レース結果をDBに保存。"""
    if not results:
        logger.warning("保存するレース結果がありません")
        return 0

    db = get_db_manager()
    session = db.get_session()
    updated = 0

    try:
        for item in results:
            race_id = item.get("race_id")
            if not race_id:
                continue

            race_data = {
                "race_id": race_id,
                "date": item.get("date"),
                "venue": item.get("venue"),
                "place": item.get("place"),
                "race_number": item.get("race_number"),
                "result": item.get("result"),
            }
            db.add_or_update_race(session, race_data)
            updated += 1

        db.sync_prediction_results_from_races(session, days=60)
        logger.info(f"✅ {updated}件のレース結果をDBに保存")
        return updated
    except Exception as e:
        logger.error(f"レース結果保存エラー: {e}")
        session.rollback()
        return 0
    finally:
        session.close()

    db = get_db_manager()
    session = db.get_session()

    try:
        saved_count = 0

        for race_data in races:
            try:
                # 既存チェック
                existing = db.get_race(session, race_data["race_id"])
                if existing:
                    logger.debug(f"スキップ（既存）: {race_data['race_id']}")
                    continue

                # 新規レースを追加
                race = Race(**race_data)
                session.add(race)
                saved_count += 1

            except Exception as e:
                logger.debug(f"レース保存エラー: {e}")
                session.rollback()

        session.commit()
        logger.info(f"✅ {saved_count}件のレースをDBに保存")
        return saved_count

    except Exception as e:
        logger.error(f"DB保存エラー: {e}")
        session.rollback()
        return 0
    finally:
        session.close()


def main():
    print()
    print("━" * 60)
    print("ボートレース公式サイト レース/結果データ取得")
    print("━" * 60)
    print()

    fetcher = BoatraceDataFetcher()

    # 当日のレースを取得
    today = datetime.now()
    today_races = fetcher.fetch_races_for_date(today)
    saved_today = save_races_to_db(today_races)

    print()

    # 翌日のレースを取得
    tomorrow = today + timedelta(days=1)
    tomorrow_races = fetcher.fetch_races_for_date(tomorrow)
    saved_tomorrow = save_races_to_db(tomorrow_races)

    # 実結果は昨日分を主対象として取得
    print()
    yesterday = today - timedelta(days=1)
    yesterday_results = fetcher.fetch_results_for_date(yesterday)
    saved_results = save_results_to_db(yesterday_results)

    print()
    print("━" * 60)
    print("✅ レースデータ取得完了！")
    print(f"   当日: {saved_today}件")
    print(f"   翌日: {saved_tomorrow}件")
    print(f"   実結果: {saved_results}件")
    print()
    print("次のコマンドで予想を実行してください：")
    print("  python main.py --mode predict-today")
    print("  python main.py --mode predict-tomorrow")
    print("━" * 60)
    print()


if __name__ == "__main__":
    main()
