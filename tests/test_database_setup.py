"""Tests for SQLite database configuration and seed data setup."""

from datetime import datetime
from inspect import signature

import config
from database.db_manager import DatabaseManager
from scripts.seed_today_races import seed_today_races


def test_database_url_defaults_to_sqlite():
    assert config.DATABASE_URL == "sqlite:///./boat_race.db"


def test_db_manager_default_url_is_sqlite():
    default_url = signature(DatabaseManager.__init__).parameters["database_url"].default
    assert default_url == "sqlite:///./boat_race.db"


def test_seed_today_races_adds_today_records(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    inserted = seed_today_races()
    assert 3 <= inserted <= 5

    db = DatabaseManager("sqlite:///./boat_race.db")
    session = db.get_session()
    try:
        races = db.get_races_by_date(session, datetime.now())
        assert len(races) >= inserted
    finally:
        session.close()
        db.close()
