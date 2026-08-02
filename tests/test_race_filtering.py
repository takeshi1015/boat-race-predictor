"""
Tests for race purchase filtering logic.

Covers:
  - is_race_purchasable() from models/xgboost_predictor.py
  - is_race_finished() from scrapers/official_scraper.py and models/xgboost_predictor.py
  - EnsembleModel purchasable race filtering
  - /api/races/today endpoint purchasable filtering
"""

from datetime import datetime, timedelta

import pytest
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# is_race_purchasable
# ---------------------------------------------------------------------------

class TestIsRacePurchasable:
    """Unit tests for the is_race_purchasable() function."""

    def _fn(self, race_start_time, current_time):
        from models.xgboost_predictor import is_race_purchasable
        return is_race_purchasable(race_start_time, current_time)

    def test_race_more_than_10_min_away_is_purchasable(self):
        """A race 11 minutes in the future should be purchasable."""
        now = datetime(2026, 8, 2, 10, 0, 0)
        race = now + timedelta(minutes=11)
        assert self._fn(race, now) is True

    def test_race_exactly_10_min_away_is_purchasable(self):
        """A race exactly 10 minutes away IS purchasable (condition is < 10)."""
        now = datetime(2026, 8, 2, 10, 0, 0)
        race = now + timedelta(minutes=10)
        assert self._fn(race, now) is True

    def test_race_less_than_10_min_away_is_not_purchasable(self):
        """A race 9 minutes away should NOT be purchasable."""
        now = datetime(2026, 8, 2, 10, 0, 0)
        race = now + timedelta(minutes=9)
        assert self._fn(race, now) is False

    def test_race_in_past_is_not_purchasable(self):
        """A race that has already started is NOT purchasable."""
        now = datetime(2026, 8, 2, 10, 30, 0)
        race = now - timedelta(minutes=5)
        assert self._fn(race, now) is False

    def test_race_at_same_time_is_not_purchasable(self):
        """A race starting right now is NOT purchasable."""
        now = datetime(2026, 8, 2, 10, 30, 0)
        assert self._fn(now, now) is False

    def test_race_far_in_future_is_purchasable(self):
        """A race 3 hours away should definitely be purchasable."""
        now = datetime(2026, 8, 2, 9, 0, 0)
        race = now + timedelta(hours=3)
        assert self._fn(race, now) is True

    def test_night_race_is_purchasable_during_day(self):
        """A 20:00 night race is purchasable when it's 10:00."""
        now = datetime(2026, 8, 2, 10, 0, 0)
        race = datetime(2026, 8, 2, 20, 0, 0)
        assert self._fn(race, now) is True

    def test_late_night_race_after_23_is_not_purchasable_if_past(self):
        """A 23:00 race should not be purchasable if current time is 23:01."""
        now = datetime(2026, 8, 2, 23, 1, 0)
        race = datetime(2026, 8, 2, 23, 0, 0)
        assert self._fn(race, now) is False


# ---------------------------------------------------------------------------
# minutes_until_race
# ---------------------------------------------------------------------------

class TestMinutesUntilRace:
    """Unit tests for the minutes_until_race() helper."""

    def test_returns_positive_for_future_race(self):
        from models.xgboost_predictor import minutes_until_race
        now = datetime(2026, 8, 2, 10, 0, 0)
        race = now + timedelta(minutes=30)
        result = minutes_until_race(race, now)
        assert abs(result - 30.0) < 0.01

    def test_returns_negative_for_past_race(self):
        from models.xgboost_predictor import minutes_until_race
        now = datetime(2026, 8, 2, 10, 0, 0)
        race = now - timedelta(minutes=15)
        result = minutes_until_race(race, now)
        assert result < 0


# ---------------------------------------------------------------------------
# is_race_finished
# ---------------------------------------------------------------------------

class TestIsRaceFinished:
    """Unit tests for is_race_finished()."""

    def _fn(self, html_str):
        from models.xgboost_predictor import is_race_finished
        soup = BeautifulSoup(html_str, "html.parser")
        return is_race_finished(soup)

    def test_returns_false_for_empty_page(self):
        assert self._fn("<html><body></body></html>") is False

    def test_returns_true_for_is_result_class(self):
        html = '<html><body><div class="is-result">確定</div></body></html>'
        assert self._fn(html) is True

    def test_returns_true_for_is_fixed_class(self):
        html = '<html><body><div class="is-fixed">着順確定</div></body></html>'
        assert self._fn(html) is True

    def test_returns_true_for_data_status_confirmed(self):
        html = '<html><body><div data-status="confirmed">ok</div></body></html>'
        assert self._fn(html) is True

    def test_returns_true_for_confirmed_text_with_result_section(self):
        html = (
            '<html><body>'
            '<div class="race-result">'
            '<p>着順確定</p>'
            '</div>'
            '</body></html>'
        )
        assert self._fn(html) is True

    def test_returns_false_for_non_result_page(self):
        html = (
            '<html><body>'
            '<table><tr><td>10:30</td><td>1R</td></tr></table>'
            '</body></html>'
        )
        assert self._fn(html) is False


