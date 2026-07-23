"""
パフォーマンス計測
実行時間やメモリ使用量の計測
"""

import logging
import time
import psutil
import os
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger(__name__)


class PerformanceMonitor:
    """パフォーマンス計測クラス"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.process = psutil.Process(os.getpid())
    
    def start(self) -> None:
        """計測を開始"""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        logger.debug(f"パフォーマンス計測開始 | メモリ: {self.start_memory:.2f}MB")
    
    def end(self) -> dict:
        """計測を終了"""
        self.end_time = time.time()
        self.end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        elapsed_time = self.end_time - self.start_time
        memory_used = self.end_memory - self.start_memory
        
        metrics = {
            'elapsed_time': elapsed_time,
            'start_memory_mb': self.start_memory,
            'end_memory_mb': self.end_memory,
            'memory_used_mb': memory_used,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.debug(
            f"パフォーマンス計測完了 | "
            f"時間: {elapsed_time:.2f}秒 | "
            f"メモリ増加: {memory_used:.2f}MB"
        )
        
        return metrics
    
    @staticmethod
    def get_system_info() -> dict:
        """システム情報を取得"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            process = psutil.Process(os.getpid())
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / 1024 / 1024,
                'memory_available_mb': memory.available / 1024 / 1024,
                'process_memory_mb': process.memory_info().rss / 1024 / 1024,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"システム情報取得エラー: {e}")
            return {}


def monitor_performance(func):
    """パフォーマンス計測デコレータ"""
    def wrapper(*args, **kwargs):
        monitor = PerformanceMonitor()
        monitor.start()
        
        try:
            result = func(*args, **kwargs)
            metrics = monitor.end()
            logger.info(f"[{func.__name__}] {metrics}")
            return result
        except Exception as e:
            logger.error(f"[{func.__name__}] 実行エラー: {e}", exc_info=True)
            raise
    
    return wrapper


if __name__ == "__main__":
    monitor = PerformanceMonitor()
    
    # テスト
    monitor.start()
    time.sleep(1)
    metrics = monitor.end()
    print(f"計測結果: {metrics}")
    
    # システム情報
    sys_info = PerformanceMonitor.get_system_info()
    print(f"システム情報: {sys_info}")
