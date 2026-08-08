"""
Tests for the new Phase 2–5 modules:
  - predictor/xgboost_model.py
  - learner/backtest.py
  - learner/failure_analyzer.py
  - learner/profit_optimizer.py
  - learner/continuous_learning.py
"""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

SAMPLE_RACE = {
    "race_id": "test-001",
    "race_number": 1,
    "wind_speed": 2.0,
    "wave_height": 3.0,
    "air_temperature": 22.0,
    "water_temperature": 20.0,
    "entries": [
        {
            "frame_number": 1,
            "player_id": "P001",
            "win_rate": 0.55,
            "place_rate": 0.70,
            "payoff_rate": 0.50,
            "avg_start_timing": 0.12,
            "recent_results": ["1", "2", "1", "3", "1"],
            "rank": "A1",
            "flying_count": 0,
            "avg_speed": 6.8,
            "boat_win_rate": 0.50,
            "boat_place_rate": 0.65,
            "engine_rate": 0.70,
            "exhibition_time": 6.75,
        },
        {
            "frame_number": 2,
            "player_id": "P002",
            "win_rate": 0.40,
            "place_rate": 0.60,
            "payoff_rate": 0.38,
            "avg_start_timing": 0.18,
            "recent_results": ["2", "1", "3", "2", "4"],
            "rank": "A2",
            "flying_count": 0,
            "avg_speed": 6.6,
            "boat_win_rate": 0.42,
            "boat_place_rate": 0.58,
            "engine_rate": 0.60,
            "exhibition_time": 6.80,
        },
        {
            "frame_number": 3,
            "player_id": "P003",
            "win_rate": 0.30,
            "place_rate": 0.50,
            "payoff_rate": 0.28,
            "avg_start_timing": 0.20,
            "recent_results": ["3", "3", "2", "5", "3"],
            "rank": "B1",
            "flying_count": 1,
            "avg_speed": 6.3,
            "boat_win_rate": 0.35,
            "boat_place_rate": 0.50,
            "engine_rate": 0.50,
            "exhibition_time": 6.90,
        },
    ],
}


# ===========================================================================
# XGBoost Model
# ===========================================================================

class TestXGBoostModel:
    """Tests for predictor/xgboost_model.py."""

    def setup_method(self):
        from predictor.xgboost_model import XGBoostModel
        self.model = XGBoostModel()

    def test_predict_returns_dict(self):
        result = self.model.predict(SAMPLE_RACE)
        assert isinstance(result, dict)

    def test_predict_has_required_keys(self):
        result = self.model.predict(SAMPLE_RACE)
        for key in ("model", "version", "prediction", "confidence", "details"):
            assert key in result, f"Missing key: {key}"

    def test_prediction_is_list_of_three(self):
        result = self.model.predict(SAMPLE_RACE)
        assert isinstance(result["prediction"], list)
        assert len(result["prediction"]) == 3

    def test_confidence_in_valid_range(self):
        result = self.model.predict(SAMPLE_RACE)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_model_name(self):
        assert self.model.model_name == "xgboost"

    def test_empty_entries_returns_empty_prediction(self):
        result = self.model.predict({"entries": []})
        assert result["prediction"] == []
        assert result["confidence"] == 0.0

    def test_predict_winner(self):
        result = self.model.predict_winner(SAMPLE_RACE)
        assert "winner" in result
        assert result["winner"] is not None

    def test_predict_order(self):
        result = self.model.predict_order(SAMPLE_RACE)
        assert "order" in result
        assert len(result["order"]) == 3

    def test_predict_probability(self):
        result = self.model.predict_probability(SAMPLE_RACE)
        assert "probabilities" in result
        probs = result["probabilities"]
        assert len(probs) == len(SAMPLE_RACE["entries"])
        for p in probs.values():
            assert 0.0 <= p <= 1.0

    def test_predict_payout(self):
        result = self.model.predict_payout(SAMPLE_RACE)
        assert "payout" in result
        assert "win" in result["payout"]
        assert result["payout"]["win"] >= 0.0

    def test_details_contains_method(self):
        result = self.model.predict(SAMPLE_RACE)
        assert result["details"].get("method") == "gradient_boosting"

    def test_lane_advantage_influences_score(self):
        """Frame 1 (inner lane) should receive a positive bonus."""
        result = self.model.predict(SAMPLE_RACE)
        # With strong inner player P001 (frame 1) and high win_rate, it
        # should appear in the top 3.
        assert "P001" in result["prediction"] or 1 in result["prediction"]


