from datetime import datetime
from types import SimpleNamespace

from models.ensemble_model import EnsembleModel


def test_predict_single_race_returns_prediction_payload():
    model = EnsembleModel()
    race = SimpleNamespace(
        race_id="RACE-001",
        place="桐生",
        race_number=1,
        date=datetime.now(),
        weather="sunny",
        water_condition="calm",
        start_time_hour=12,
    )

    prediction = model._predict_single_race(race)

    assert prediction is not None
    assert prediction["race_id"] == "RACE-001"
    assert prediction["place"] == "桐生"
    assert "predicted_order" in prediction
    assert "race_time" in prediction
    assert "purchase_deadline" in prediction
    assert "is_purchasable" in prediction
    assert "time_remaining" in prediction


def test_predict_today_fetches_races_and_closes_session(monkeypatch):
    model = EnsembleModel()
    race = SimpleNamespace(
        race_id="RACE-002",
        place="戸田",
        race_number=2,
        date=datetime.now(),
        weather="sunny",
        water_condition="calm",
        start_time_hour=12,
    )

    class FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return [race]

    class FakeSession:
        def __init__(self):
            self.closed = False

        def query(self, *_args, **_kwargs):
            return FakeQuery()

        def close(self):
            self.closed = True

    fake_session = FakeSession()

    class FakeDBManager:
        def get_session(self):
            return fake_session

    import database.db_manager as db_manager

    monkeypatch.setattr(db_manager, "get_db_manager", lambda: FakeDBManager())

    predictions = model.predict_today()

    assert len(predictions) == 1
    assert predictions[0]["race_id"] == "RACE-002"
    assert fake_session.closed is True


def test_predict_single_race_passes_period(monkeypatch):
    model = EnsembleModel()
    race = SimpleNamespace(race_id="RACE-003")
    captured = {}

    def fake_predict_race(_race, period):
        captured["period"] = period
        return {"race_id": _race.race_id}

    monkeypatch.setattr(model, "_predict_race", fake_predict_race)

    result = model._predict_single_race(race, "tomorrow")

    assert result["race_id"] == "RACE-003"
    assert captured["period"] == "tomorrow"
