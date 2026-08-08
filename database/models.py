"""
Database models for Boat Race Predictor
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Player(Base):
    """Player statistics table"""
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(String, unique=True, index=True)
    name = Column(String)
    registered_location = Column(String)
    
    # Statistics
    win_rate = Column(Float, default=0.0)
    place_rate = Column(Float, default=0.0)
    payoff_rate = Column(Float, default=0.0)
    avg_speed = Column(Float, default=0.0)
    
    # Recent performance
    recent_form = Column(Float, default=0.0)  # 直近成績
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = {"comment": "プレイヤー統計"}


class Boat(Base):
    """Boat statistics table"""
    __tablename__ = "boats"
    
    id = Column(Integer, primary_key=True, index=True)
    boat_id = Column(String, unique=True, index=True)
    venue = Column(String)
    boat_number = Column(Integer)
    
    # Statistics
    boat_win_rate = Column(Float, default=0.0)
    boat_place_rate = Column(Float, default=0.0)
    
    # Boat info
    boat_age = Column(Integer, default=0)
    boat_propeller = Column(String)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = {"comment": "ボート統計"}


class Race(Base):
    """Race information table"""
    __tablename__ = "races"
    
    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(String, unique=True, index=True)
    venue = Column(String, index=True)
    place = Column(String, index=True)  # 日本語会場名 (e.g. 桐生, 戸田)
    date = Column(DateTime, index=True)
    race_number = Column(Integer)
    race_grade = Column(String)  # G1, G2, G3, etc.
    race_distance = Column(Integer)
    
    # Conditions
    wind_speed = Column(Float, default=0.0)
    wind_direction = Column(String)
    water_surface = Column(String)  # calm, slightly_rough, rough
    weather = Column(String)        # sunny, cloudy, rainy
    water_condition = Column(String)  # calm, slight, moderate, rough
    temperature = Column(Float, default=0.0)
    humidity = Column(Float, default=0.0)
    tide = Column(String)
    
    # Race info
    number_of_boats = Column(Integer, default=6)
    time_of_day = Column(String)    # morning, midday, evening
    start_time_hour = Column(Integer, default=0)  # 開始時刻（時）
    
    # Results
    result = Column(JSON)  # {1st: player_id, 2nd: player_id, 3rd: player_id}
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = {"comment": "レース情報"}


class Prediction(Base):
    """Prediction table"""
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(String, index=True)
    prediction_date = Column(DateTime, index=True)
    prediction_type = Column(String)  # high_confidence, high_odds
    
    # Prediction data
    predicted_order = Column(JSON)  # [player1, player2, player3]
    confidence = Column(Float)
    estimated_odds = Column(Float)
    
    # Model info
    model_version = Column(String)
    methods_used = Column(JSON)  # List of prediction methods
    
    # Result
    result = Column(JSON)  # {is_hit: bool, actual_odds: float}
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = {"comment": "予想記録"}


class ModelPerformance(Base):
    """Model performance tracking table"""
    __tablename__ = "model_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, index=True)
    model_version = Column(String)
    
    # Accuracy metrics
    hit_rate = Column(Float)  # 的中率
    recovery_rate = Column(Float)  # 回収率
    
    # Statistics
    total_predictions = Column(Integer)
    total_hits = Column(Integer)
    
    # Date range
    evaluation_start = Column(DateTime)
    evaluation_end = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    
    __table_args__ = {"comment": "モデル性能追跡"}


class RaceEntry(Base):
    """Race entry (one row per boat per race) table"""
    __tablename__ = "race_entries"

    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(String, index=True)
    frame_number = Column(Integer)        # 1～6号艇

    # 選手情報
    player_name = Column(String)
    player_id = Column(String, index=True)
    rank = Column(String)                 # A1, A2, B1, B2
    wins_rate = Column(Float, default=0.0)    # 勝率
    place_rate = Column(Float, default=0.0)   # 連対率
    avg_start_timing = Column(Float, default=0.0)  # スタート差（秒）
    recent_results = Column(JSON)         # 直近5走 ["1","2","3","1","2"]

    # 艇・エンジン情報
    boat_number = Column(String)
    boat_wins_rate = Column(Float, default=0.0)   # 使用艇の勝率
    engine_number = Column(String)
    engine_wins_rate = Column(Float, default=0.0) # 使用エンジンの勝率
    exhibition_time = Column(Float, default=0.0)  # 展示タイム（秒）

    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = {"comment": "レースエントリー（出走艇）"}


class RaceResult(Base):
    """Actual race result table"""
    __tablename__ = "race_results"

    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(String, unique=True, index=True)

    # 着順
    first_place = Column(Integer)         # 1着艇番号
    second_place = Column(Integer)        # 2着艇番号
    third_place = Column(Integer)         # 3着艇番号

    # 配当（100円当たり）
    payoff_win = Column(Integer)          # 単勝配当
    payoff_place_1 = Column(Integer)      # 複勝1着配当
    payoff_place_2 = Column(Integer)      # 複勝2着配当
    payoff_exacta = Column(Integer)       # 2連単配当
    payoff_quinella = Column(Integer)     # 2連複配当
    payoff_trifecta = Column(Integer)     # 3連単配当
    payoff_trio = Column(Integer)         # 3連複配当

    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = {"comment": "レース実結果・配当"}


class LearningFeedback(Base):
    """Learning feedback table for reinforcement learning"""
    __tablename__ = "learning_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer)
    
    # State info
    state = Column(JSON)  # Race conditions and player info
    action = Column(JSON)  # Prediction made
    reward = Column(Float)  # Reward signal (positive/negative)
    
    # Next state
    next_state = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    
    __table_args__ = {"comment": "強化学習フィードバック"}


class Notification(Base):
    """Notification log table"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    notification_type = Column(String)  # email, line
    recipient = Column(String)
    subject = Column(String)
    content = Column(Text)
    
    # Status
    status = Column(String)  # sent, failed, pending
    error_message = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    sent_at = Column(DateTime, nullable=True)
    
    __table_args__ = {"comment": "通知ログ"}
