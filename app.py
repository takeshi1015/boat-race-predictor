"""
Flask web application for the Boat Race Predictor.

Run with:
    python app.py
or via the CLI:
    python main.py --mode web
"""

from flask import Flask, render_template, request
from flask_cors import CORS

import config
from api import api_bp
from utils.logger import logger


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

    # -----------------------------------------------------------------------
    # Web dashboard routes
    # -----------------------------------------------------------------------

    @app.route("/")
    def dashboard() -> str:
        """Main dashboard page."""
        return render_template("dashboard.html")

    @app.route("/results")
    def results() -> str:
        """Detailed results page."""
        return render_template("results.html")

    @app.route("/api-docs")
    def api_docs() -> str:
        """API documentation page."""
        base_api_url = f"{request.url_root.rstrip('/')}/api"
        return render_template("api_docs.html", base_api_url=base_api_url)

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
