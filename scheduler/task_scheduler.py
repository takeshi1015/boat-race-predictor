"""
タスクスケジューラー
APSchedulerを使用して、定期的なタスクをスケジュール・実行
"""

import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config
from models.ensemble_model import EnsembleModel
from notifiers.email_notifier import EmailNotifier
from utils.logger import setup_logger

logger = setup_logger(__name__)


class TaskScheduler:
    """定期タスク実行スケジューラー"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.config = Config()
        self.model = EnsembleModel()
        self.email_notifier = EmailNotifier() if self.config.USE_EMAIL else None
        
    def start(self):
        """スケジューラーを開始"""
        try:
            self._schedule_tasks()
            self.scheduler.start()
            logger.info("タスクスケジューラーを開始しました")
            print("✅ スケジューラーが起動しました")
        except Exception as e:
            logger.error(f"スケジューラー起動エラー: {e}")
            raise
    
    def _schedule_tasks(self):
        """定期タスクをスケジュール"""
        
        # 当日予測タスク
        today_hour, today_minute = self._parse_time(self.config.SCHEDULE_TODAY)
        self.scheduler.add_job(
            self.predict_today,
            CronTrigger(hour=today_hour, minute=today_minute),
            id='predict_today',
            name='当日予測タスク',
            replace_existing=True
        )
        logger.info(f"当日予測: {today_hour:02d}:{today_minute:02d}にスケジュール")
        
        # 翌日予測タスク
        tomorrow_hour, tomorrow_minute = self._parse_time(self.config.SCHEDULE_TOMORROW)
        self.scheduler.add_job(
            self.predict_tomorrow,
            CronTrigger(hour=tomorrow_hour, minute=tomorrow_minute),
            id='predict_tomorrow',
            name='翌日予測タスク',
            replace_existing=True
        )
        logger.info(f"翌日予測: {tomorrow_hour:02d}:{tomorrow_minute:02d}にスケジュール")
        
        # 評価タスク
        eval_hour, eval_minute = self._parse_time(self.config.SCHEDULE_EVALUATE)
        self.scheduler.add_job(
            self.evaluate_performance,
            CronTrigger(hour=eval_hour, minute=eval_minute),
            id='evaluate_performance',
            name='パフォーマンス評価タスク',
            replace_existing=True
        )
        logger.info(f"パフォーマンス評価: {eval_hour:02d}:{eval_minute:02d}にスケジュール")
    
    @staticmethod
    def _parse_time(time_str):
        """時刻文字列を時間と分に変換"""
        parts = time_str.split(':')
        return int(parts[0]), int(parts[1])
    
    def predict_today(self):
        """当日予測を実行"""
        logger.info("=" * 60)
        logger.info("当日予測タスクを開始")
        try:
            predictions = self.model.predict_today()
            logger.info(f"当日予測完了: {len(predictions)}レース")
            
            # 高い信頼度の予測をフィルタリング
            high_confidence = [p for p in predictions if p['confidence'] >= 0.7]
            if high_confidence:
                logger.info(f"高信頼度予測: {len(high_confidence)}件")
                self._notify_predictions(high_confidence, "当日予測")
            
        except Exception as e:
            logger.error(f"当日予測エラー: {e}", exc_info=True)
        logger.info("=" * 60)
    
    def predict_tomorrow(self):
        """翌日予測を実行"""
        logger.info("=" * 60)
        logger.info("翌日予測タスクを開始")
        try:
            predictions = self.model.predict_tomorrow()
            logger.info(f"翌日予測完了: {len(predictions)}レース")
            
            # 高い信頼度の予測をフィルタリング
            high_confidence = [p for p in predictions if p['confidence'] >= 0.7]
            if high_confidence:
                logger.info(f"高信頼度予測: {len(high_confidence)}件")
                self._notify_predictions(high_confidence, "翌日予測")
            
        except Exception as e:
            logger.error(f"翌日予測エラー: {e}", exc_info=True)
        logger.info("=" * 60)
    
    def evaluate_performance(self):
        """パフォーマンスを評価"""
        logger.info("=" * 60)
        logger.info("パフォーマンス評価タスクを開始")
        try:
            metrics = self.model.evaluate_performance()
            logger.info(f"精度: {metrics['accuracy']:.2%}")
            logger.info(f"適合率: {metrics['precision']:.2%}")
            logger.info(f"再現率: {metrics['recall']:.2%}")
            
            # 精度が低い場合にアラートを送信
            if metrics['accuracy'] < 0.55:
                logger.warning("⚠️ 精度が低下しています")
                self._send_alert(f"精度低下アラート: {metrics['accuracy']:.2%}")
            
        except Exception as e:
            logger.error(f"パフォーマンス評価エラー: {e}", exc_info=True)
        logger.info("=" * 60)
    
    def _notify_predictions(self, predictions, title):
        """予測結果を通知"""
        try:
            if self.email_notifier:
                self.email_notifier.send_predictions(predictions, title)
            logger.info("✅ 通知を送信しました")
        except Exception as e:
            logger.error(f"通知送信エラー: {e}")
    
    def _send_alert(self, message):
        """アラートメッセージを送信"""
        try:
            if self.email_notifier:
                self.email_notifier.send_alert(message)
        except Exception as e:
            logger.error(f"アラート送信エラー: {e}")
    
    def shutdown(self):
        """スケジューラーをシャットダウン"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("スケジューラーを停止しました")


def run_scheduler():
    """スケジューラーを実行"""
    scheduler = TaskScheduler()
    try:
        scheduler.start()
        # スケジューラーは独立したスレッドで動作
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("ユーザーによる中断")
        scheduler.shutdown()
    except Exception as e:
        logger.error(f"スケジューラー実行エラー: {e}", exc_info=True)
        scheduler.shutdown()


if __name__ == "__main__":
    run_scheduler()
