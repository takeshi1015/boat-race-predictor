"""
API package for Boat Race Predictor REST endpoints.
"""

from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from api import routes  # noqa: E402, F401
