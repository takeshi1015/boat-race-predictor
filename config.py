"""
Configuration file for Boat Race Predictor
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==================== DATABASE ====================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/boat_race_db")
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "False").lower() == "true"

# ==================== EMAIL SETTINGS ====================
USE_EMAIL = os.getenv("USE_EMAIL", "True").lower() == "true"
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "your_email@example.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your_app_password")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_RECIPIENTS = [
    email.strip() for email in os.getenv("EMAIL_RECIPIENTS", "").split(",")
    if email.strip()
]

# ==================== LINE SETTINGS ====================
USE_LINE = os.getenv("USE_LINE", "True").lower() == "true"
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "your_line_token")

# ==================== SCRAPER SETTINGS ====================
SCRAPER_BASE_URL = "https://boatrace.jp"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
SCRAPER_RETRY_COUNT = int(os.getenv("SCRAPER_RETRY_COUNT", "3"))
SCRAPER_RETRY_DELAY = int(os.getenv("SCRAPER_RETRY_DELAY", "5"))

# ==================== PREDICTION SETTINGS ====================
HIGH_CONFIDENCE_RACES = int(os.getenv("HIGH_CONFIDENCE_RACES", "5"))
HIGH_ODDS_RACES = int(os.getenv("HIGH_ODDS_RACES", "5"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

# Prediction model weights
PREDICTION_WEIGHTS = {
    "statistical": 0.25,
    "ml": 0.35,
    "rule_based": 0.20,
}

# ==================== MACHINE LEARNING ====================
MODEL_SAVE_PATH = os.getenv("MODEL_SAVE_PATH", "./models/")
EPOCHS = int(os.getenv("EPOCHS", "50"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))
LEARNING_RATE = float(os.getenv("LEARNING_RATE", "0.001"))
NN_DROPOUT_RATE = float(os.getenv("NN_DROPOUT_RATE", "0.3"))

# ==================== REINFORCEMENT LEARNING ====================
Q_LEARNING_ALPHA = float(os.getenv("Q_LEARNING_ALPHA", "0.1"))  # Learning rate
Q_LEARNING_GAMMA = float(os.getenv("Q_LEARNING_GAMMA", "0.99"))  # Discount factor
Q_LEARNING_EPSILON = float(os.getenv("Q_LEARNING_EPSILON", "0.1"))  # Exploration rate

# ==================== SCHEDULER SETTINGS ====================
SCHEDULE_TODAY = os.getenv("SCHEDULE_TODAY", "06:00")
SCHEDULE_TOMORROW = os.getenv("SCHEDULE_TOMORROW", "18:00")
SCHEDULE_EVALUATE = os.getenv("SCHEDULE_EVALUATE", "23:30")

# ==================== PERFORMANCE MONITORING ====================
ACCURACY_ALERT_THRESHOLD = float(os.getenv("ACCURACY_ALERT_THRESHOLD", "0.40"))
ALERT_LOW_ACCURACY = os.getenv("ALERT_LOW_ACCURACY", "True").lower() == "true"

# ==================== LOGGING ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/boat_race_predictor.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10 MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# ==================== ENVIRONMENT ====================
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
