"""
Flask web application for the Boat Race Predictor.

Run with:
    python app.py
or via the CLI:
    python main.py --mode web
"""

import os
from flask import Flask, render_template
from flask_cors import CORS

import config
from api import api_bp
from utils.logger import logger

_race_sync_scheduler = None
_race_sync_started = False


def _is_test_runtime() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _start_race_data_sync() -> None:
    global _race_sync_scheduler, _race_sync_started
    if _race_sync_started:
        return

    try:
        from scripts.fetch_real_races import refresh_race_data

        saved, archived = refresh_race_data()
        logger.info("起動時レースデータ更新: 保存=%d 履歴化=%d", saved, archived)
    except Exception as exc:
        logger.error("起動時レースデータ更新に失敗: %s", exc, exc_info=True)

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        _race_sync_scheduler = BackgroundScheduler()
        _race_sync_scheduler.add_job(
            _sync_race_data_job,
            trigger="interval",
            hours=1,
            id="sync_race_data_hourly",
            replace_existing=True,
        )
        _race_sync_scheduler.start()
        _race_sync_started = True
        logger.info("レースデータ1時間更新スケジューラを開始")
    except Exception as exc:
        logger.warning("1時間更新スケジューラ開始失敗: %s", exc)


def _sync_race_data_job() -> None:
    try:
        from scripts.fetch_real_races import refresh_race_data

        saved, archived = refresh_race_data()
        logger.info("定期レースデータ更新: 保存=%d 履歴化=%d", saved, archived)
    except Exception as exc:
        logger.error("定期レースデータ更新エラー: %s", exc, exc_info=True)


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

    if not _is_test_runtime():
        _start_race_data_sync()

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
