"""
テストデータ初期化スクリプト
当日・翌日のレースデータと過去30日間の履歴データを生成します
"""

import sys
import os
import random
from datetime import datetime, timedelta
from itertools import permutations

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

WEATHERS = ["sunny", "cloudy", "rainy"]
WATER_CONDITIONS = ["calm", "slight", "moderate"]
WEATHER_WEIGHT = [0.5, 0.35, 0.15]

# 全120通りの3連単
BOATS = [1, 2, 3, 4, 5, 6]
ALL_ORDERS = [list(p) for p in permutations(BOATS, 3)]


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


def _predict_boat_order(weather: str, water_condition: str, confidence: float) -> list:
    """
    天気・水面・信頼度に基づいて3連単を予想
    高信頼度：1号艇が絡む確率が高い
    低信頼度（穴狙い）：どの艇でも等確率
    """
    if confidence >= 0.75:
        # 高信頼度：1号艇が1着の可能性が高い
        first_boat = 1
        remaining = [2, 3, 4, 5, 6]
        if weather == "rainy":
            # 雨天は波乱含み、内外艇の混在
            second_third = random.sample(remaining, 2)
        else:
            # 晴天・曇りは内側寄り
            second_third = random.sample([2, 3, 4], min(2, len([2, 3, 4]))) if len([2, 3, 4]) >= 2 else random.sample(remaining, 2)
        return [first_boat] + second_third
    
    elif confidence >= 0.60:
        # 中信頼度：1,2号艇が上位の確率
        if random.random() < 0.6:
            first_boat = 1
        else:
            first_boat = 2
        remaining = [b for b in BOATS if b != first_boat]
        second_third = random.sample(remaining, 2)
        return [first_boat] + second_third
    
    else:
        # 低信頼度（穴狙い）：全120通りから等確率で選択
        return random.choice(ALL_ORDERS)


def _make_prediction(race_id: str, date: datetime, race_weather: str, race_water: str, hour: int) -> dict:
    """予測データを生成"""
    
    # 信頼度を生成（50%～95%全範囲）
    base = 0.50
    if race_weather == "sunny":
        base += 0.25
    elif race_weather == "cloudy":
        base += 0.05
    else:
        base -= 0.10
    
    if race_water == "calm":
        base += 0.20
    elif race_water == "slight":
        base += 0.10
    elif race_water == "moderate":
        base -= 0.05
    else:
        base -= 0.15
    
    if 10 <= hour <= 14:
        base += 0.15
    elif 15 <= hour <= 17:
        base += 0.05
    elif hour < 9:
        base -= 0.10
    else:
        base -= 0.05
    
    confidence = base + random.uniform(-0.30, 0.30)
    confidence = min(max(confidence, 0.50), 0.95)
    
    # 信頼度に基づいて3連単を予想
    predicted_order = _predict_boat_order(race_weather, race_water, confidence)
    
    is_hit = random.random() < 0.55
    actual_odds = round(random.uniform(5.0, 50.0), 1) if is_hit else 0.0
    
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
            "actual_odds": actual_odds,
        },
    }


def create_today_races(session, db, target_date: datetime, num_races: int = 10, create_predictions: bool = False) -> list:
    """当日のレースデータを作成（全24場から10場をランダム選択、現在時刻より30分以上後のレースのみ）"""
    now = datetime.now()
    
    # 全24場からランダムに選択
    venues_today = random.sample(ALL_VENUES, min(num_races, len(ALL_VENUES)))
    
    # 現在時刻より30分以上後のレースを生成
    current_hour = now.hour
    current_minute = now.minute
    
    # 最初のレースは30分以上後
    if current_minute < 30:
        start_hour = current_hour + 1  # 次の時間の00分
    else:
        start_hour = current_hour + 1  # 次の時間の00分
    
    # 生成するレース時刻（現在時刻の30分以上後）
    hours = []
    for i in range(num_races):
        race_hour = start_hour + i
        if race_hour < 24:  # 同日内のみ
            hours.append(race_hour)
    
    # 時刻が不足する場合はランダムに生成
    while len(hours) < num_races:
        hours.append(random.randint(start_hour, 23))
    
    hours = hours[:num_races]
    
    created = []
    for i, venue in enumerate(venues_today):
        if i < len(hours):
            hour = hours[i]
        else:
            hour = random.randint(start_hour, 23)
        
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
        
        # 当日の場合は予測も生成
        if create_predictions:
            pred_data = _make_prediction(
                race_data["race_id"],
                target_date,
                race_data["weather"],
                race_data["water_condition"],
                hour
            )
            pred = Prediction(**pred_data)
            session.add(pred)
    
    session.commit()
    return created


def create_historical_data(session, db, days: int = 30) -> int:
    """過去30日間のデータを生成"""
    total_races = 0
    total_predictions = 0
    today = datetime.now()

    for day_offset in range(1, days + 1):
        target_date = today - timedelta(days=day_offset)
        num_venues = random.randint(5, 10)
        venues_day = random.sample(ALL_VENUES, num_venues)
        hours = [10, 12, 14, 16, 18, 20]

        for i, venue in enumerate(venues_day):
            hour = hours[i % len(hours)]
            race_data = _make_race(target_date, venue, i + 1, hour)

            existing = db.get_race(session, race_data["race_id"])
            if existing:
                race_id = existing.race_id
                weather = existing.weather
                water = existing.water_condition
            else:
                race = Race(**race_data)
                session.add(race)
                session.flush()
                race_id = race.race_id
                weather = race.weather
                water = race.water_condition
            total_races += 1

            # 予測データを生成（多様性確保）
            pred_data = _make_prediction(race_id, target_date, weather, water, hour)
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

        # 当日レース（全24場からランダム選択）+ 予測
        print("📅 当日レースデータを作成中...")
        print(f"   現在時刻: {today.strftime('%H:%M:%S')}")
        today_races = create_today_races(session, db, today, num_races=10, create_predictions=True)
        print(f"  ✅ 当日レース: {len(today_races)}件")
        for r in today_races:
            place = r.place or r.venue or "?"
            print(f"    - {place}競艇場 {r.race_number}レース "
                  f"({r.weather}, {r.water_condition}, {r.start_time_hour}時)")

        # 翌日レース
        print()
        print("📅 翌日レースデータを作成中...")
        tomorrow_races = create_today_races(session, db, tomorrow, num_races=10, create_predictions=True)
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
