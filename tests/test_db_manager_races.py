"""Tests for race-date retrieval helpers."""

from datetime import datetime

from database.db_manager import DatabaseManager
from database.models import Race


def test_get_races_by_date_filters_and_orders():
    db = DatabaseManager("sqlite:///:memory:")
    session = db.get_session()
    try:
        race_a = Race(
            race_id="20260808_A_01",
            venue="桐生",
            place="桐生",
            race_number=1,
            date=datetime(2026, 8, 8, 9, 30),
        )
        race_b = Race(
            race_id="20260808_A_02",
            venue="桐生",
            place="桐生",
            race_number=2,
            date=datetime(2026, 8, 8, 10, 50),
        )
        race_other_day = Race(
            race_id="20260809_A_01",
            venue="桐生",
            place="桐生",
            race_number=1,
            date=datetime(2026, 8, 9, 9, 30),
        )
        session.add_all([race_b, race_other_day, race_a])
        session.commit()

        races = db.get_races_by_date(session, datetime(2026, 8, 8, 0, 0))

        assert [r.race_id for r in races] == ["20260808_A_01", "20260808_A_02"]
        assert races[0].race_time == datetime(2026, 8, 8, 9, 30)
    finally:
        session.close()
