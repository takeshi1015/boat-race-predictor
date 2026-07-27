"""Task scheduler and CLI task runner."""

from datetime import datetime, timedelta
from typing import Dict, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from models.ensemble_model import EnsembleModel
from utils.logger import setup_logger
from utils.statistics import confidence_stars, purchase_label

logger = setup_logger(__name__)


class TaskScheduler:
    """Schedule and run prediction tasks."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.model = EnsembleModel()

    def start(self):
        self._schedule_tasks()
        self.scheduler.start()
        logger.info("タスクスケジューラーを開始しました")
        print("✅ スケジューラーが起動しました")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def _schedule_tasks(self):
        today_hour, today_minute = self._parse_time(config.SCHEDULE_TODAY)
        tomorrow_hour, tomorrow_minute = self._parse_time(config.SCHEDULE_TOMORROW)
        eval_hour, eval_minute = self._parse_time(config.SCHEDULE_EVALUATE)
        retrain_hour, retrain_minute = self._parse_time(config.SCHEDULE_RETRAIN)

        self.scheduler.add_job(self._run_today_prediction, CronTrigger(hour=today_hour, minute=today_minute), id="predict_today", replace_existing=True)
        self.scheduler.add_job(self._run_tomorrow_prediction, CronTrigger(hour=tomorrow_hour, minute=tomorrow_minute), id="predict_tomorrow", replace_existing=True)
        self.scheduler.add_job(self._run_performance_analysis, CronTrigger(hour=eval_hour, minute=eval_minute), id="evaluate_performance", replace_existing=True)
        if config.AUTO_LEARNING_ENABLED:
            self.scheduler.add_job(self._run_auto_learning_cycle, CronTrigger(hour=retrain_hour, minute=retrain_minute), id="auto_learn", replace_existing=True)

    @staticmethod
    def _parse_time(time_str):
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])

    def _run_today_prediction(self) -> List[Dict]:
        logger.info("=" * 60)
        logger.info("当日予測タスクを開始")
        predictions = self.model.predict_today()
        self.model.save_prediction_records(predictions, "today")
        self._print_predictions("当日予想", datetime.now().strftime("%Y-%m-%d"), predictions)
        logger.info("当日予測完了: %dレース", len(predictions))
        logger.info("=" * 60)
        return predictions

    def _run_tomorrow_prediction(self) -> List[Dict]:
        logger.info("=" * 60)
        logger.info("翌日予測タスクを開始")
        predictions = self.model.predict_tomorrow()
        self.model.save_prediction_records(predictions, "tomorrow")
        tomorrow = datetime.now().date() + timedelta(days=1)
        self._print_predictions("翌日予想", tomorrow.isoformat(), predictions)
        logger.info("翌日予測完了: %dレース", len(predictions))
        logger.info("=" * 60)
        return predictions

    def _run_performance_analysis(self):
        result = self.model.evaluate_performance(days=30)
        print("\n【的中率分析】")
        print(f"対象件数: {result['total_predictions']}件")
        print(f"的中率: {result['hit_rate']:.2%}")
        print("不適中原因:")
        if not result["miss_causes"]:
            print("  - データ不足のため分析結果なし")
        else:
            for cause, count in sorted(result["miss_causes"].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {cause}: {count}件")
        return result

    def _run_model_retraining(self):
        result = self.model.retrain(days=30)
        print("\n【再学習】")
        print(f"学習対象レース: {result['learned_races']}件")
        print(f"更新予測件数: {result['updated_predictions']}件")
        print(f"モデル重み: {result['weights']}")
        return result

    def _run_auto_learning_cycle(self):
        logger.info("=" * 60)
        logger.info("自動学習ループを開始")
        result = self.model.auto_learning_cycle(days=30)
        before = result.get("before", {})
        after = result.get("after", {})
        retrain = result.get("retrain", {})
        print("\n【自動学習ループ】")
        print(f"学習対象期間: 直近{result.get('days', 30)}日")
        print(f"改善前 的中率: {before.get('hit_rate', 0.0):.2%}")
        print(f"改善後 的中率: {after.get('hit_rate', 0.0):.2%}")
        print(f"学習対象レース: {retrain.get('learned_races', 0)}件")
        print(f"重み: {retrain.get('weights', {})}")
        for action in result.get("actions", []):
            print(f"- 対策: {action}")
        logger.info("自動学習ループ完了")
        logger.info("=" * 60)
        return result

    def _run_stats_display(self):
        result = self.model.evaluate_performance(days=30)
        print("\n【統計情報】")
        print(f"予測数: {result['total_predictions']}")
        print(f"的中率: {result['hit_rate']:.2%}")
        return result

    def _print_predictions(self, title: str, target_date: str, predictions: List[Dict]):
        print(f"\n【{title}】")
        print(f"日付: {target_date}\n")
        if not predictions:
            print("予測対象レースがありません。")
            return
        purchasable = [p for p in predictions if p["purchasable"]]
        print(f"購入可能予想(信頼度{config.CONFIDENCE_THRESHOLD:.1f}以上): {len(purchasable)}件\n")
        for pred in predictions:
            label = purchase_label(pred["confidence"], config.CONFIDENCE_THRESHOLD)
            stars = confidence_stars(pred["confidence"])
            print(f"{pred['place']}競艇場 {pred['race_number']}レース")
            print(f"推奨買い目: {pred['recommended_bet']}")
            print(f"信頼度: {pred['confidence']:.2f} {stars} ({label})")
            print(f"理由: {pred['reason']}\n")


def run_scheduler():
    scheduler = TaskScheduler()
    scheduler.start()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
