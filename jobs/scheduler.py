"""
定時更新スケジューラー

APScheduler を使って以下のジョブを定期実行する:
  - 毎朝 06:00  → 当日開催情報を取得し DB に保存
  - 毎 30 分    → 各レース情報を更新
  - 毎夜 22:00  → 学習データを分析して重みを調整
  - レース終了後 → 結果・配当を取得して予測と照合
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual job functions
# ---------------------------------------------------------------------------

def job_fetch_today_races() -> None:
    """毎朝 06:00 – 当日開催情報をスクレイピングして DB に保存する。"""
    logger.info("[scheduler] 当日レースデータ取得ジョブ開始")
    try:
        from scripts.fetch_real_races import BoatraceDataFetcher, save_races_to_db

        fetcher = BoatraceDataFetcher()
        races = fetcher.fetch_races_for_date(datetime.now())
        saved = save_races_to_db(races)
        logger.info(f"[scheduler] 当日レース保存完了: {saved}件")
    except Exception as exc:
        logger.error(f"[scheduler] 当日レース取得エラー: {exc}", exc_info=True)


def job_fetch_tomorrow_races() -> None:
    """翌日分のレース情報を取得して DB に保存する。"""
    logger.info("[scheduler] 翌日レースデータ取得ジョブ開始")
    try:
        from scripts.fetch_real_races import BoatraceDataFetcher, save_races_to_db

        fetcher = BoatraceDataFetcher()
        tomorrow = datetime.now() + timedelta(days=1)
        races = fetcher.fetch_races_for_date(tomorrow)
        saved = save_races_to_db(races)
        logger.info(f"[scheduler] 翌日レース保存完了: {saved}件")
    except Exception as exc:
        logger.error(f"[scheduler] 翌日レース取得エラー: {exc}", exc_info=True)


def job_update_race_info() -> None:
    """毎 30 分 – 終了前レースの天気・水面状況を更新する。"""
    logger.info("[scheduler] レース情報更新ジョブ開始")
    try:
        from database.db_manager import get_db_manager
        from scrapers.boat_race_scraper import fetch_race_details

        db = get_db_manager()
        session = db.get_session()
        try:
            now = datetime.now()
            cutoff = now + timedelta(hours=2)
            races = db.get_races_by_date(session, now)
            updated = 0
            for race in races:
                race_dt = getattr(race, "date", None)
                if race_dt is None or race_dt < now or race_dt > cutoff:
                    continue
                venue_code = getattr(race, "venue_code", None)
                if not venue_code:
                    continue
                details = fetch_race_details(
                    venue_code,
                    race.race_number,
                    now.strftime("%Y%m%d"),
                )
                race_info = details.get("race_info", {})
                for key, value in race_info.items():
                    if hasattr(race, key) and value:
                        setattr(race, key, value)
                updated += 1
            session.commit()
            logger.info(f"[scheduler] レース情報更新完了: {updated}件")
        finally:
            session.close()
    except Exception as exc:
        logger.error(f"[scheduler] レース情報更新エラー: {exc}", exc_info=True)


def job_fetch_race_results() -> None:
    """毎 30 分 – 終了したレースの実結果・配当を取得して DB に保存する。"""
    logger.info("[scheduler] レース結果取得ジョブ開始")
    try:
        from database.db_manager import get_db_manager
        from scrapers.boat_race_scraper import fetch_race_result

        db = get_db_manager()
        session = db.get_session()
        try:
            now = datetime.now()
            finished_cutoff = now - timedelta(minutes=30)
            races = db.get_races_by_date(session, now)
            saved = 0
            for race in races:
                race_dt = getattr(race, "date", None)
                if race_dt is None or race_dt > finished_cutoff:
                    continue
                existing = db.get_race_result(session, race.race_id)
                if existing:
                    continue
                result_data = fetch_race_result(race.race_id)
                if result_data and result_data.get("first_place"):
                    db.save_race_result(session, result_data)
                    saved += 1
            logger.info(f"[scheduler] レース結果保存完了: {saved}件")
        finally:
            session.close()
    except Exception as exc:
        logger.error(f"[scheduler] レース結果取得エラー: {exc}", exc_info=True)


def job_nightly_learning() -> None:
    """毎夜 22:00 – 予測精度を分析してモデル重みを調整する。"""
    logger.info("[scheduler] 夜間学習ジョブ開始")
    try:
        from jobs.learning import verify_predictions, calculate_accuracy_by_confidence

        verify_predictions()
        stats = calculate_accuracy_by_confidence()
        logger.info(f"[scheduler] 夜間学習完了: {stats}")
    except Exception as exc:
        logger.error(f"[scheduler] 夜間学習エラー: {exc}", exc_info=True)


# ---------------------------------------------------------------------------
# Scheduler class
# ---------------------------------------------------------------------------

class RaceScheduler:
    """ボートレース予測システムの定時タスクスケジューラー。"""

    def __init__(self):
        self._scheduler = BackgroundScheduler(timezone="Asia/Tokyo")
        self._running = False

    def start(self) -> None:
        """スケジューラーを起動して全ジョブを登録する。"""
        if self._running:
            logger.warning("[scheduler] 既に起動済みです")
            return

        # 毎朝 06:00 – 当日レースデータ取得
        self._scheduler.add_job(
            job_fetch_today_races,
            CronTrigger(hour=6, minute=0),
            id="fetch_today_races",
            name="当日レースデータ取得",
            replace_existing=True,
        )

        # 毎夕 18:00 – 翌日レースデータ取得
        self._scheduler.add_job(
            job_fetch_tomorrow_races,
            CronTrigger(hour=18, minute=0),
            id="fetch_tomorrow_races",
            name="翌日レースデータ取得",
            replace_existing=True,
        )

        # 毎 30 分 – レース情報更新
        self._scheduler.add_job(
            job_update_race_info,
            IntervalTrigger(minutes=30),
            id="update_race_info",
            name="レース情報更新",
            replace_existing=True,
        )

        # 毎 30 分 – レース結果取得（更新の 15 分後にずらす）
        self._scheduler.add_job(
            job_fetch_race_results,
            IntervalTrigger(minutes=30, start_date=datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=15)),
            id="fetch_race_results",
            name="レース結果取得",
            replace_existing=True,
        )

        # 毎夜 22:00 – 夜間学習
        self._scheduler.add_job(
            job_nightly_learning,
            CronTrigger(hour=22, minute=0),
            id="nightly_learning",
            name="夜間学習",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True
        logger.info("[scheduler] スケジューラー起動完了（全5ジョブ登録）")

    def stop(self) -> None:
        """スケジューラーを停止する。"""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("[scheduler] スケジューラー停止")

    def run_job_now(self, job_id: str) -> None:
        """指定したジョブを即時実行する（デバッグ用）。"""
        job = self._scheduler.get_job(job_id)
        if job:
            job.func()
        else:
            logger.warning(f"[scheduler] ジョブ '{job_id}' が見つかりません")

    @property
    def is_running(self) -> bool:
        return self._running


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_scheduler: RaceScheduler = None


def get_scheduler() -> RaceScheduler:
    """グローバルスケジューラーインスタンスを取得する。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = RaceScheduler()
    return _scheduler


if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO)
    scheduler = get_scheduler()
    scheduler.start()
    print("スケジューラー起動。Ctrl+C で停止")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.stop()
