"""
ロギング設定
アプリケーション全体のログ出力を管理
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# ログディレクトリを作成
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def setup_logger(name, level=logging.INFO):
    """ロガーを設定"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # ログファイルのパスを定義
    log_file = os.path.join(LOG_DIR, "boat_race_predictor.log")
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    
    # ファイルハンドラー（ローテーション対応）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    # ハンドラーをロガーに追加
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    
    return logger


def log_execution_time(logger):
    """実行時間をログに記録するデコレータ"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            logger.info(f"実行開始: {func.__name__}")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"実行完了: {func.__name__} ({elapsed:.2f}秒)")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"実行失敗: {func.__name__} ({elapsed:.2f}秒) - {e}", exc_info=True)
                raise
        return wrapper
    return decorator


if __name__ == "__main__":
    # ロギング設定のテスト
    test_logger = setup_logger(__name__)
    test_logger.info("ロギング設定テスト: INFO")
    test_logger.warning("ロギング設定テスト: WARNING")
    test_logger.error("ロギング設定テスト: ERROR")
    print("✅ ロギング設定完了")
