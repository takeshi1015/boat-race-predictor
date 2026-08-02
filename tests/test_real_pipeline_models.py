from datetime import datetime

import numpy as np

from models.ml_ensemble import MLEnsembleModel
from models.statistical_model import StatisticalRaceModel
from scrapers.official_scraper import OfficialBoatraceScraper


class _DummyResponse:
    def __init__(self, text: str):
        self.text = text


def test_official_scraper_parse_result_with_mocked_html(monkeypatch):
    html = """
    <html><body>
      <table>
        <tr><td>1</td><td>2</td></tr>
        <tr><td>2</td><td>1</td></tr>
        <tr><td>3</td><td>3</td></tr>
      </table>
      <div>天候:晴 風速:3m 水面:calm</div>
      <div>3連単 2-1-3 1240</div>
      <table>
        <tr><td>1</td><td>5010</td><td>選手A</td><td>45</td></tr>
        <tr><td>2</td><td>5020</td><td>選手B</td><td>46</td></tr>
      </table>
    </body></html>
    """
    scraper = OfficialBoatraceScraper()

    monkeypatch.setattr(scraper, "_request", lambda *args, **kwargs: _DummyResponse(html))
    data = scraper.fetch_race_result("20260801", "01", 1)

    assert data is not None
    assert data["race_id"] == "20260801_01_01"
    assert data["result"]["finish_order"] == [2, 1, 3]
    assert data["result"]["odds"]["trifecta"] == 1240.0


def test_statistical_model_scores_and_confidence():
    model = StatisticalRaceModel()
    race_data = {
        "weather": "sunny",
        "water_condition": "calm",
        "entries": [
            {"player_id": "A", "lane": 1, "recent_5_win_rate": 0.8, "motor_recent_10_rate": 0.7, "venue_win_rate": 0.75},
            {"player_id": "B", "lane": 2, "recent_5_win_rate": 0.6, "motor_recent_10_rate": 0.55, "venue_win_rate": 0.6},
            {"player_id": "C", "lane": 6, "recent_5_win_rate": 0.2, "motor_recent_10_rate": 0.3, "venue_win_rate": 0.25},
        ],
    }

    result = model.predict(race_data)
    assert result["prediction"][0] == "A"
    assert 0.0 <= result["confidence"] <= 1.0
    assert all(0.0 <= row["score"] <= 100.0 for row in result["scores"])


def test_ml_ensemble_predict_top3():
    x = np.array([[1, 10, 2] * 6, [2, 20, 3] * 6, [3, 30, 1] * 6, [4, 40, 2] * 6, [5, 50, 3] * 6, [6, 60, 1] * 6])
    y = np.array([0, 1, 2, 3, 4, 5])

    model = MLEnsembleModel()
    model.fit(x, y)

    prediction = model.predict_top3(x[:1], statistical_scores=np.array([0.4, 0.2, 0.1, 0.1, 0.1, 0.1]))

    assert len(prediction["prediction"]) == 3
    assert 0.0 <= prediction["confidence"] <= 1.0
