"""再学習スクリプト."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scheduler.task_scheduler import TaskScheduler


if __name__ == "__main__":
    TaskScheduler()._run_model_retraining()
