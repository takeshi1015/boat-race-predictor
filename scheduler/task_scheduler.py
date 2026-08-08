"""
タスクスケジューラー
APSchedulerを使用して、定期的なタスクをスケジュール・実行
"""

import logging
from datetime import datetime, timedelta

import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

# 信頼度に応じた星評価
def _stars(confidence: float) -> str:
    filled = round(confidence * 5)
    return "⭐" * filled + "☆" * (5 - filled)


# 購入可否ラベル
def _buy_label(confidence: float) -> str:
    return "購入可能" if confidence >= 0.7 else "参考情報"


def _format_pred_row(pred: dict, width: int = 44) -> None:
    """1件の予測をボックス形式で出力"""
    place = pred.get("place") or pred.get("venue", "不明")
    race_number = pred.get("race_number", "?")
    predicted_order = pred.get("predicted_order") or pred.get("prediction", [])
    confidence = float(pred.get("confidence", 0.0))
    reason = pred.get("reason", "")
    odds = pred.get("estimated_odds")

    if isinstance(predicted_order, list) and predicted_order:
        buy_pattern = "-".join(str(x) for x in predicted_order[:3])
    elif isinstance(predicted_order, dict):
        sorted_keys = sorted(predicted_order, key=lambda k: predicted_order[k], reverse=True)
        buy_pattern = "-".join(str(k) for k in sorted_keys[:3])
    else:
        buy_pattern = "不明"

    header_info = f"─ {place}競艇場 {race_number}レース "
    border_top = "┌" + header_info + "─" * max(1, width - len(header_info) - 1) + "┐"
    border_bot = "└" + "─" * (width + 2) + "┘"

    print(border_top)
    print(f"│ 推奨買い目: {buy_pattern:<34}│")
    stars_str = _stars(confidence)
    label = _buy_label(confidence)
    conf_str = f"{stars_str} {confidence:.2f} ({label})"
    print(f"│ 信頼度: {conf_str:<36}│")
    if odds is not None:
        print(f"│ 推定オッズ: {odds:.1f}倍{'':<36}│")
    if reason:
        print(f"│ 理由: {reason:<38}│")
    print(border_bot)
    print()


def _display_predictions(predictions: list, title: str, target_date: datetime = None) -> None:
    """予測結果をCLI形式で表示"""
    if target_date is None:
        target_date = datetime.now()

    date_str = target_date.strftime("%Y-%m-%d")
    print()
    print("━" * 50)
    print(f"ボートレース予測システム v1.0")
    print("━" * 50)
    print()
    print(f"【{title}】 {date_str}")
    print()

    if not predictions:
        print("  予測データがありません。")
        print("  python scripts/init_test_data.py でテストデータを追加してください。")
        print()
        return

    for pred in predictions:
        _format_pred_row(pred)


def _display_categorized_predictions(
    high_confidence: list,
    high_odds: list,
    title: str,
    target_date: datetime = None,
    hit_rate: float = None,
) -> None:
    """カテゴリー別予測をCLI形式で表示"""
    if target_date is None:
        target_date = datetime.now()

    date_str = target_date.strftime("%Y-%m-%d")
    print()
    print("━" * 50)
    print("ボートレース予測システム v1.0")
    print("━" * 50)
    print()
    print(f"【{title}】 {date_str}")
    print()

    if not high_confidence and not high_odds:
        print("  予測データがありません。")
        print("  python scripts/init_test_data.py でテストデータを追加してください。")
        print()
        return

    if high_confidence:
        print(f"🎯 確実性の高い予想 TOP {len(high_confidence)}")
        print("-" * 50)
        for pred in high_confidence:
            _format_pred_row(pred)
    else:
        print("🎯 確実性の高い予想: 該当なし（信頼度0.8以上のレースがありません）")
        print()

    if high_odds:
        print(f"💰 穴狙い予想 TOP {len(high_odds)}")
        print("-" * 50)
        for pred in high_odds:
            _format_pred_row(pred)
    else:
        print("💰 穴狙い予想: 該当なし")
        print()

    if hit_rate is not None:
        print(f"📈 今月の成績: 的中率 {hit_rate:.1%} （過去30日平均）")
        print()


