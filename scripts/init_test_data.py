"""テストデータを作成するスクリプト."""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.db_manager import get_db_manager
from database.models import Race


def _upsert_race(session, payload):
    race = session.query(Race).filter_by(race_id=payload["race_id"]).first()
    if race:
        for key, value in payload.items():
            setattr(race, key, value)
    else:
        session.add(Race(**payload))


def main():
    db = get_db_manager()
    session = db.get_session()
    now = datetime.now()
    today = now.replace(hour=9, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    races = [
        {"race_id": "today_001", "venue": "桐生", "date": today + timedelta(hours=1), "race_number": 1, "wind_speed": 2.0, "water_surface": "calm", "temperature": 28.0, "time_of_day": "morning", "tide": "low"},
        {"race_id": "today_002", "venue": "戸田", "date": today + timedelta(hours=3), "race_number": 2, "wind_speed": 4.0, "water_surface": "slight", "temperature": 26.0, "time_of_day": "midday", "tide": "high"},
        {"race_id": "today_003", "venue": "江戸川", "date": today + timedelta(hours=6), "race_number": 3, "wind_speed": 6.0, "water_surface": "moderate", "temperature": 24.0, "time_of_day": "evening", "tide": "high"},
        {"race_id": "today_004", "venue": "多摩川", "date": today + timedelta(hours=8), "race_number": 4, "wind_speed": 3.0, "water_surface": "calm", "temperature": 27.0, "time_of_day": "evening", "tide": "low"},
        {"race_id": "today_005", "venue": "浜名湖", "date": today + timedelta(hours=10), "race_number": 5, "wind_speed": 5.0, "water_surface": "rough", "temperature": 22.0, "time_of_day": "evening", "tide": "high"},
        {"race_id": "tomorrow_001", "venue": "桐生", "date": tomorrow + timedelta(hours=1), "race_number": 1, "wind_speed": 2.0, "water_surface": "calm", "temperature": 29.0, "time_of_day": "morning", "tide": "low"},
        {"race_id": "tomorrow_002", "venue": "戸田", "date": tomorrow + timedelta(hours=3), "race_number": 2, "wind_speed": 5.0, "water_surface": "slight", "temperature": 25.0, "time_of_day": "midday", "tide": "high"},
        {"race_id": "tomorrow_003", "venue": "江戸川", "date": tomorrow + timedelta(hours=6), "race_number": 3, "wind_speed": 7.0, "water_surface": "moderate", "temperature": 23.0, "time_of_day": "evening", "tide": "high"},
        {"race_id": "hist_001", "venue": "桐生", "date": yesterday + timedelta(hours=1), "race_number": 1, "wind_speed": 3.0, "water_surface": "calm", "temperature": 27.0, "time_of_day": "morning", "tide": "low", "result": {"1st": 1, "2nd": 2, "3rd": 3}},
        {"race_id": "hist_002", "venue": "戸田", "date": yesterday + timedelta(hours=2), "race_number": 2, "wind_speed": 6.0, "water_surface": "rough", "temperature": 22.0, "time_of_day": "midday", "tide": "high", "result": {"1st": 2, "2nd": 1, "3rd": 4}},
    ]

    for payload in races:
        _upsert_race(session, payload)

    session.commit()
    print(f"✅ テストレースデータを{len(races)}件設定しました")
    session.close()


if __name__ == "__main__":
    main()
