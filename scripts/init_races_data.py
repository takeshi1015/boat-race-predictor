"""
レースデータ初期化スクリプト
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


# 全24場のボートレース場
ALL_VENUES = [
    "桐生", "戸田", "江戸川", "平和島", "多摩川",
    "浜名湖", "蒲郡", "常滑", "津", "三国",
    "びわこ", "住之江", "尼崎", "鳴門", "丸亀",
    "児島", "宮島", "芦屋", "福岡", "唐津", "大村",
]

# 各会場の第1レース開始時刻と分
VENUE_START_TIMES = {
    "桐生": (15, 28),
    "多摩川": (11, 32),
    "浜名湖": (11, 24),
    "常滑": (11, 7),
    "びわこ": (11, 10),
    "尼崎": (11, 15),
    "丸亀": (11, 20),
    "児島": (11, 25),
    "若松": (10, 30),
    "芦屋": (13, 10),
    "福岡": (12, 20),
    "唐津": (12, 30),
    "戸田": (10, 50),
    "江戸川": (10, 20),
    "平和島": (10, 40),
    "蒲郡": (11, 35),
    "津": (11, 40),
    "三国": (11, 45),
    "鳴門": (11, 50),
    "宮島": (12, 10),
    "大村": (12, 40),
}

WEATHERS = ["sunny", "cloudy", "rainy"]
WATER_CONDITIONS = ["calm", "slight", "moderate"]
WEATHER_WEIGHT = [0.5, 0.35, 0.15]


def _random_race_id(date: datetime, venue: str, race_number: int) -> str:
    date_str = date.strftime("%Y%m%d")
    venue_code = venue[:2]
    return f"{date_str}_{venue_code}_{race_number:02d}"


def _make_race(date: datetime, venue: str, race_number: int, hour: int, minute: int) -> dict:
    weather = random.choices(WEATHERS, weights=WEATHER_WEIGHT)[0]
    water = random.choice(WATER_CONDITIONS)
    
    return {
        "race_id": _random_race_id(date, venue, race_number),
        "date": date.replace(hour=hour, minute=minute, second=0, microsecond=0),
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


def create_today_races(session, db, target_date: datetime) -> list:
    """当日のレースデータを作成"""
    now = datetime.now()
    
    # 2026年8月2日の公式開催場所
    official_venues_20260802 = [
        "桐生", "多摩川", "浜名湖", "常滑", "びわこ", 
        "尼崎", "丸亀", "児島", "若松", "芦屋", "福岡", "唐津"
    ]
    
    if target_date.strftime("%Y-%m-%d") == "2026-08-02":
        available_venues = official_venues_20260802
    else:
        available_venues = ALL_VENUES
    
    created = []
    
    for venue in available_venues:
        start_h, start_m = VENUE_START_TIMES.get(venue, (11, 0))
        
        # 当日の場合、現在時刻以降のレースのみ
        if target_date.date() == now.date():
            first_race_time = target_date.replace(hour=start_h, minute=start_m)
            if first_race_time < now:
                # 現在時刻以降の最初のレースから開始
                elapsed_minutes = int((now - first_race_time).total_seconds() / 60)
                first_race_num = (elapsed_minutes // 20) + 1
            else:
                first_race_num = 1
        else:
            first_race_num = 1
        
        # 12レース生成（20分ごと）
        for race_number in range(first_race_num, 13):
            offset_minutes = (race_number - 1) * 20
            total_minutes = start_h * 60 + start_m + offset_minutes
            
            if total_minutes >= 24 * 60:  # 24時間超過でスキップ
                break
            
            hour = total_minutes // 60
            minute = total_minutes % 60
            
            race_data = _make_race(target_date, venue, race_number, hour, minute)
            
            existing = db.get_race(session, race_data["race_id"])
            if not existing:
                race = Race(**race_data)
                session.add(race)
                session.flush()
            created.append(existing or race)
    
    session.commit()
    return created


def create_historical_data(session, db, days: int = 30) -> tuple:
    """過去30日間のデータを生成"""
    total_races = 0
    total_predictions = 0
    today = datetime.now()

    for day_offset in range(1, days + 1):
        target_date = today - timedelta(days=day_offset)
        
        for venue in ALL_VENUES:
            start_h, start_m = VENUE_START_TIMES.get(venue, (11, 0))
            
            for race_number in range(1, 13):
                offset_minutes = (race_number - 1) * 20
                total_minutes = start_h * 60 + start_m + offset_minutes
                
                if total_minutes >= 24 * 60:
                    break
                
                hour = total_minutes // 60
                minute = total_minutes % 60
                
                race_data = _make_race(target_date, venue, race_number, hour, minute)
                
                existing = db.get_race(session, race_data["race_id"])
                if existing:
                    race_id = existing.race_id
                else:
                    race = Race(**race_data)
                    session.add(race)
                    session.flush()
                    race_id = race.race_id
                total_races += 1

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
    print("━" * 60)
    print("レースデータ初期化スクリプト")
    print("━" * 60)
    print()

    db = get_db_manager()
    session = db.get_session()

    try:
        today = datetime.now()
        tomorrow = today + timedelta(days=1)

        print("📅 当日レースデータを生成中...")
        print(f"   現在時刻: {today.strftime('%H:%M:%S')}")
        today_races = create_today_races(session, db, today)
        print(f"  ✅ 当日レース: {len(today_races)}件")

        print()
        print("📅 翌日レースデータを生成中...")
        tomorrow_races = create_today_races(session, db, tomorrow)
        print(f"  ✅ 翌日レース: {len(tomorrow_races)}件")

        print()
        print("📊 過去30日間のデータを生成中...")
        total_races, total_predictions = create_historical_data(session, db, days=30)
        print(f"  ✅ 過去レース: {total_races}件")
        print(f"  ✅ 過去予測:   {total_predictions}件")

        print()
        all_today = db.get_races_by_date(session, today)
        print(f"✅ 当日合計: {len(all_today)}件のレースが登録されています")
        print()
        print("━" * 60)
        print("セットアップ完了！")
        print()
        print("  python main.py --mode predict-today")
        print("  python main.py --mode run-server")
        print("━" * 60)
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
