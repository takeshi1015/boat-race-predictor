"""主要機能の動作確認スクリプト."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))


def run(cmd: str):
    print(f"\n$ {cmd}")
    result = subprocess.run(cmd, cwd=ROOT, shell=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    run("python scripts/init_test_data.py")
    run("python scripts/predict_today.py")
    run("python scripts/predict_tomorrow.py")
    run("python scripts/analyze_performance.py")
    run("python scripts/retrain_model.py")
    run("python scripts/stats_display.py")
    print("\n✅ verify_app 完了")
