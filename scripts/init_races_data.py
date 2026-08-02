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

# 各会場の第1レース開始時刻（実開催情報）
VENUE_START_TIMES = {
    "桐生": 15,      # 15:28
    "多摩川": 11,    # 11:32
    "浜名湖": 11,    # 11:24
    "常滑": 11,      # 11:07
    "びわこ": 11,    # 11:10
    "尼崎": 11,      # 11時台
    "丸亀": 11,      # 11時台
    "児島": 11,      # 11時台
    "若松": 10,      # 10時台
    "芦屋": 13,      # 13時台
    "福岡": 12,      # 12時台
    "唐津": 12,      # 12時台
}

WEATHERS = ["sunny", "cloudy", "rainy"]
WATER_CONDITIONS = ["calm", "slight", "moderate"]
WEATHER_WEIGHT = [0.5, 0.35, 0.15]


def _random_race_id(date: datetime, venue: str, race_number: int) -> str:
    date_str = date.strftime("%Y%m%d")
    venue_code = venue[:2]
    return f"{date_str}_{venue_code}_{race_number:02d}"


def _make_race(date: datetime, venue: str, race_number: int, hour: int, minute: int = 0) -> dict:
    weather = random.choices(WEATHERS, weights=WEATHER_WEIGHT)[0]
    water = random.choice(WATER_CONDITIONS)
    
    # start_time_hour は時間のみ（分は含まない）
    start_time_hour = hour
    
    return {
        "race_id": _random_race_id(date, venue, race_number),
        "date": date.replace(hour=hour, minute=minute, second=0, microsecond=0),
        "venue": venue,
        "place": venue,
        "race_number": race_number,
        "weather": weather,
        "water_condition": water,
        "water_surface": water,
        "start_time_hour": start_time_hour,
        "time_of_day": "morning" if hour < 12 else ("midday" if hour < 17 else "evening"),
        "number_of_boats": 6,
        "wind_speed": round(random.uniform(0, 5), 1),
        "temperature": round(random.uniform(15, 35), 1),
        "humidity": round(random.uniform(40, 90), 1),
    }


def _make_prediction(race_id: str, date: datetime, is_hit: bool, confidence: float) -> dict:
    predicted_order = [1, 2, 3] if is_hit else [2, 3, 1]
    # 実際のオッズはランダムに生成（シミュレーションデータ）
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
    """当日のレースデータを作成（実開催会場、各会場12レース、現在時刻以降のみ）"""
    now = datetime.now()
    
    # 2026年8月2日の公式開催場所
    official_venues_20260802 = [
        "桐生", "多摩川", "浜名湖", "常滑", "びわこ", 
        "尼崎", "丸亀", "児島", "若松", "芦屋", "福岡", "唐津"
    ]
    
    # 本日のデータか判定
    if target_date.strftime("%Y-%m-%d") == "2026-08-02":
        available_venues = official_venues_20260802
    else:
        available_venues = ALL_VENUES
    
    created = []
    
    # 各会場ごとに12レースを生成
    for venue in available_venues:
        # 会場ごとの第1レース開始時刻
        start_hour = VENUE_START_TIMES.get(venue, 11)
        start_minute = random.randint(0, 59)  # 分はランダム
        
        # 当日の場合、現在時刻以降のレースのみ生成
        if target_date.date() == now.date():
            # 現在時刻より前のレースはスキップ
            race_start = target_date.replace(hour=start_hour, minute=start_minute)
            if race_start < now:
                # 最初のレースが現在時刻を過ぎている場合、次のレース時刻から開始
                elapsed_minutes = int((now - race_start).total_seconds() / 60)
                races_passed = elapsed_minutes // 20  # 20分ごと
                first_race_number = races_passed + 1
            else:
                first_race_number = 1
        else:
            first_race_number = 1
        
        # 各会場12レース生成
        for race_number in range(first_race_number, 13):
            # 第1レースから20分ごと
            minutes_offset = (race_number - 1) * 20
            total_minutes = start_hour * 60 + start_minute + minutes_offset
            
            # 24時間を超える場合はスキップ
            if total_minutes >= 24 * 60:
                break
            
            race_hour = total_minutes // 60
            race_minute = total_minutes % 60
            
            race_data = _make_race(target_date, venue, race_number, race_hour, race_minute)
            
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
        
        # 過去データは全24場で各12レース
        for venue in ALL_VENUES:
            start_hour = VENUE_START_TIMES.get(venue, 11)
            start_minute = random.randint(0, 59)
            
            # 各会場12レース
            for race_number in range(1, 13):
                minutes_offset = (race_number - 1) * 20
                total_minutes = start_hour * 60 + start_minute + minutes_offset
                
                if total_minutes >= 24 * 60:
                    break
                
                race_hour = total_minutes // 60
                race_minute = total_minutes % 60
                
                race_data = _make_race(target_date, venue, race_number, race_hour, race_minute)
                
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
    print("━" * 60)
    print("レースデータ初期化スクリプト")
    print("━" * 60)
    print()

    db = get_db_manager()
    session = db.get_session()

    try:
        today = datetime.now()
        tomorrow = today + timedelta(days=1)

        # 当日レース
        print("📅 当日レースデータを生成中...")
        print(f"   現在時刻: {today.strftime('%H:%M:%S')}")
        today_races = create_today_races(session, db, today)
        print(f"  ✅ 当日レース: {len(today_races)}件")
        
        # 会場ごとにグループ化して表示
        venues_dict = {}
        for r in today_races:
            venue = r.place or r.venue or "?"
            if venue not in venues_dict:
                venues_dict[venue] = []
            venues_dict[venue].append(r)
        
        for venue in sorted(venues_dict.keys()):
            races = venues_dict[venue]
            times = ", ".join([f"{r.start_time_hour}:{str(r.date.minute).zfill(2)}" for r in races[:3]])
            print(f"    - {venue}競艇場: {len(races)}レース ({times}...)")

        # 翌日レース
        print()
        print("📅 翌日レースデータを生成中...")
        tomorrow_races = create_today_races(session, db, tomorrow)
        print(f"  ✅ 翌日レース: {len(tomorrow_races)}件")

        # 過去30日間データ
        print()
        print("📊 過去30日間のデータを生成中...")
        total_races, total_predictions = create_historical_data(session, db, days=30)
        print(f"  ✅ 過去レース: {total_races}件")
        print(f"  ✅ 過去予測:   {total_predictions}件")

        # 確認
        print()
        all_today = db.get_races_by_date(session, today)
        print(f"✅ 当日合計: {len(all_today)}件のレースが登録されています")
        print()
        print("━" * 60)
        print("セットアップ完了！")
        print()
        print("次のコマンドで動作を確認してください：")
        print("  python main.py --mode predict-today")
        print("  python main.py --mode predict-tomorrow")
        print("  python main.py --mode stats")
        print("  python main.py --mode run-server  (Web UI)")
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
