from datetime import datetime, timedelta

from scrapers.official_scraper import OfficialRaceScraper, is_race_purchasable
from utils.race_time import filter_races_by_time


def test_same_day_race_within_10_minutes_is_excluded():
    now = datetime(2026, 8, 2, 15, 0)
    race_time = now + timedelta(minutes=9)
    assert is_race_purchasable(race_time, race_time, now=now) is False


def test_race_after_2250_is_excluded():
    now = datetime(2026, 8, 2, 15, 0)
    race_time = datetime(2026, 8, 2, 22, 51)
    assert is_race_purchasable(race_time, race_time, now=now) is False


def test_next_day_race_before_2250_is_included():
    now = datetime(2026, 8, 2, 15, 0)
    race_time = datetime(2026, 8, 3, 8, 30)
    assert is_race_purchasable(race_time, race_time, now=now) is True


def test_filter_races_by_time_keeps_only_purchasable_races():
    now = datetime(2026, 8, 2, 15, 0)
    races = [
        {"race_id": "soon", "date": now + timedelta(minutes=5)},
        {"race_id": "late", "date": datetime(2026, 8, 2, 23, 0)},
        {"race_id": "valid", "date": now + timedelta(minutes=15)},
        {"race_id": "tomorrow", "date": datetime(2026, 8, 3, 9, 0)},
    ]

    filtered = filter_races_by_time(races, now=now)

    assert [race["race_id"] for race in filtered] == ["valid", "tomorrow"]


def test_official_scraper_filters_generated_races(monkeypatch):
    now = datetime(2026, 8, 2, 15, 0)
    scraper = OfficialRaceScraper()
    generated_races = [
        {"race_id": "soon", "date": now + timedelta(minutes=5)},
        {"race_id": "valid", "date": now + timedelta(minutes=20)},
        {"race_id": "late", "date": datetime(2026, 8, 2, 23, 0)},
    ]

    monkeypatch.setattr(scraper.fetcher, "fetch_races_for_date", lambda target_date: generated_races)

    filtered = scraper.fetch_today_races(now=now)

    assert [race["race_id"] for race in filtered] == ["valid"]
