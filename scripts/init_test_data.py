"""
テストデータ初期化スクリプト
当日・翌日のレースデータと過去30日間の履歴データを生成します
"""

import sys
import os
import random
from datetime import datetime, timedelta

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db_manager
from database.models import Race, Prediction


# 競艇場データ
VENUES = [
    "桐生", "戸田", "江戸川", "平和島", "多摩川",
    "浜名湖", "蒲郡", "常滑", "津", "三国",
    "びわこ", "住之江", "尼崎", "鳴門", "丸亀",
]

WEATHERS = ["sunny", "cloudy", "rainy"]
WATER_CONDITIONS = ["calm", "slight", "moderate"]
WEATHER_WEIGHT = [0.5, 0.35, 0.15]


def _random_race_id(date: datetime, venue: str, race_number: int) -> str:
    date_str = date.strftime("%Y%m%d")
    venue_code = venue[:2]
    return f"{date_str}_{venue_code}_{race_number:02d}"


def _make_race(date: datetime, venue: str, race_number: int, hour: int) -> dict:
    weather = random.choices(WEATHERS, weights=WEATHER_WEIGHT)[0]
    water = random.choice(WATER_CONDITIONS)
    return {
        "race_id": _random_race_id(date, venue, race_number),
        "date": date.replace(hour=hour, minute=0, second=0, microsecond=0),
        "venue": venue,
        "place": venue,
        "race_number": race_number,
        "weather": weather,
        "water_condition": water,
        "water_surface": water,
        "start_time_hour": hour,
        "time_of_day": "morning" if hour < 12 else ("midday" if hour < 17 else "evening"),
        "number_of_boats": 6,
        "wind_speed": round(random.uniform(0, 5), 1),
        "temperature": round(random.uniform(15, 35), 1),
        "humidity": round(random.uniform(40, 90), 1),
    }


def _make_prediction(race_id: str, date: datetime, is_hit: bool, confidence: float) -> dict:
    predicted_order = [1, 2, 3] if is_hit else [2, 3, 1]
    # 実際のオッズは的中・不的中に関わらず設定（実際のレース結果に基づく）
    actual_odds = round(random.uniform(2.0, 50.0), 1)
    return {
        "race_id": race_id,
        "prediction_date": date,
        "prediction_type": "high_confidence" if confidence >= 0.7 else "standard",
        "predicted_order": predicted_order,
        "confidence": confidence,
        "estimated_odds": round(random.uniform(3.0, 20.0), 1),
        "model_version": "1.0",
        "methods_used": ["statistical", "ml", "rule_based"],
        "result": {
            "is_hit": is_hit,
            "actual_odds": actual_odds if is_hit else 0.0,
        },
    }


def create_today_races(session, db, target_date: datetime, num_races: int = 6) -> list:
    """当日のレースデータを作成"""
    venues_today = random.sample(VENUES, min(num_races, len(VENUES)))
    hours = [10, 11, 12, 13, 14, 16, 18, 19, 20]
    created = []
    for i, venue in enumerate(venues_today):
        hour = hours[i % len(hours)]
        race_data = _make_race(target_date, venue, i + 1, hour)
        # 既存チェック
        existing = db.get_race(session, race_data["race_id"])
        if existing:
            created.append(existing)
        else:
            race = Race(**race_data)
            session.add(race)
            session.flush()
            created.append(race)
    session.commit()
    return created


def create_historical_data(session, db, days: int = 30) -> int:
    """過去30日間のデータを生成"""
    total_races = 0
    total_predictions = 0
    today = datetime.now()

    for day_offset in range(1, days + 1):
        target_date = today - timedelta(days=day_offset)
        num_venues = random.randint(3, 6)
        venues_day = random.sample(VENUES, num_venues)
        hours = [10, 12, 14, 16, 18, 20]

        for i, venue in enumerate(venues_day):
            hour = hours[i % len(hours)]
            race_data = _make_race(target_date, venue, i + 1, hour)

            existing = db.get_race(session, race_data["race_id"])
            if existing:
                race_id = existing.race_id
            else:
                race = Race(**race_data)
                session.add(race)
                session.flush()
                race_id = race.race_id
            total_races += 1

            # 過去予測（的中率 ~55%）
            is_hit = random.random() < 0.55
            confidence = round(random.uniform(0.55, 0.90), 2)
            pred_data = _make_prediction(race_id, target_date, is_hit, confidence)
            pred = Prediction(**pred_data)
            session.add(pred)
            total_predictions += 1

    session.commit()
    return total_races, total_predictions


def main():
    print()
    print("━" * 50)
    print("テストデータ初期化スクリプト")
    print("━" * 50)
    print()

    db = get_db_manager()
    session = db.get_session()

    try:
        today = datetime.now()
        tomorrow = today + timedelta(days=1)

        # 当日レース（6件以上）
        print("📅 当日レースデータを作成中...")
        today_races = create_today_races(session, db, today, num_races=6)
        print(f"  ✅ 当日レース: {len(today_races)}件")
        for r in today_races:
            place = r.place or r.venue or "?"
            print(f"    - {place}競艇場 {r.race_number}レース "
                  f"({r.weather}, {r.water_condition}, {r.start_time_hour}時)")

        # 翌日レース
        print()
        print("📅 翌日レースデータを作成中...")
        tomorrow_races = create_today_races(session, db, tomorrow, num_races=5)
        print(f"  ✅ 翌日レース: {len(tomorrow_races)}件")

        # 過去30日間データ
        print()
        print("📊 過去30日間のデータを作成中...")
        total_races, total_predictions = create_historical_data(session, db, days=30)
        print(f"  ✅ 過去レース: {total_races}件")
        print(f"  ✅ 過去予測:   {total_predictions}件")

        # 確認
        print()
        all_today = db.get_races_by_date(session, today)
        print(f"✅ 当日合計: {len(all_today)}件のレースが登録されています")
        print()
        print("━" * 50)
        print("セットアップ完了！")
        print()
        print("次のコマンドで動作を確認してください：")
        print("  python main.py --mode predict-today")
        print("  python main.py --mode predict-tomorrow")
        print("  python main.py --mode stats")
        print("  python main.py --mode run-server  (Web UI)")
        print("━" * 50)
        print()

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    main()
