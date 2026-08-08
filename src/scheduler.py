"""
src/scheduler.py – APScheduler を使用して毎日朝 5:00 に自動実行するスケジューラー。

実行内容:
  1. 当日のレースデータを boatrace.jp から取得してDBに保存
  2. 全レースの予想を生成してDBに保存
  3. 処理結果をログに記録

使用例::

    from src.scheduler import RaceScheduler
    scheduler = RaceScheduler()
    scheduler.start()       # バックグラウンドで定期実行開始
    ...
    scheduler.stop()        # 停止
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

import config
from utils.logger import logger


class RaceScheduler:
    """APScheduler を用いたレース予想自動実行スケジューラー。

    毎日朝 5:00 に :meth:`run_daily_task` を実行する。
    ``DAILY_SCHEDULE_TIME = "05:00"`` で定義されており、変更する場合は
    このクラス定数を直接変更してください。
    """

    DAILY_SCHEDULE_TIME = "05:00"  # 要件: 毎日朝5時

    def __init__(self) -> None:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            self._scheduler = BackgroundScheduler()
        except ImportError:
            logger.warning("APScheduler がインストールされていません")
            self._scheduler = None

        self._running = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """スケジューラーをバックグラウンドで起動する。"""
        if self._scheduler is None:
            logger.error("APScheduler が利用できないためスケジューラーを起動できません")
            return

        self._register_jobs()
        self._scheduler.start()
        self._running = True
        logger.info(
            "スケジューラー起動: 毎日 %s にレースデータ取得・予想生成を実行します",
            self.DAILY_SCHEDULE_TIME,
        )

    def stop(self) -> None:
        """スケジューラーを停止する。"""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("スケジューラー停止")

    def run_daily_task(self) -> Dict[str, Any]:
        """毎日の定期処理を手動または自動で実行する。

        処理順序:
          1. 当日のレースデータを取得・DB保存
          2. 訓練済みモデルで全レースの予想を生成
          3. 予想を DB に保存

        Returns:
            実行結果のサマリー辞書。
        """
        logger.info("=" * 60)
        logger.info("定期タスク開始: %s", datetime.now().isoformat())
        result: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "races_fetched": 0,
            "predictions_saved": 0,
            "errors": [],
        }

        # Step 1: レースデータ取得
        races = self._fetch_today_races(result)

        # Step 2 & 3: 予想生成・保存
        if races:
            self._generate_and_save_predictions(races, result)

        logger.info(
            "定期タスク完了: レース取得=%d, 予想保存=%d",
            result["races_fetched"],
            result["predictions_saved"],
        )
        logger.info("=" * 60)
        return result

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _register_jobs(self) -> None:
        """APScheduler にジョブを登録する。"""
        from apscheduler.triggers.cron import CronTrigger

        hour, minute = self._parse_time(self.DAILY_SCHEDULE_TIME)
        self._scheduler.add_job(
            self.run_daily_task,
            CronTrigger(hour=hour, minute=minute),
            id="daily_race_fetch",
            name="当日レースデータ取得・予想生成",
            replace_existing=True,
            misfire_grace_time=3600,  # 1時間以内なら遅延実行
        )
        logger.info(
            "ジョブ登録完了: 毎日 %02d:%02d に実行", hour, minute
        )

    def _fetch_today_races(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """当日のレースデータを取得してDBに保存する。"""
        try:
            from src.scraper import RaceDataScraper

            scraper = RaceDataScraper()
            races = scraper.fetch_and_save_today()
            result["races_fetched"] = len(races)
            logger.info("レースデータ取得完了: %d件", len(races))
            return races
        except Exception as exc:
            msg = f"レースデータ取得エラー: {exc}"
            logger.error(msg, exc_info=True)
            result["errors"].append(msg)
            return []

    def _generate_and_save_predictions(
        self, races: List[Dict[str, Any]], result: Dict[str, Any]
    ) -> None:
        """全レースの予想を生成してDBに保存する。"""
        try:
            from models.ensemble_model import EnsembleModel

            model = EnsembleModel()
            predictions = model.predict_today()
            saved = self._save_predictions(predictions)
            result["predictions_saved"] = saved
            logger.info("予想生成・保存完了: %d件", saved)
        except Exception as exc:
            msg = f"予想生成エラー: {exc}"
            logger.error(msg, exc_info=True)
            result["errors"].append(msg)

    @staticmethod
    def _save_predictions(predictions: List[Dict[str, Any]]) -> int:
        """予想リストをデータベースに保存する。

        Args:
            predictions: :class:`~models.ensemble_model.EnsembleModel` の
                ``predict_today()`` が返す予想辞書のリスト。

        Returns:
            保存した件数。
        """
        if not predictions:
            return 0

        saved = 0
        try:
            from database.db_manager import get_db_manager

            db = get_db_manager()
            session = db.get_session()
            try:
                for pred in predictions:
                    try:
                        db.add_prediction(
                            session,
                            {
                                "race_id": pred.get("race_id", "unknown"),
                                "prediction_date": datetime.now(),
                                "prediction_type": (
                                    "high_confidence"
                                    if pred.get("confidence", 0) >= 0.8
                                    else "high_odds"
                                ),
                                "predicted_order": pred.get("predicted_order", []),
                                "confidence": pred.get("confidence", 0.0),
                                "estimated_odds": 0.0,
                                "model_version": "ensemble_v1",
                                "methods_used": ["statistical", "rule_based"],
                            },
                        )
                        saved += 1
                    except Exception as exc:
                        logger.warning("予想保存スキップ: %s", exc)
            finally:
                session.close()
        except Exception as exc:
            logger.error("予想保存エラー: %s", exc)

        return saved

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_time(time_str: str):
        """``"HH:MM"`` 形式の文字列を (hour, minute) タプルに変換する。"""
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])
