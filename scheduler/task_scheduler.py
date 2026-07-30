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


def _display_predictions(predictions: list, title: str) -> None:
    """予測結果をCLI形式で表示"""
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    print()
    print("━" * 50)
    print(f"ボートレース予測システム v1.0")
    print("━" * 50)
    print()
    print(f"【{title}】 {today_str}")
    print()

    if not predictions:
        print("  今から購入できるレースがありません。")
        print()
        return

    for pred in predictions:
        place = pred.get("place") or pred.get("venue", "不明")
        race_number = pred.get("race_number", "?")
        predicted_order = pred.get("predicted_order") or pred.get("prediction", [])
        confidence = float(pred.get("confidence", 0.0))
        reason = pred.get("reason", "")
        time_remaining = pred.get("time_remaining_minutes")
        hole_bets_data = pred.get("hole_bets", {})

        # 買い目を "1-2-3" 形式に
        if isinstance(predicted_order, list) and predicted_order:
            buy_pattern = "-".join(str(x) for x in predicted_order[:3])
        elif isinstance(predicted_order, dict):
            # {1: prob, 2: prob, 3: prob} 形式
            sorted_keys = sorted(predicted_order, key=lambda k: predicted_order[k], reverse=True)
            buy_pattern = "-".join(str(k) for k in sorted_keys[:3])
        else:
            buy_pattern = "不明"

        width = 44
        border_top = f"┌─ {place}競艇場 {race_number}レース " + "─" * max(1, width - len(f"─ {place}競艇場 {race_number}レース ") - 1) + "┐"
        border_bot = "└" + "─" * (width + 2) + "┘"

        print(border_top)

        # レース開始までの時間
        if time_remaining is not None:
            h = time_remaining // 60
            m = time_remaining % 60
            if h > 0:
                time_str = f"あと {h}時間 {m}分"
            else:
                time_str = f"あと {m}分"
            print(f"│ レース開始まで: {time_str:<29}│")
            print(f"│{' ' * 46}│")

        # 通常買い目
        print(f"│ 【通常買い目】{' ' * 32}│")
        print(f"│ 推奨買い目: {buy_pattern:<34}│")
        stars_str = _stars(confidence)
        label = _buy_label(confidence)
        conf_str = f"{stars_str} {confidence:.2f} ({label})"
        print(f"│ 信頼度: {conf_str:<36}│")
        if reason:
            print(f"│ 理由: {reason:<38}│")

        # 穴狙い買い目
        hole_bets = hole_bets_data.get("bets", [])
        hole_conf_list = hole_bets_data.get("confidence", [])
        if hole_bets:
            print(f"│{' ' * 46}│")
            print(f"│ 【穴狙い買い目】{' ' * 30}│")
            hole_patterns = " / ".join(
                "-".join(str(x) for x in bet) for bet in hole_bets
            )
            print(f"│ 穴狙い: {hole_patterns:<37}│")
            avg_hole_conf = sum(hole_conf_list) / len(hole_conf_list) if hole_conf_list else 0.0
            hole_stars = _stars(avg_hole_conf)
            hole_conf_str = f"{hole_stars} {avg_hole_conf:.2f} (ハイリスク・ハイリターン)"
            print(f"│ 信頼度: {hole_conf_str:<36}│")

        print(border_bot)
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
            predictions = self._get_model().predict_today()
            logger.info(f"当日予測完了: {len(predictions)}レース")

            high_confidence = [p for p in predictions if float(p.get("confidence", 0)) >= 0.7]
            if high_confidence:
                logger.info(f"信頼度0.7以上の予測: {len(high_confidence)}件")
            else:
                logger.info("信頼度0.7以上の予測はありません")

            _display_predictions(predictions, "当日予想")
        except Exception as e:
            logger.error(f"当日予測エラー: {e}", exc_info=True)
            print(f"❌ 当日予測エラー: {e}")
        logger.info("=" * 60)

    def _run_tomorrow_prediction(self):
        """翌日予測を即座に実行（main.py から呼び出し）"""
        logger.info("=" * 60)
        logger.info("翌日予測タスクを開始")
        try:
            predictions = self._get_model().predict_tomorrow()
            logger.info(f"翌日予測完了: {len(predictions)}レース")

            high_confidence = [p for p in predictions if float(p.get("confidence", 0)) >= 0.7]
            if high_confidence:
                logger.info(f"信頼度0.7以上の予測: {len(high_confidence)}件")
            else:
                logger.info("信頼度0.7以上の予測はありません")

            _display_predictions(predictions, "翌日予想")
        except Exception as e:
            logger.error(f"翌日予測エラー: {e}", exc_info=True)
            print(f"❌ 翌日予測エラー: {e}")
        logger.info("=" * 60)

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
