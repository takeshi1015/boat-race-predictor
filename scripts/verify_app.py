"""主要機能の動作確認スクリプト."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))


def execute_verification_step(cmd):
    print(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    python = sys.executable
    execute_verification_step([python, os.path.join(ROOT, "scripts/init_test_data.py")])
    execute_verification_step([python, os.path.join(ROOT, "scripts/predict_today.py")])
    execute_verification_step([python, os.path.join(ROOT, "scripts/predict_tomorrow.py")])
    execute_verification_step([python, os.path.join(ROOT, "scripts/analyze_performance.py")])
    execute_verification_step([python, os.path.join(ROOT, "scripts/retrain_model.py")])
    execute_verification_step([python, os.path.join(ROOT, "scripts/stats_display.py")])
    print("\n✅ verify_app 完了")
