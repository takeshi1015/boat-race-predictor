"""
LINE通知機能
LINE Notify経由でLINEメッセージを送信
"""

import requests
import logging
from config import Config
from utils.logger import setup_logger

logger = setup_logger(__name__)


class LineNotifier:
    """LINE通知クラス"""
    
    LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"
    
    def __init__(self):
        self.config = Config()
        self.access_token = self.config.LINE_NOTIFY_TOKEN
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    
    def send_predictions(self, predictions, title="予測結果"):
        """予測結果をLINE送信"""
        try:
            if not self.config.USE_LINE:
                logger.info("LINE通知は無効です")
                return
            
            message = self._format_predictions_message(predictions, title)
            self._send_message(message)
            logger.info("✅ 予測結果のLINE通知を送信しました")
        except Exception as e:
            logger.error(f"予測LINE送信エラー: {e}", exc_info=True)
    
    def send_alert(self, message):
        """アラートメッセージをLINE送信"""
        try:
            if not self.config.USE_LINE:
                return
            
            alert_message = f"⚠️ ボートレース予測: アラート\n\n{message}"
            self._send_message(alert_message)
            logger.info("✅ アラートLINE通知を送信しました")
        except Exception as e:
            logger.error(f"アラートLINE送信エラー: {e}", exc_info=True)
    
    def send_report(self, report):
        """レポートをLINE送信"""
        try:
            if not self.config.USE_LINE:
                return
            
            message = self._format_report_message(report)
            self._send_message(message)
            logger.info("✅ レポートLINE通知を送信しました")
        except Exception as e:
            logger.error(f"レポートLINE送信エラー: {e}", exc_info=True)
    
    def _send_message(self, message):
        """LINE Notifyにメッセージを送信"""
        try:
            payload = {'message': message}
            response = requests.post(
                self.LINE_NOTIFY_URL,
                headers=self.headers,
                data=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"LINE送信成功")
        except requests.exceptions.RequestException as e:
            logger.error(f"LINE送信エラー: {e}")
            raise
    
    def _format_predictions_message(self, predictions, title):
        """予測結果をLINEメッセージにフォーマット"""
        message = f"🚤 ボートレース予測\n\n【{title}】\n\n"
        
        for i, pred in enumerate(predictions[:5], 1):  # 最大5件
            message += f"第{i}レース\n"
            message += f"日付: {pred.get('date', 'N/A')}\n"
            message += f"予測: {pred.get('prediction', 'N/A')}\n"
            message += f"信頼度: {pred.get('confidence', 0):.1%}\n\n"
        
        message += "\n注意: 予測は参考情報です\n投資は自己責任でお願いします"
        return message
    
    def _format_report_message(self, report):
        """レポートをLINEメッセージにフォーマット"""
        message = f"📊 ボートレース予測 日次レポート\n\n"
        message += f"本日の成績:\n"
        message += f"的中: {report.get('hits', 0)}件\n"
        message += f"外れ: {report.get('misses', 0)}件\n"
        message += f"的中率: {report.get('hit_rate', 0):.1%}\n\n"
        message += f"累計成績:\n"
        message += f"累計的中: {report.get('total_hits', 0)}件\n"
        message += f"累計的中率: {report.get('total_hit_rate', 0):.1%}\n"
        message += f"回収率: {report.get('total_return_rate', 0):.1%}"
        
        return message


if __name__ == "__main__":
    notifier = LineNotifier()
    
    # テスト: 予測結果を送信
    test_predictions = [
        {
            'date': '2026-07-23',
            'prediction': '1-2-3',
            'confidence': 0.75
        }
    ]
    notifier.send_predictions(test_predictions, "テスト予測")
