from datetime import datetime
from types import SimpleNamespace

from models.ensemble_model import EnsembleModel


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 30, 15, 0, 43)


def test_predict_today_filters_started_races(monkeypatch):
    races = [
        SimpleNamespace(
            race_id="past",
            date=datetime(2026, 7, 30, 14, 0, 0),
            start_time_hour=14,
            race_number=1,
            place="桐生",
            weather="sunny",
            water_condition="calm",
        ),
        SimpleNamespace(
            race_id="in_progress",
            date=datetime(2026, 7, 30, 15, 0, 0),
            start_time_hour=15,
            race_number=2,
            place="戸田",
            weather="sunny",
            water_condition="calm",
        ),
        SimpleNamespace(
            race_id="future",
            date=datetime(2026, 7, 30, 16, 0, 0),
            start_time_hour=16,
            race_number=3,
            place="江戸川",
            weather="sunny",
            water_condition="calm",
        ),
    ]

    class FakeSession:
        def close(self):
            pass

    class FakeDB:
        def get_session(self):
            return FakeSession()

        def get_races_by_date(self, session, target_date):
            return races

    monkeypatch.setattr("models.ensemble_model.get_db_manager", lambda: FakeDB(), raising=False)
    monkeypatch.setattr("models.ensemble_model.datetime", FixedDateTime)

    predictions = EnsembleModel().predict_today()

    assert [prediction["race_id"] for prediction in predictions] == ["future"]


def test_predict_tomorrow_keeps_all_races(monkeypatch):
    races = [
        SimpleNamespace(
            race_id="tomorrow-1",
            date=datetime(2026, 7, 31, 10, 0, 0),
            start_time_hour=10,
            race_number=1,
            place="桐生",
            weather="sunny",
            water_condition="calm",
        ),
        SimpleNamespace(
            race_id="tomorrow-2",
            date=datetime(2026, 7, 31, 12, 0, 0),
            start_time_hour=12,
            race_number=2,
            place="戸田",
            weather="sunny",
            water_condition="calm",
        ),
    ]

    class FakeSession:
        def close(self):
            pass

    class FakeDB:
        def get_session(self):
            return FakeSession()

        def get_races_by_date(self, session, target_date):
            return races

    monkeypatch.setattr("models.ensemble_model.get_db_manager", lambda: FakeDB(), raising=False)
    monkeypatch.setattr("models.ensemble_model.datetime", FixedDateTime)

    predictions = EnsembleModel().predict_tomorrow()

    assert [prediction["race_id"] for prediction in predictions] == ["tomorrow-1", "tomorrow-2"]
