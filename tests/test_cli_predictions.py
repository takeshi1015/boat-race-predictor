"""Tests for CLI prediction flow."""

import subprocess
from datetime import datetime

from database.db_manager import get_db_manager
from database.models import Race
from utils.statistics import purchase_label


def test_purchase_label_threshold():
    assert purchase_label(0.70, 0.7) == "購入可能"
    assert purchase_label(0.69, 0.7) == "参考情報"


def test_init_test_data_creates_today_races():
    subprocess.run(["python", "scripts/init_test_data.py"], check=True)
    db = get_db_manager()
    session = db.get_session()
    try:
        start = datetime.combine(datetime.now().date(), datetime.min.time())
        end = datetime.combine(datetime.now().date(), datetime.max.time())
        count = session.query(Race).filter(Race.date.between(start, end)).count()
        assert count >= 5
    finally:
        session.close()


def test_main_help_mode_outputs_startup_guide():
    result = subprocess.run(
        ["python", "main.py", "--mode", "help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "ボートレース予測システム v1.0" in result.stdout
    assert "【当日予想】" in result.stdout
    assert "【翌日予想】" in result.stdout
