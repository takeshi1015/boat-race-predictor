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
            date=FixedDateTime(2026, 7, 30, 14, 0, 0),
            start_time_hour=14,
            race_number=1,
            place="桐生",
            weather="sunny",
            water_condition="calm",
        ),
        SimpleNamespace(
            race_id="in_progress",
            date=FixedDateTime(2026, 7, 30, 15, 0, 0),
            start_time_hour=15,
            race_number=2,
            place="戸田",
            weather="sunny",
            water_condition="calm",
        ),
        SimpleNamespace(
            race_id="future",
            date=FixedDateTime(2026, 7, 30, 16, 0, 0),
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

    monkeypatch.setattr("database.db_manager.get_db_manager", lambda: FakeDB())
    monkeypatch.setattr("models.ensemble_model.datetime", FixedDateTime)
    monkeypatch.setattr(
        EnsembleModel,
        "_get_operating_venues_today",
        staticmethod(lambda: {"桐生", "戸田", "江戸川"}),
    )

    predictions = EnsembleModel().predict_today()

    assert [prediction["race_id"] for prediction in predictions] == ["future"]


def test_predict_tomorrow_keeps_all_races(monkeypatch):
    races = [
        SimpleNamespace(
            race_id="tomorrow-1",
            date=FixedDateTime(2026, 7, 31, 10, 0, 0),
            start_time_hour=10,
            race_number=1,
            place="桐生",
            weather="sunny",
            water_condition="calm",
        ),
        SimpleNamespace(
            race_id="tomorrow-2",
            date=FixedDateTime(2026, 7, 31, 12, 0, 0),
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

    monkeypatch.setattr("database.db_manager.get_db_manager", lambda: FakeDB())
    monkeypatch.setattr("models.ensemble_model.datetime", FixedDateTime)

    predictions = EnsembleModel().predict_tomorrow()

    assert [prediction["race_id"] for prediction in predictions] == ["tomorrow-1", "tomorrow-2"]


def test_predict_today_filters_non_operating_venues(monkeypatch):
    races = [
        SimpleNamespace(
            race_id="operating",
            date=FixedDateTime(2026, 7, 30, 16, 0, 0),
            start_time_hour=16,
            race_number=1,
            place="丸亀",
            venue="丸亀",
            weather="sunny",
            water_condition="calm",
        ),
        SimpleNamespace(
            race_id="non-operating",
            date=FixedDateTime(2026, 7, 30, 17, 0, 0),
            start_time_hour=17,
            race_number=2,
            place="桐生",
            venue="桐生",
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

    monkeypatch.setattr("database.db_manager.get_db_manager", lambda: FakeDB())
    monkeypatch.setattr("models.ensemble_model.datetime", FixedDateTime)
    monkeypatch.setattr(
        EnsembleModel,
        "_get_operating_venues_today",
        staticmethod(lambda: {"丸亀"}),
    )

    predictions = EnsembleModel().predict_today()

    assert [prediction["race_id"] for prediction in predictions] == ["operating"]


def test_predict_today_filters_non_purchasable_predictions(monkeypatch):
    races = [
        SimpleNamespace(race_id="low-confidence"),
        SimpleNamespace(race_id="high-confidence"),
    ]

    class FakeSession:
        def close(self):
            pass

    class FakeDB:
        def get_session(self):
            return FakeSession()

        def get_races_by_date(self, session, target_date):
            return races

    def fake_predict_race(self, race):
        confidence = 0.55 if race.race_id == "low-confidence" else 0.85
        return {
            "race_id": race.race_id,
            "place": "丸亀",
            "race_number": 1,
            "predicted_order": [1, 2, 3],
            "confidence": confidence,
            "reason": "test",
        }

    monkeypatch.setattr("database.db_manager.get_db_manager", lambda: FakeDB())
    monkeypatch.setattr("models.ensemble_model.datetime", FixedDateTime)
    monkeypatch.setattr(
        EnsembleModel,
        "_get_operating_venues_today",
        staticmethod(lambda: set()),
    )
    monkeypatch.setattr(EnsembleModel, "_get_race_start_datetime", staticmethod(lambda race: None))
    monkeypatch.setattr(EnsembleModel, "_predict_race", fake_predict_race)

    predictions = EnsembleModel().predict_today()

    assert [prediction["race_id"] for prediction in predictions] == ["high-confidence"]
