"""Seed 3-5 test races for today into SQLite database."""

from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.db_manager import DatabaseManager

RACE_DISTANCE = 1800


def seed_today_races() -> int:
    db = DatabaseManager("sqlite:///./boat_race.db")
    session = db.get_session()

    today_datetime = datetime.now().replace(minute=0, second=0, microsecond=0)
    races = [
        {
            "race_id": f"TEST-{today_datetime.strftime('%Y%m%d')}-01",
            "venue": "桐生",
            "date": today_datetime.replace(hour=9),
            "race_number": 1,
            "race_grade": "一般",
            "race_distance": RACE_DISTANCE,
            "wind_speed": 2.5,
            "wind_direction": "北",
            "water_surface": "calm",
            "temperature": 28.0,
            "humidity": 65.0,
            "tide": "中潮",
            "number_of_boats": 6,
            "time_of_day": "morning",
        },
        {
            "race_id": f"TEST-{today_datetime.strftime('%Y%m%d')}-02",
            "venue": "戸田",
            "date": today_datetime.replace(hour=11),
            "race_number": 2,
            "race_grade": "一般",
            "race_distance": RACE_DISTANCE,
            "wind_speed": 3.0,
            "wind_direction": "東",
            "water_surface": "slight",
            "temperature": 29.0,
            "humidity": 63.0,
            "tide": "中潮",
            "number_of_boats": 6,
            "time_of_day": "midday",
        },
        {
            "race_id": f"TEST-{today_datetime.strftime('%Y%m%d')}-03",
            "venue": "平和島",
            "date": today_datetime.replace(hour=13),
            "race_number": 3,
            "race_grade": "一般",
            "race_distance": RACE_DISTANCE,
            "wind_speed": 1.8,
            "wind_direction": "南",
            "water_surface": "calm",
            "temperature": 30.0,
            "humidity": 60.0,
            "tide": "大潮",
            "number_of_boats": 6,
            "time_of_day": "midday",
        },
        {
            "race_id": f"TEST-{today_datetime.strftime('%Y%m%d')}-04",
            "venue": "蒲郡",
            "date": today_datetime.replace(hour=15),
            "race_number": 4,
            "race_grade": "一般",
            "race_distance": RACE_DISTANCE,
            "wind_speed": 2.2,
            "wind_direction": "西",
            "water_surface": "moderate",
            "temperature": 27.0,
            "humidity": 68.0,
            "tide": "小潮",
            "number_of_boats": 6,
            "time_of_day": "evening",
        },
    ]

    try:
        for race in races:
            db.add_or_update_race(session, race)
        return len(races)
    finally:
        session.close()
        db.close()


if __name__ == "__main__":
    count = seed_today_races()
    print(f"Seeded {count} races for today")