# ---------------------------------------------------------------------------
# RACE_TICKET_CUTOFF_MINUTES constant
# ---------------------------------------------------------------------------

def test_purchase_cutoff_is_10_minutes():
    """The ticket cutoff must be 10 minutes (not 5)."""
    from models.ensemble_model import RACE_TICKET_CUTOFF_MINUTES
    assert RACE_TICKET_CUTOFF_MINUTES == 10


def test_xgboost_cutoff_is_10_minutes():
    """The xgboost_predictor cutoff constant must be 10 minutes."""
    from models.xgboost_predictor import PURCHASE_CUTOFF_MINUTES
    assert PURCHASE_CUTOFF_MINUTES == 10


# ---------------------------------------------------------------------------
# EnsembleModel prediction fields
# ---------------------------------------------------------------------------

class TestEnsembleModelPredictionFields:
    """Verify that _predict_race() returns the new required fields."""

    def _make_mock_race(self, race_dt):
        """Create a minimal mock race object."""
        class MockRace:
            race_id = "test-001"
            place = "桐生"
            venue = "桐生"
            race_number = 1
            weather = "sunny"
            water_condition = "calm"
            start_time_hour = race_dt.hour
            date = race_dt
            result = None

        return MockRace()

    def test_predict_race_has_time_until_start_minutes(self):
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        future = datetime.now() + timedelta(hours=2)
        race = self._make_mock_race(future)
        pred = model._predict_race(race)
        assert pred is not None
        assert "time_until_start_minutes" in pred
        assert pred["time_until_start_minutes"] >= 0

    def test_predict_race_has_is_recommended(self):
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        future = datetime.now() + timedelta(hours=2)
        race = self._make_mock_race(future)
        pred = model._predict_race(race)
        assert pred is not None
        assert "is_recommended" in pred
        assert isinstance(pred["is_recommended"], bool)

    def test_predict_race_future_is_purchasable(self):
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        future = datetime.now() + timedelta(hours=2)
        race = self._make_mock_race(future)
        pred = model._predict_race(race)
        assert pred is not None
        assert pred["is_purchasable"] is True

    def test_predict_race_past_is_not_purchasable(self):
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        past = datetime.now() - timedelta(hours=1)
        race = self._make_mock_race(past)
        pred = model._predict_race(race)
        assert pred is not None
        assert pred["is_purchasable"] is False


# ---------------------------------------------------------------------------
# /api/races/today endpoint
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a Flask test client."""
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_api_races_today_has_current_time(client):
    """GET /api/races/today should return current_time field."""
    response = client.get("/api/races/today")
    assert response.status_code == 200
    import json
    data = json.loads(response.data)
    assert "current_time" in data


def test_api_races_today_has_count(client):
    """GET /api/races/today should return a count field."""
    response = client.get("/api/races/today")
    assert response.status_code == 200
    import json
    data = json.loads(response.data)
    assert "count" in data
    assert isinstance(data["count"], int)


def test_api_races_today_predictions_are_purchasable(client):
    """All predictions in /api/races/today must have is_purchasable=True."""
    response = client.get("/api/races/today")
    assert response.status_code == 200
    import json
    data = json.loads(response.data)
    predictions = data.get("predictions", [])
    for pred in predictions:
        assert pred.get("is_purchasable") is True, (
            f"Non-purchasable race found: {pred.get('place')} R{pred.get('race_number')}"
            f" start_time={pred.get('race_time')}"
        )


def test_api_races_today_has_time_until_start(client):
    """Predictions should include time_until_start_minutes."""
    response = client.get("/api/races/today")
    assert response.status_code == 200
    import json
    data = json.loads(response.data)
    for pred in data.get("predictions", []):
        assert "time_until_start_minutes" in pred
        assert pred["time_until_start_minutes"] >= 0


def test_api_races_today_has_is_recommended(client):
    """Predictions should include is_recommended field."""
    response = client.get("/api/races/today")
    assert response.status_code == 200
    import json
    data = json.loads(response.data)
    for pred in data.get("predictions", []):
        assert "is_recommended" in pred
        assert isinstance(pred["is_recommended"], bool)
