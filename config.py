"""Configuration file for Boat Race Predictor."""

import os
from dotenv import load_dotenv

load_dotenv()

# ==================== DATABASE ====================
SQLITE_FALLBACK_URL = "sqlite:///boat_race_predictor.db"
DATABASE_URL = os.getenv("DATABASE_URL", SQLITE_FALLBACK_URL)
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "False").lower() == "true"

# ==================== EMAIL SETTINGS ====================
USE_EMAIL = os.getenv("USE_EMAIL", "False").lower() == "true"
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "your_email@example.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your_app_password")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_RECIPIENTS_RAW = os.getenv("EMAIL_RECIPIENTS", "")
EMAIL_RECIPIENTS = [email.strip() for email in EMAIL_RECIPIENTS_RAW.split(",") if email.strip()]

# ==================== LINE SETTINGS ====================
USE_LINE = os.getenv("USE_LINE", "False").lower() == "true"
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "your_line_token")

# ==================== SCRAPER SETTINGS ====================
SCRAPER_BASE_URL = "https://boatrace.jp"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
SCRAPER_RETRY_COUNT = int(os.getenv("SCRAPER_RETRY_COUNT", "3"))
SCRAPER_RETRY_DELAY = int(os.getenv("SCRAPER_RETRY_DELAY", "5"))

# ==================== PREDICTION SETTINGS ====================
# Business rule: env override cannot lower this under 0.7
# because predictions below 0.7 are not buy candidates.
MIN_CONFIDENCE_THRESHOLD = 0.7
HIGH_CONFIDENCE_RACES = int(os.getenv("HIGH_CONFIDENCE_RACES", "5"))
HIGH_ODDS_RACES = int(os.getenv("HIGH_ODDS_RACES", "5"))
CONFIDENCE_THRESHOLD = max(MIN_CONFIDENCE_THRESHOLD, float(os.getenv("CONFIDENCE_THRESHOLD", "0.7")))

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
Q_LEARNING_ALPHA = float(os.getenv("Q_LEARNING_ALPHA", "0.1"))
Q_LEARNING_GAMMA = float(os.getenv("Q_LEARNING_GAMMA", "0.99"))
Q_LEARNING_EPSILON = float(os.getenv("Q_LEARNING_EPSILON", "0.1"))

# ==================== SCHEDULER SETTINGS ====================
SCHEDULE_TODAY = os.getenv("SCHEDULE_TODAY", "06:00")
SCHEDULE_TOMORROW = os.getenv("SCHEDULE_TOMORROW", "18:00")
SCHEDULE_EVALUATE = os.getenv("SCHEDULE_EVALUATE", "23:30")
SCHEDULE_RETRAIN = os.getenv("SCHEDULE_RETRAIN", "23:40")
AUTO_LEARNING_ENABLED = os.getenv("AUTO_LEARNING_ENABLED", "True").lower() == "true"

# ==================== PERFORMANCE MONITORING ====================
ACCURACY_ALERT_THRESHOLD = float(os.getenv("ACCURACY_ALERT_THRESHOLD", "0.40"))
ALERT_LOW_ACCURACY = os.getenv("ALERT_LOW_ACCURACY", "True").lower() == "true"

# ==================== LOGGING ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/boat_race_predictor.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# ==================== ENVIRONMENT ====================
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# ==================== WEB / API SETTINGS ====================
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
WEB_DEBUG = os.getenv("WEB_DEBUG", "False").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# ==================== OUTPUT SETTINGS ====================
OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", "outputs")
OUTPUTS_HISTORY_DIR = os.path.join(OUTPUTS_DIR, "history")
OUTPUTS_MAX_HISTORY = int(os.getenv("OUTPUTS_MAX_HISTORY", "100"))


class Config:
    """Backward-compatible object-style configuration."""

    def __init__(self):
        self.DATABASE_URL = DATABASE_URL
        self.DATABASE_ECHO = DATABASE_ECHO
        self.USE_EMAIL = USE_EMAIL
        self.EMAIL_ADDRESS = EMAIL_ADDRESS
        self.EMAIL_PASSWORD = EMAIL_PASSWORD
        self.SMTP_SERVER = SMTP_SERVER
        self.SMTP_PORT = SMTP_PORT
        self.EMAIL_RECIPIENTS = EMAIL_RECIPIENTS
        self.USE_LINE = USE_LINE
        self.LINE_NOTIFY_TOKEN = LINE_NOTIFY_TOKEN
        self.SCHEDULE_TODAY = SCHEDULE_TODAY
        self.SCHEDULE_TOMORROW = SCHEDULE_TOMORROW
        self.SCHEDULE_EVALUATE = SCHEDULE_EVALUATE
        self.SCHEDULE_RETRAIN = SCHEDULE_RETRAIN
        self.AUTO_LEARNING_ENABLED = AUTO_LEARNING_ENABLED
