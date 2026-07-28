"""Tests for CLI prediction flow."""

import os
import sqlite3
import subprocess
from datetime import datetime, timedelta

from database.db_manager import get_db_manager
from database.models import Race
from scripts.init_test_data import main as init_test_data_main
from utils.statistics import purchase_label


def test_purchase_label_threshold():
    assert purchase_label(0.70, 0.7) == "購入可能"
    assert purchase_label(0.69, 0.7) == "参考情報"


def test_init_test_data_creates_today_races():
    init_test_data_main()
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


def test_predict_tomorrow_bootstraps_when_db_is_empty(tmp_path):
    db_file = tmp_path / "tomorrow_only.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_file}"
    env["OUTPUTS_DIR"] = str(tmp_path / "outputs")
    result = subprocess.run(
        ["python", "main.py", "--mode", "predict-tomorrow"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "【翌日予想】" in result.stdout
    assert "購入可能予想" in result.stdout
    assert "予測対象レースがありません。" not in result.stdout

    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
    with sqlite3.connect(db_file) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM races WHERE substr(date, 1, 10) = ?",
            (tomorrow,),
        ).fetchone()
    assert row is not None and row[0] >= 1
