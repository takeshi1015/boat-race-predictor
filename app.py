"""
Flask web application for the Boat Race Predictor.

Run with:
    python app.py
or via the CLI:
    python main.py --mode web
"""

from flask import Flask, render_template
from flask_cors import CORS

import config
from api import api_bp
from utils.logger import logger

# フラグ：起動時処理が既に完了しているか
_startup_done = False


def _init_database() -> None:
    """データベーススキーマを自動作成する"""
    try:
        from database.db_manager import get_db_manager
        get_db_manager()
        logger.info("✅ データベーススキーマを初期化しました")
    except Exception as exc:
        logger.error("データベース初期化エラー: %s", exc)


def _fetch_real_races() -> None:
    """boatrace.jp から本日のレースデータを自動取得してDBに保存する"""
    try:
        from scripts.fetch_real_races import BoatraceDataFetcher, save_races_to_db
        from datetime import datetime

        fetcher = BoatraceDataFetcher()
        today = datetime.now()
        races = fetcher.fetch_races_for_date(today)
        saved = save_races_to_db(races)
        logger.info("✅ 本日のレースデータを取得・保存しました: %d件", saved)
    except Exception as exc:
        logger.error("レースデータ取得エラー: %s", exc)


def _start_hourly_updater() -> None:
    """バックグラウンドで1時間ごとにレースデータを自動更新する"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            _fetch_real_races,
            IntervalTrigger(hours=1),
            id="hourly_race_fetch",
            name="1時間ごとレース取得",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("✅ 1時間ごとの自動更新スケジューラーを開始しました")
    except ImportError:
        logger.warning("APScheduler が利用できないため自動更新は無効です")
    except Exception as exc:
        logger.error("自動更新スケジューラー開始エラー: %s", exc)


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "boat-race-predictor-secret"

    # Enable CORS for the API blueprint
    CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}})

    # Register the REST API blueprint
    app.register_blueprint(api_bp)

    # データベースの自動初期化・レース取得は初回起動時のみ実行
    global _startup_done
    if not _startup_done:
        _startup_done = True
        _init_database()
        _fetch_real_races()
        _start_hourly_updater()

    # -----------------------------------------------------------------------
    # Web dashboard routes
    # -----------------------------------------------------------------------

    @app.route("/")
    def dashboard() -> str:
        """Main dashboard page."""
        return render_template("dashboard.html")

    @app.route("/predictions/today")
    def predictions_today() -> str:
        """Today's predictions page."""
        return render_template("predictions_today.html")

    @app.route("/predictions/tomorrow")
    def predictions_tomorrow() -> str:
        """Tomorrow's predictions page."""
        return render_template("predictions_tomorrow.html")

    @app.route("/analysis")
    def analysis() -> str:
        """Analysis page."""
        return render_template("analysis.html")

    @app.route("/results")
    def results() -> str:
        """Detailed results page."""
        return render_template("results.html")

    @app.route("/settings")
    def settings() -> str:
        """Settings page."""
        return render_template("settings.html")

    @app.route("/api-docs")
    def api_docs() -> str:
        """API documentation page."""
        return render_template("api_docs.html")

    # -----------------------------------------------------------------------
    # Error handlers
    # -----------------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return render_template("base.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        """Handle 500 errors."""
        logger.error("Internal server error: %s", error)
        return render_template("base.html"), 500

    return app


if __name__ == "__main__":
    app = create_app()
    logger.info("Starting Flask server on %s:%d", config.WEB_HOST, config.WEB_PORT)
    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=config.WEB_DEBUG,
    )
