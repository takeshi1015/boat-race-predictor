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

_APP_DATA_INITIALIZED = False
_DATA_REFRESH_SCHEDULER = None


def initialize_application_data(force_refresh: bool = False) -> None:
    """Initialize DB schema and bootstrap race data."""
    global _APP_DATA_INITIALIZED

    if _APP_DATA_INITIALIZED and not force_refresh:
        return

    try:
        from database.db_manager import init_db
        from scripts.fetch_real_races import fetch_and_store_races

        init_db()
        summary = fetch_and_store_races()
        logger.info("Race data bootstrap completed: %s", summary)
        _APP_DATA_INITIALIZED = True
    except Exception as exc:
        logger.error("Application bootstrap failed: %s", exc, exc_info=True)


def start_data_refresh_scheduler() -> None:
    """Start an hourly background refresh for race data."""
    global _DATA_REFRESH_SCHEDULER

    if _DATA_REFRESH_SCHEDULER is not None or os.getenv("PYTEST_CURRENT_TEST"):
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            initialize_application_data,
            "interval",
            hours=1,
            kwargs={"force_refresh": True},
            id="refresh-race-data",
            replace_existing=True,
        )
        scheduler.start()
        _DATA_REFRESH_SCHEDULER = scheduler
        logger.info("Started hourly race data refresh scheduler")
    except Exception as exc:
        logger.error("Failed to start race data scheduler: %s", exc, exc_info=True)


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

    initialize_application_data()

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
    start_data_refresh_scheduler()
    logger.info("Starting Flask server on %s:%d", config.WEB_HOST, config.WEB_PORT)
    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=config.WEB_DEBUG,
    )
