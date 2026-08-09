"""Tests for scheduler CLI prediction display."""

import importlib.util
import logging
import sys
import types
from datetime import datetime
from pathlib import Path


def _load_task_scheduler_module():
    """Load task_scheduler with lightweight stubs for unrelated dependencies."""
    config_stub = types.ModuleType("config")
    config_stub.SCHEDULE_TODAY = "06:00"
    config_stub.SCHEDULE_TOMORROW = "18:00"
    config_stub.SCHEDULE_EVALUATE = "23:30"
    sys.modules.setdefault("config", config_stub)

    utils_stub = types.ModuleType("utils")
    logger_stub = types.ModuleType("utils.logger")
    logger_stub.setup_logger = lambda name: logging.getLogger(name)
    utils_stub.logger = logger_stub
    sys.modules.setdefault("utils", utils_stub)
    sys.modules["utils.logger"] = logger_stub

    module_path = Path(__file__).resolve().parents[1] / "scheduler" / "task_scheduler.py"
    spec = importlib.util.spec_from_file_location("task_scheduler_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


task_scheduler = _load_task_scheduler_module()
_display_predictions = task_scheduler._display_predictions


def test_display_predictions_groups_high_and_low_confidence(capsys):
    """Predictions should be split into high- and low-confidence sections."""
    predictions = [
        {
            "place": "戸田",
            "race_number": 1,
            "predicted_order": [1, 2, 3],
            "confidence": 0.95,
        },
        {
            "place": "平和島",
            "race_number": 2,
            "predicted_order": [4, 5, 6],
            "confidence": 0.55,
        },
    ]

    _display_predictions(predictions, "当日予想", datetime(2026, 8, 9))

    output = capsys.readouterr().out
    assert "✅ ✅ 確実性の高い予想 - 本金狙い" in output
    assert "🎯 🎪 穴確率が高い予想 - 配当狙い" in output
    assert output.index("✅ ✅ 確実性の高い予想 - 本金狙い") < output.index("🎯 🎪 穴確率が高い予想 - 配当狙い")
    assert "戸田競艇場 1レース" in output
    assert "平和島競艇場 2レース" in output


def test_display_predictions_uses_boundary_of_point_seven_for_main_section(capsys):
    """Confidence of exactly 0.7 should remain in the high-confidence section."""
    predictions = [
        {
            "place": "桐生",
            "race_number": 7,
            "predicted_order": [2, 1, 3],
            "confidence": 0.7,
        }
    ]

    _display_predictions(predictions, "当日予想", datetime(2026, 8, 9))

    output = capsys.readouterr().out
    main_section = output.split("🎯 🎪 穴確率が高い予想 - 配当狙い")[0]
    assert "桐生競艇場 7レース" in main_section
    assert "該当する予想はありません。" in output
