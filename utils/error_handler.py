"""
エラーハンドリング
カスタム例外とエラーハンドラー
"""

import logging
from utils.logger import setup_logger

logger = setup_logger(__name__)


class BoatRacePredictorException(Exception):
    """基本例外クラス"""
    pass


class DatabaseException(BoatRacePredictorException):
    """データベース関連の例外"""
    pass


class ScraperException(BoatRacePredictorException):
    """スクレイパー関連の例外"""
    pass


class PredictionException(BoatRacePredictorException):
    """予測関連の例外"""
    pass


class NotificationException(BoatRacePredictorException):
    """通知関連の例外"""
    pass


class SchedulerException(BoatRacePredictorException):
    """スケジューラー関連の例外"""
    pass


class ErrorHandler:
    """エラーハンドラー"""
    
    @staticmethod
    def handle_exception(exception: Exception, context: str = "") -> None:
        """例外をハンドル"""
        error_message = str(exception)
        
        if context:
            logger.error(f"[{context}] {error_message}", exc_info=True)
        else:
            logger.error(f"エラー発生: {error_message}", exc_info=True)
        
        # エラーの種類に応じた処理
        if isinstance(exception, DatabaseException):
            logger.critical("データベースエラーが発生しました")
        elif isinstance(exception, ScraperException):
            logger.warning("スクレイパーエラーが発生しました")
        elif isinstance(exception, PredictionException):
            logger.warning("予測処理でエラーが発生しました")
        elif isinstance(exception, NotificationException):
            logger.warning("通知送信でエラーが発生しました")
        elif isinstance(exception, SchedulerException):
            logger.critical("スケジューラーエラーが発生しました")
    
    @staticmethod
    def retry_operation(func, max_retries: int = 3, delay: float = 1.0):
        """操作を再試行"""
        import time
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"再試行 {attempt + 1}/{max_retries - 1}")
                    time.sleep(delay)
                else:
                    logger.error(f"最大再試行回数に達しました")
                    raise


if __name__ == "__main__":
    # テスト
    handler = ErrorHandler()
    
    try:
        raise PredictionException("予測処理でエラーが発生しました")
    except Exception as e:
        handler.handle_exception(e, "テスト処理")
