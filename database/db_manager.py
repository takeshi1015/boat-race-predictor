"""
Database manager for Boat Race Predictor
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import config
from utils.logger import logger
from database.models import (
    Base, Player, Boat, Race, Prediction,
    ModelPerformance, LearningFeedback, Notification
)


class DatabaseManager:
    """Database management class"""
    
    def __init__(self, database_url: str = config.DATABASE_URL):
        """
        Initialize database manager
        
        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        
        # Create engine
        if database_url.startswith("sqlite"):
            # SQLite configuration
            self.engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            # Other databases
            self.engine = create_engine(database_url, pool_pre_ping=True)
        
        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    # ============================================================================
    # Player Operations
    # ============================================================================
    
    def add_or_update_player(self, session: Session, player_data: Dict[str, Any]) -> Player:
        """Add or update player"""
        player = session.query(Player).filter_by(player_id=player_data["player_id"]).first()
        
        if player:
            # Update existing player
            for key, value in player_data.items():
                if hasattr(player, key):
                    setattr(player, key, value)
            player.updated_at = datetime.now()
        else:
            # Create new player
            player = Player(**player_data)
        
        session.add(player)
        session.commit()
        return player
    
    def get_player(self, session: Session, player_id: str) -> Optional[Player]:
        """Get player by ID"""
        return session.query(Player).filter_by(player_id=player_id).first()
    
    # ============================================================================
    # Boat Operations
    # ============================================================================
    
    def add_or_update_boat(self, session: Session, boat_data: Dict[str, Any]) -> Boat:
        """Add or update boat"""
        boat = session.query(Boat).filter_by(boat_id=boat_data["boat_id"]).first()
        
        if boat:
            for key, value in boat_data.items():
                if hasattr(boat, key):
                    setattr(boat, key, value)
            boat.updated_at = datetime.now()
        else:
            boat = Boat(**boat_data)
        
        session.add(boat)
        session.commit()
        return boat
    
    def get_boat(self, session: Session, boat_id: str) -> Optional[Boat]:
        """Get boat by ID"""
        return session.query(Boat).filter_by(boat_id=boat_id).first()
    
    # ============================================================================
    # Race Operations
    # ============================================================================
    
    def add_or_update_race(self, session: Session, race_data: Dict[str, Any]) -> Race:
        """Add or update race"""
        race = session.query(Race).filter_by(race_id=race_data["race_id"]).first()
        
        if race:
            for key, value in race_data.items():
                if hasattr(race, key):
                    setattr(race, key, value)
            race.updated_at = datetime.now()
        else:
            race = Race(**race_data)
        
        session.add(race)
        session.commit()
        return race
    
    def get_race(self, session: Session, race_id: str) -> Optional[Race]:
        """Get race by ID"""
        return session.query(Race).filter_by(race_id=race_id).first()
    
    def get_races_by_date(self, session: Session, date: datetime) -> List[Race]:
        """Get races for specific date"""
        start = datetime.combine(date.date(), datetime.min.time())
        end = datetime.combine(date.date(), datetime.max.time())
        return session.query(Race).filter(Race.date.between(start, end)).all()
    
    # ============================================================================
    # Prediction Operations
    # ============================================================================
    
    def add_prediction(self, session: Session, prediction_data: Dict[str, Any]) -> Prediction:
        """Add prediction"""
        prediction = Prediction(**prediction_data)
        session.add(prediction)
        session.commit()
        return prediction
    
    def get_predictions_by_race(self, session: Session, race_id: str) -> List[Prediction]:
        """Get predictions for race"""
        return session.query(Prediction).filter_by(race_id=race_id).all()
    
    def get_recent_predictions(self, session: Session, days: int = 7) -> List[Prediction]:
        """Get recent predictions"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return session.query(Prediction).filter(
            Prediction.prediction_date >= cutoff_date
        ).all()
    
    def update_prediction_result(
        self,
        session: Session,
        prediction_id: int,
        result: Dict[str, Any]
    ) -> Optional[Prediction]:
        """Update prediction with result"""
        prediction = session.query(Prediction).filter_by(id=prediction_id).first()
        if prediction:
            prediction.result = result
            prediction.updated_at = datetime.now()
            session.commit()
        return prediction
    
    # ============================================================================
    # Performance Operations
    # ============================================================================
    
    def add_model_performance(self, session: Session, performance_data: Dict[str, Any]) -> ModelPerformance:
        """Add model performance record"""
        performance = ModelPerformance(**performance_data)
        session.add(performance)
        session.commit()
        return performance
    
    def get_model_performance(self, session: Session, model_name: str, days: int = 7) -> Optional[ModelPerformance]:
        """Get latest model performance"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return session.query(ModelPerformance).filter(
            ModelPerformance.model_name == model_name,
            ModelPerformance.created_at >= cutoff_date
        ).order_by(ModelPerformance.created_at.desc()).first()
    
    # ============================================================================
    # Learning Feedback Operations
    # ============================================================================
    
    def add_learning_feedback(self, session: Session, feedback_data: Dict[str, Any]) -> LearningFeedback:
        """Add learning feedback"""
        feedback = LearningFeedback(**feedback_data)
        session.add(feedback)
        session.commit()
        return feedback
    
    def get_recent_feedback(self, session: Session, days: int = 7) -> List[LearningFeedback]:
        """Get recent learning feedback"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return session.query(LearningFeedback).filter(
            LearningFeedback.created_at >= cutoff_date
        ).all()
    
    # ============================================================================
    # Notification Operations
    # ============================================================================
    
    def add_notification(self, session: Session, notification_data: Dict[str, Any]) -> Notification:
        """Add notification record"""
        notification = Notification(**notification_data)
        session.add(notification)
        session.commit()
        return notification
    
    def get_notification_log(self, session: Session, days: int = 7) -> List[Notification]:
        """Get notification logs"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return session.query(Notification).filter(
            Notification.created_at >= cutoff_date
        ).all()
    
    # ============================================================================
    # Statistics Operations
    # ============================================================================
    
    def calculate_hit_rate(self, session: Session, days: int = 7) -> float:
        """Calculate hit rate"""
        cutoff_date = datetime.now() - timedelta(days=days)
        predictions = session.query(Prediction).filter(
            Prediction.prediction_date >= cutoff_date
        ).all()
        
        if not predictions:
            return 0.0
        
        hits = sum(1 for p in predictions if p.result and p.result.get("is_hit"))
        return hits / len(predictions)
    
    def calculate_recovery_rate(self, session: Session, days: int = 7) -> float:
        """Calculate recovery rate (回収率)"""
        cutoff_date = datetime.now() - timedelta(days=days)
        predictions = session.query(Prediction).filter(
            Prediction.prediction_date >= cutoff_date
        ).all()
        
        if not predictions:
            return 0.0
        
        total_payout = sum(
            p.result.get("actual_odds", 0) if p.result and p.result.get("is_hit") else 0
            for p in predictions
        )
        
        return total_payout / len(predictions)
    
    def close(self):
        """Close database connection"""
        self.engine.dispose()
        logger.info("Database connection closed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get or create global database manager"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def init_db():
    """Initialize database"""
    db_manager = get_db_manager()
    logger.info("Database initialized")
    return db_manager