# ===========================================================================
# Backtest
# ===========================================================================

class TestBacktest:
    """Tests for learner/backtest.py."""

    def _make_model(self, prediction):
        """Create a mock model that always returns the given prediction."""
        m = MagicMock()
        m.predict.return_value = prediction
        return m

    def _make_past_race(self, race_id, actual):
        return {
            "race_id": race_id,
            "venue": "桐生",
            "race_number": 1,
            "entries": SAMPLE_RACE["entries"],
            "actual_result": actual,
            "odds": 12.0,
        }

    def test_backtest_returns_result(self):
        from learner.backtest import backtest
        model = self._make_model({"prediction": ["P001", "P002", "P003"], "confidence": 0.75})
        races = [self._make_past_race("r1", ["P001", "P002", "P003"])]
        result = backtest(model, races)
        assert result.total_races == 1

    def test_backtest_hit_on_correct_prediction(self):
        from learner.backtest import backtest
        model = self._make_model({"prediction": ["P001", "P002", "P003"], "confidence": 0.75})
        races = [self._make_past_race("r1", ["P001", "P002", "P003"])]
        result = backtest(model, races)
        assert result.hits == 1
        assert result.hit_rate == 1.0

    def test_backtest_miss_on_wrong_prediction(self):
        from learner.backtest import backtest
        model = self._make_model({"prediction": ["P001", "P003", "P002"], "confidence": 0.50})
        races = [self._make_past_race("r1", ["P001", "P002", "P003"])]
        result = backtest(model, races)
        assert result.hits == 0
        assert result.hit_rate == 0.0

    def test_backtest_recovery_rate(self):
        from learner.backtest import backtest
        model = self._make_model({"prediction": ["P001", "P002", "P003"], "confidence": 0.80})
        races = [self._make_past_race("r1", ["P001", "P002", "P003"])]
        result = backtest(model, races, bet_amount=100.0)
        # odds=12.0 → payout=1200, bet=100 → recovery=12.0
        assert result.recovery_rate == pytest.approx(12.0)

    def test_backtest_skips_races_without_actual_result(self):
        from learner.backtest import backtest
        model = self._make_model({"prediction": ["P001", "P002", "P003"], "confidence": 0.75})
        races = [{"race_id": "r1", "entries": [], "actual_result": []}]
        result = backtest(model, races)
        assert result.total_races == 0

    def test_backtest_by_confidence_buckets(self):
        from learner.backtest import backtest
        model = self._make_model({"prediction": ["P001", "P002", "P003"], "confidence": 0.85})
        races = [self._make_past_race("r1", ["P001", "P002", "P003"])]
        result = backtest(model, races)
        assert "high (≥80%)" in result.by_confidence

    def test_backtest_by_venue(self):
        from learner.backtest import backtest
        model = self._make_model({"prediction": ["P001", "P002", "P003"], "confidence": 0.75})
        races = [self._make_past_race("r1", ["P001", "P002", "P003"])]
        result = backtest(model, races)
        assert "桐生" in result.by_venue

    def test_backtest_to_dict(self):
        from learner.backtest import backtest
        model = self._make_model({"prediction": ["P001", "P002", "P003"], "confidence": 0.75})
        races = [self._make_past_race("r1", ["P001", "P002", "P003"])]
        result = backtest(model, races)
        d = result.to_dict()
        for key in ("total_races", "hits", "hit_rate", "recovery_rate", "by_confidence", "by_venue"):
            assert key in d

    def test_backtest_multiple_races(self):
        from learner.backtest import backtest
        call_count = [0]
        def side_effect(race):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                return {"prediction": ["P001", "P002", "P003"], "confidence": 0.75}
            return {"prediction": ["P003", "P002", "P001"], "confidence": 0.45}
        model = MagicMock()
        model.predict.side_effect = side_effect
        races = [
            self._make_past_race("r1", ["P001", "P002", "P003"]),
            self._make_past_race("r2", ["P001", "P002", "P003"]),
            self._make_past_race("r3", ["P001", "P002", "P003"]),
            self._make_past_race("r4", ["P001", "P002", "P003"]),
        ]
        result = backtest(model, races)
        assert result.total_races == 4
        assert result.hits == 2


