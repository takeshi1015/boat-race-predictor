"""
Database package initialization
"""

from database.db_manager import DatabaseManager, get_db_manager, init_db
from database.models import (
    Base, Player, Boat, Race, Prediction,
    ModelPerformance, LearningFeedback, Notification
)

__all__ = [
    "DatabaseManager",
    "get_db_manager",
    "init_db",
    "Base",
    "Player",
    "Boat",
    "Race",
    "Prediction",
    "ModelPerformance",
    "LearningFeedback",
    "Notification",
]
