"""
テストデータ初期化スクリプト
当日のレースデータを5件以上データベースに追加します。
"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from database.db_manager import get_db_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)


def init_test_data():
    """当日のテストレースデータを追加"""
    db = get_db_manager()
    session = db.get_session()

    today = datetime.now().date()

    test_races = [
        {
            "race_id": "test_001",
            "venue": "桐生",
            "date": datetime(today.year, today.month, today.day, 10, 0, 0),
            "race_number": 1,
            "race_grade": "一般",
            "race_distance": 1800,
            "weather": "sunny",
            "water_surface": "calm",
            "wind_speed": 2.0,
            "wind_direction": "北",
            "temperature": 25.0,
            "humidity": 60.0,
            "tide": "中潮",
            "number_of_boats": 6,
            "time_of_day": "morning",
        },
        {
            "race_id": "test_002",
            "venue": "戸田",
            "date": datetime(today.year, today.month, today.day, 12, 0, 0),
            "race_number": 2,
            "race_grade": "一般",
            "race_distance": 1800,
            "weather": "cloudy",
            "water_surface": "slight",
            "wind_speed": 3.5,
            "wind_direction": "南",
            "temperature": 23.0,
            "humidity": 65.0,
            "tide": "大潮",
            "number_of_boats": 6,
            "time_of_day": "midday",
        },
        {
            "race_id": "test_003",
            "venue": "江戸川",
            "date": datetime(today.year, today.month, today.day, 14, 0, 0),
            "race_number": 3,
            "race_grade": "一般",
            "race_distance": 1800,
            "weather": "sunny",
            "water_surface": "calm",
            "wind_speed": 1.5,
            "wind_direction": "東",
            "temperature": 26.0,
            "humidity": 55.0,
            "tide": "小潮",
            "number_of_boats": 6,
            "time_of_day": "midday",
        },
        {
            "race_id": "test_004",
            "venue": "多摩川",
            "date": datetime(today.year, today.month, today.day, 16, 0, 0),
            "race_number": 4,
            "race_grade": "一般",
            "race_distance": 1800,
            "weather": "rainy",
            "water_surface": "moderate",
            "wind_speed": 5.0,
            "wind_direction": "西",
            "temperature": 20.0,
            "humidity": 80.0,
            "tide": "中潮",
            "number_of_boats": 6,
            "time_of_day": "midday",
        },
        {
            "race_id": "test_005",
            "venue": "浜名湖",
            "date": datetime(today.year, today.month, today.day, 18, 0, 0),
            "race_number": 5,
            "race_grade": "一般",
            "race_distance": 1800,
            "weather": "cloudy",
            "water_surface": "slight",
            "wind_speed": 4.0,
            "wind_direction": "北西",
            "temperature": 22.0,
            "humidity": 70.0,
            "tide": "大潮",
            "number_of_boats": 6,
            "time_of_day": "evening",
        },
    ]

    try:
        count = 0
        for race_data in test_races:
            db.add_or_update_race(session, race_data)
            count += 1

        logger.info(f"テストデータ登録完了: {count}件")
        print(f"✅ テストデータ追加完了: {count}件のレースデータを登録しました")

        # 登録済みデータを確認
        races = db.get_races_by_date(session, datetime.now())
        print(f"📊 当日のレースデータ: {len(races)}件")
        for r in races:
            print(f"  - {r.race_id}: {r.venue} 第{r.race_number}R "
                  f"({r.weather}, {r.water_surface}, {r.date.hour}時)")

        return len(races)
    except Exception as e:
        logger.error(f"テストデータ追加エラー: {e}", exc_info=True)
        print(f"❌ テストデータ追加エラー: {e}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("テストデータ初期化スクリプト")
    print("=" * 60)
    count = init_test_data()
    if count >= 5:
        print(f"\n✅ 成功: {count}件のレースデータが登録されています")
        sys.exit(0)
    else:
        print(f"\n❌ 失敗: レースデータが不足しています ({count}件)")
        sys.exit(1)