# ===========================================================================
# Failure Analyzer
# ===========================================================================

class TestFailureAnalyzer:
    """Tests for learner/failure_analyzer.py."""

    def _make_failure(self, predicted, actual, confidence=0.5):
        return {
            "predicted": predicted,
            "actual": actual,
            "confidence": confidence,
            "details": {},
        }

    def test_analyze_failure_returns_dict(self):
        from learner.failure_analyzer import analyze_failure
        pred = {"prediction": ["P002", "P003", "P001"], "confidence": 0.5}
        result = analyze_failure(pred, ["P001", "P002", "P003"])
        assert isinstance(result, dict)

    def test_analyze_failure_has_category(self):
        from learner.failure_analyzer import analyze_failure
        pred = {"prediction": ["P002", "P003", "P001"], "confidence": 0.5}
        result = analyze_failure(pred, ["P001", "P002", "P003"])
        assert "category" in result
        assert result["category"] != ""

    def test_analyze_failure_has_recommendations(self):
        from learner.failure_analyzer import analyze_failure
        pred = {"prediction": ["P002", "P003", "P001"], "confidence": 0.5}
        result = analyze_failure(pred, ["P001", "P002", "P003"])
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    def test_high_confidence_wrong_is_confidence_error(self):
        from learner.failure_analyzer import analyze_failure, CATEGORY_CONFIDENCE_ERROR
        pred = {"prediction": ["P002", "P003", "P001"], "confidence": 0.90}
        result = analyze_failure(pred, ["P001", "P002", "P003"])
        assert result["category"] == CATEGORY_CONFIDENCE_ERROR

    def test_analyze_failures_returns_summary(self):
        from learner.failure_analyzer import analyze_failures
        failures = [
            self._make_failure(["P002"], ["P001", "P002", "P003"], 0.5),
            self._make_failure(["P002"], ["P001", "P002", "P003"], 0.9),
        ]
        result = analyze_failures(failures)
        assert "total_failures" in result
        assert result["total_failures"] == 2

    def test_analyze_failures_empty(self):
        from learner.failure_analyzer import analyze_failures
        result = analyze_failures([])
        assert result["total_failures"] == 0
        assert result["top_category"] is None

    def test_analyze_failures_improvement_plan(self):
        from learner.failure_analyzer import analyze_failures
        failures = [
            self._make_failure(["P002"], ["P001", "P002", "P003"], 0.9)
            for _ in range(10)
        ]
        result = analyze_failures(failures)
        assert "improvement_plan" in result
        assert isinstance(result["improvement_plan"], list)

    def test_improvement_summary_is_string(self):
        from learner.failure_analyzer import analyze_failures, improvement_summary
        failures = [self._make_failure(["P002"], ["P001", "P002", "P003"], 0.5)]
        analysis = analyze_failures(failures)
        summary = improvement_summary(analysis)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_all_categories_have_labels(self):
        from learner.failure_analyzer import _CATEGORY_LABELS_JA, _ALL_CATEGORIES
        for cat in _ALL_CATEGORIES:
            assert cat in _CATEGORY_LABELS_JA, f"Missing label for {cat}"


# ===========================================================================
# Profit Optimizer
# ===========================================================================

