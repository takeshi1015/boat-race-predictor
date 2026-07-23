"""
データベース管理
SQLAlchemy経由でデータベース接続を管理
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from config import Config
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Base class for ORM models
Base = declarative_base()


class DatabaseManager:
    """データベース接続管理クラス"""
    
    def __init__(self):
        self.config = Config()
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """データベースエンジンを初期化"""
        try:
            db_url = self.config.DATABASE_URL
            logger.info(f"データベースに接続中: {db_url}")
            
            self.engine = create_engine(
                db_url,
                echo=self.config.DEBUG_MODE,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # テーブルを作成
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ データベース接続成功")
        except Exception as e:
            logger.error(f"データベース初期化エラー: {e}", exc_info=True)
            raise
    
    def get_session(self) -> Session:
        """セッションを取得"""
        if self.SessionLocal is None:
            raise RuntimeError("データベースエンジンが初期化されていません")
        return self.SessionLocal()
    
    def close(self):
        """データベース接続を閉じる"""
        if self.engine:
            self.engine.dispose()
            logger.info("データベース接続を閉じました")
    
    def health_check(self) -> bool:
        """データベース接続状態を確認"""
        try:
            session = self.get_session()
            session.execute("SELECT 1")
            session.close()
            logger.info("✅ データベースヘルスチェック: OK")
            return True
        except Exception as e:
            logger.error(f"データベースヘルスチェック失敗: {e}")
            return False


# グローバルインスタンス
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """データベースマネージャーを取得"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db_session() -> Session:
    """データベースセッションを取得"""
    return get_db_manager().get_session()


def close_db():
    """データベース接続を閉じる"""
    global _db_manager
    if _db_manager:
        _db_manager.close()
        _db_manager = None


# ORM Models
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime


class Race(Base):
    """レース情報テーブル"""
    __tablename__ = "races"
    
    id = Column(Integer, primary_key=True)
    date = Column(String, nullable=False)
    place_code = Column(String, nullable=False)
    race_number = Column(Integer, nullable=False)
    start_time = Column(String, nullable=True)
    weather = Column(String, nullable=True)
    water_condition = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Prediction(Base):
    """予測結果テーブル"""
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, nullable=False)
    predicted_position = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    model_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Result(Base):
    """レース結果テーブル"""
    __tablename__ = "results"
    
    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, nullable=False)
    first_place = Column(Integer, nullable=False)
    second_place = Column(Integer, nullable=False)
    third_place = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Performance(Base):
    """パフォーマンスメトリクステーブル"""
    __tablename__ = "performance"
    
    id = Column(Integer, primary_key=True)
    accuracy = Column(Float, nullable=False)
    precision = Column(Float, nullable=False)
    recall = Column(Float, nullable=False)
    f1_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


if __name__ == "__main__":
    db_manager = get_db_manager()
    if db_manager.health_check():
        print("✅ データベースセットアップ完了")