class TaskScheduler:
    """定期タスク実行スケジューラー"""

    def __init__(self):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler()
        except ImportError:
            self._scheduler = None

        # EnsembleModel は遅延インポートして import エラーを防ぐ
        self._model = None

    def _get_model(self):
        if self._model is None:
            from models.ensemble_model import EnsembleModel
            self._model = EnsembleModel()
        return self._model

    # ------------------------------------------------------------------
    # Public interface used by main.py
    # ------------------------------------------------------------------

    def start(self):
        """スケジューラーを開始（連続実行モード）"""
        if self._scheduler is None:
            logger.error("APScheduler がインストールされていません")
            return

        self._schedule_tasks()
        self._scheduler.start()
        logger.info("タスクスケジューラーを開始しました")
        print("✅ スケジューラーが起動しました")

    def stop(self):
        """スケジューラーを停止"""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("スケジューラーを停止しました")

    def _run_today_prediction(self):
        """当日予測を即座に実行（main.py から呼び出し）"""
        logger.info("=" * 60)
        logger.info("当日予測タスクを開始")
        try:
            today = datetime.now()
            predictions_data = self._get_model().predict_categorized("today")
            high_conf = predictions_data.get("high_confidence", [])
            high_odds = predictions_data.get("high_odds", [])

            logger.info(f"当日予測完了: 高信頼度={len(high_conf)}件, 穴狙い={len(high_odds)}件")

            # 的中率取得
            hit_rate = self._get_hit_rate()

            _display_categorized_predictions(high_conf, high_odds, "当日予想", today, hit_rate)

            # メール送付
            self._send_prediction_email(predictions_data, "today", hit_rate)
        except Exception as e:
            logger.error(f"当日予測エラー: {e}", exc_info=True)
            print(f"❌ 当日予測エラー: {e}")
        logger.info("=" * 60)

    def _run_tomorrow_prediction(self):
        """翌日予測を即座に実行（main.py から呼び出し）"""
        logger.info("=" * 60)
        logger.info("翌日予測タスクを開始")
        try:
            tomorrow = datetime.now() + timedelta(days=1)
            predictions_data = self._get_model().predict_categorized("tomorrow")
            high_conf = predictions_data.get("high_confidence", [])
            high_odds = predictions_data.get("high_odds", [])

            logger.info(f"翌日予測完了: 高信頼度={len(high_conf)}件, 穴狙い={len(high_odds)}件")

            # 的中率取得
            hit_rate = self._get_hit_rate()

            _display_categorized_predictions(high_conf, high_odds, "翌日予想", tomorrow, hit_rate)

            # メール送付
            self._send_prediction_email(predictions_data, "tomorrow", hit_rate)
        except Exception as e:
            logger.error(f"翌日予測エラー: {e}", exc_info=True)
            print(f"❌ 翌日予測エラー: {e}")
        logger.info("=" * 60)

    def _get_hit_rate(self) -> float:
        """過去30日の的中率を取得"""
        try:
            from database.db_manager import get_db_manager
            db = get_db_manager()
            session = db.get_session()
            try:
                return db.calculate_hit_rate(session, days=30)
            finally:
                session.close()
        except Exception:
            return 0.0

    def _send_prediction_email(self, predictions_data: dict, mode: str, hit_rate: float = 0.0) -> None:
        """予測結果をメール送付"""
        try:
            from notifier.email_notifier import EmailNotifier
            notifier = EmailNotifier()
            label = "翌日" if mode == "tomorrow" else "当日"
            subject = f"【ボートレース予測】{label}の推奨予想"
            notifier.send_prediction_email(
                subject=subject,
                predictions=predictions_data,
                mode=mode,
                hit_rate=hit_rate,
            )
            logger.info(f"メール送付完了 [{mode}]")
        except Exception as e:
            logger.warning(f"メール送付スキップ: {e}")

    def _run_performance_analysis(self):
        """パフォーマンス分析を実行（main.py から呼び出し）"""
        logger.info("=" * 60)
        logger.info("パフォーマンス分析タスクを開始")
        try:
            metrics = self._get_model().evaluate_performance()
            accuracy = metrics.get("accuracy", 0.0)
            precision = metrics.get("precision", 0.0)
            recall = metrics.get("recall", 0.0)
            recovery = metrics.get("recovery_rate", 0.0)
            total = metrics.get("total_predictions", 0)

            print()
            print("━" * 50)
            print("【的中率分析】 過去30日間")
            print("━" * 50)
            print()
            print(f"  的中率:   {accuracy:.1%}")
            print(f"  回収率:   {recovery:.1%}")
            print(f"  適合率:   {precision:.1%}")
            print(f"  再現率:   {recall:.1%}")
            print(f"  総レース: {total}件")
            print()

            if accuracy < 0.4:
                print("  ⚠️  的中率が低下しています。再学習を推奨します。")
                print("  実行: python main.py --mode retrain")
                print()

        except Exception as e:
            logger.error(f"パフォーマンス分析エラー: {e}", exc_info=True)
            print(f"❌ 分析エラー: {e}")
        logger.info("=" * 60)

    def _run_model_retraining(self):
        """モデルの再学習を実行（main.py から呼び出し）"""
        logger.info("=" * 60)
        logger.info("モデル再学習タスクを開始")
        try:
            result = self._get_model().retrain()
            print()
            print("━" * 50)
            print("【学習実行】")
            print("━" * 50)
            print()
            print(f"  ✅ 学習完了")
            if isinstance(result, dict):
                for key, val in result.items():
                    print(f"  {key}: {val}")
            print()
        except Exception as e:
            logger.error(f"モデル再学習エラー: {e}", exc_info=True)
            print(f"❌ 学習エラー: {e}")
        logger.info("=" * 60)

    def _run_stats_display(self):
        """統計情報を表示（main.py から呼び出し）"""
        logger.info("統計情報表示")
        try:
            from database.db_manager import get_db_manager
            db = get_db_manager()
            session = db.get_session()
            try:
                hit_rate = db.calculate_hit_rate(session, days=30)
                recovery = db.calculate_recovery_rate(session, days=30)
                from database.models import Prediction
                total = session.query(Prediction).count()

                print()
                print("━" * 50)
                print("【統計情報】")
                print("━" * 50)
                print()
                print(f"  的中率: {hit_rate:.1%} (過去30日)")
                print(f"  回収率: {recovery:.1%}")
                print(f"  総取り組み: {total}レース")
                print()
            finally:
                session.close()
        except Exception as e:
            logger.error(f"統計情報エラー: {e}", exc_info=True)
            print(f"❌ 統計情報取得エラー: {e}")

    # ------------------------------------------------------------------
    # Scheduled tasks (continuous mode)
    # ------------------------------------------------------------------

    def _schedule_tasks(self):
        """定期タスクをスケジュール"""
        today_time = config.SCHEDULE_TODAY
        tomorrow_time = config.SCHEDULE_TOMORROW
        eval_time = config.SCHEDULE_EVALUATE

        from apscheduler.triggers.cron import CronTrigger

        today_h, today_m = self._parse_time(today_time)
        self._scheduler.add_job(
            self._run_today_prediction,
            CronTrigger(hour=today_h, minute=today_m),
            id="predict_today",
            name="当日予測タスク",
            replace_existing=True,
        )

        tomorrow_h, tomorrow_m = self._parse_time(tomorrow_time)
        self._scheduler.add_job(
            self._run_tomorrow_prediction,
            CronTrigger(hour=tomorrow_h, minute=tomorrow_m),
            id="predict_tomorrow",
            name="翌日予測タスク",
            replace_existing=True,
        )

        eval_h, eval_m = self._parse_time(eval_time)
        self._scheduler.add_job(
            self._run_performance_analysis,
            CronTrigger(hour=eval_h, minute=eval_m),
            id="evaluate_performance",
            name="パフォーマンス評価タスク",
            replace_existing=True,
        )

    @staticmethod
    def _parse_time(time_str: str):
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])


def run_scheduler():
    """スケジューラーを実行"""
    scheduler = TaskScheduler()
    try:
        scheduler.start()
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("ユーザーによる中断")
        scheduler.stop()
    except Exception as e:
        logger.error(f"スケジューラー実行エラー: {e}", exc_info=True)
        scheduler.stop()


if __name__ == "__main__":
    run_scheduler()