class TestProfitOptimizer:
    """Tests for learner/profit_optimizer.py."""

    def _make_prediction(self, race_id, confidence, odds):
        return {
            "race_id": race_id,
            "place": "桐生",
            "race_number": 1,
            "prediction": ["P001", "P002", "P003"],
            "confidence": confidence,
            "estimated_odds": odds,
        }

    def test_select_races_returns_list(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer()
        result = opt.select_races([])
        assert isinstance(result, list)

    def test_high_confidence_high_odds_is_selected(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer(min_confidence=0.70, min_expected_odds=5.0)
        preds = [self._make_prediction("r1", confidence=0.80, odds=10.0)]
        result = opt.select_races(preds, bankroll=10000)
        assert len(result) == 1
        assert result[0]["is_recommended"] is True

    def test_low_confidence_is_rejected(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer(min_confidence=0.70)
        preds = [self._make_prediction("r1", confidence=0.50, odds=10.0)]
        result = opt.select_races(preds, bankroll=10000)
        assert len(result) == 0

    def test_low_odds_is_rejected(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer(min_expected_odds=5.0)
        preds = [self._make_prediction("r1", confidence=0.80, odds=2.0)]
        result = opt.select_races(preds, bankroll=10000)
        assert len(result) == 0

    def test_optimize_bet_size_kelly(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer()
        bet = opt.optimize_bet_size(confidence=0.80, estimated_odds=10.0, bankroll=10000)
        assert bet > 0
        assert bet <= 10000 * opt.max_bet_fraction

    def test_optimize_bet_size_zero_for_negative_ev(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer()
        # confidence=0.05, odds=2 → Kelly is negative
        bet = opt.optimize_bet_size(confidence=0.05, estimated_odds=2.0, bankroll=10000)
        assert bet == 0.0

    def test_expected_value_computed(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer()
        eval_result = opt.evaluate_race(
            {"confidence": 0.85, "estimated_odds": 8.0}, bankroll=10000
        )
        assert eval_result["expected_value"] == pytest.approx(0.85 * 8.0)

    def test_generate_report(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer(min_confidence=0.70, min_expected_odds=5.0)
        preds = [self._make_prediction("r1", 0.80, 10.0)]
        selected = opt.select_races(preds, bankroll=10000)
        report = opt.generate_report(selected, bankroll=10000)
        assert "total_races_recommended" in report
        assert "total_bet" in report
        assert "weighted_expected_value" in report

    def test_select_races_sorted_by_ev(self):
        from learner.profit_optimizer import ProfitOptimizer
        opt = ProfitOptimizer(min_confidence=0.70, min_expected_odds=5.0)
        preds = [
            self._make_prediction("r1", 0.75, 8.0),   # EV=6.0
            self._make_prediction("r2", 0.80, 10.0),  # EV=8.0
            self._make_prediction("r3", 0.70, 6.0),   # EV=4.2
        ]
        selected = opt.select_races(preds, bankroll=10000)
        evs = [r["expected_value"] for r in selected]
        assert evs == sorted(evs, reverse=True)

    def test_module_level_select_races(self):
        from learner.profit_optimizer import select_races
        preds = [self._make_prediction("r1", 0.80, 10.0)]
        result = select_races(preds, bankroll=10000, min_confidence=0.70, min_expected_odds=5.0)
        assert isinstance(result, list)


# ===========================================================================
# Continuous Learning
# ===========================================================================

class TestContinuousLearning:
    """Tests for learner/continuous_learning.py."""

    def _make_model(self):
        m = MagicMock()
        m.predict.return_value = {
            "prediction": ["P001", "P002", "P003"],
            "confidence": 0.75,
        }
        m.retrain.return_value = {"status": "ok"}
        return m

    def test_init_succeeds(self, tmp_path):
        from learner.continuous_learning import ContinuousLearning
        model = self._make_model()
        cl = ContinuousLearning(model, state_file=str(tmp_path / "history.json"))
        assert cl is not None

    def test_get_history_empty_initially(self, tmp_path):
        from learner.continuous_learning import ContinuousLearning
        cl = ContinuousLearning(self._make_model(), state_file=str(tmp_path / "h.json"))
        assert cl.get_history() == []

    def test_daily_cycle_returns_summary(self, tmp_path):
        from learner.continuous_learning import ContinuousLearning
        cl = ContinuousLearning(self._make_model(), state_file=str(tmp_path / "h.json"))
        # Mock DB calls to avoid actual DB access
        with patch.object(cl, "_fetch_today_races", return_value=[]), \
             patch.object(cl, "_fetch_yesterday_results", return_value=[]):
            summary = cl.daily_cycle()
        assert "date" in summary
        assert "predictions_made" in summary

    def test_daily_cycle_saves_history(self, tmp_path):
        from learner.continuous_learning import ContinuousLearning
        state_file = str(tmp_path / "h.json")
        cl = ContinuousLearning(self._make_model(), state_file=state_file)
        with patch.object(cl, "_fetch_today_races", return_value=[]), \
             patch.object(cl, "_fetch_yesterday_results", return_value=[]):
            cl.daily_cycle()
        assert len(cl._history) == 1

    def test_get_performance_trend(self, tmp_path):
        from learner.continuous_learning import ContinuousLearning
        cl = ContinuousLearning(self._make_model(), state_file=str(tmp_path / "h.json"))
        # Seed some history
        cl._history = [
            {"date": "2026-07-01", "accuracy": {"hit_rate": 0.04, "recovery_rate": 0.8}},
            {"date": "2026-07-02", "accuracy": {"hit_rate": 0.05, "recovery_rate": 0.9}},
        ]
        trend = cl.get_performance_trend()
        assert "hit_rate_trend" in trend
        assert len(trend["hit_rate_trend"]) == 2
        assert trend["latest_hit_rate"] == pytest.approx(0.05)

    def test_maybe_deploy_deploys_on_improvement(self, tmp_path):
        from learner.continuous_learning import ContinuousLearning
        cl = ContinuousLearning(self._make_model(), state_file=str(tmp_path / "h.json"))
        cl._previous_accuracy = 0.04
        assert cl._maybe_deploy(0.05) is True  # 0.05 > 0.04 + 0.001

    def test_maybe_deploy_skips_without_improvement(self, tmp_path):
        from learner.continuous_learning import ContinuousLearning
        cl = ContinuousLearning(self._make_model(), state_file=str(tmp_path / "h.json"))
        cl._previous_accuracy = 0.05
        assert cl._maybe_deploy(0.05) is False


# ===========================================================================
# New API endpoints
# ===========================================================================

class TestNewApiEndpoints:
    """Tests for /api/backtest, /api/optimize, /api/failure-analysis."""

    @pytest.fixture
    def client(self):
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_backtest_missing_body_returns_400(self, client):
        import json
        resp = client.post(
            "/api/backtest",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_backtest_valid_request(self, client):
        import json
        body = {
            "races": [
                {
                    "race_id": "test-bt-1",
                    "venue": "桐生",
                    "race_number": 1,
                    "entries": SAMPLE_RACE["entries"],
                    "actual_result": ["P001", "P002", "P003"],
                    "odds": 10.0,
                }
            ],
            "model": "ensemble",
            "bet_amount": 100,
        }
        resp = client.post(
            "/api/backtest",
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "hit_rate" in data
        assert "recovery_rate" in data
        assert "total_races" in data

    def test_optimize_missing_body_returns_400(self, client):
        import json
        resp = client.post(
            "/api/optimize",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_optimize_valid_request(self, client):
        import json
        body = {
            "predictions": [
                {
                    "race_id": "r1",
                    "place": "桐生",
                    "race_number": 1,
                    "prediction": ["P001", "P002", "P003"],
                    "confidence": 0.80,
                    "estimated_odds": 10.0,
                }
            ],
            "bankroll": 10000,
        }
        resp = client.post(
            "/api/optimize",
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "total_races_recommended" in data
        assert "total_bet" in data

    def test_failure_analysis_missing_body_returns_400(self, client):
        import json
        resp = client.post(
            "/api/failure-analysis",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_failure_analysis_valid_request(self, client):
        import json
        body = {
            "failures": [
                {
                    "predicted": ["P002", "P003", "P001"],
                    "actual": ["P001", "P002", "P003"],
                    "confidence": 0.50,
                    "race_id": "test-f1",
                }
            ]
        }
        resp = client.post(
            "/api/failure-analysis",
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "total_failures" in data
        assert data["total_failures"] == 1
        assert "improvement_plan" in data


# ===========================================================================
# XGBoost included in run_all_predictions
# ===========================================================================

def test_run_all_predictions_includes_xgboost():
    """run_all_predictions should include the xgboost model."""
    from main import run_all_predictions
    results = run_all_predictions(SAMPLE_RACE)
    assert "xgboost" in results
    xgb = results["xgboost"]
    assert "prediction" in xgb
    assert "confidence" in xgb


def test_xgboost_in_api_models_info():
    """GET /api/models/info should include xgboost."""
    import json
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        resp = client.get("/api/models/info")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "xgboost" in data["models"]
