"""
LINE Notification Module
Sends predictions via LINE Notify
"""

import requests
from typing import Optional, Dict, Any
from datetime import datetime

import config
from utils.logger import logger


class LineNotifier:
    """LINE notification class"""
    
    # LINE Notify API endpoint
    LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"
    
    def __init__(self):
        """Initialize LINE notifier"""
        self.token = config.LINE_NOTIFY_TOKEN
        self.enabled = config.USE_LINE
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
    
    def send_prediction_notification(
        self,
        predictions: Optional[Dict[str, Any]] = None,
        mode: str = "today"
    ) -> bool:
        """
        Send prediction notification via LINE
        
        Args:
            predictions: Prediction data
            mode: 'today' or 'tomorrow'
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.warning("LINE notifications are disabled")
            return False
        
        try:
            message = self._create_prediction_message(predictions, mode)
            return self._send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending LINE notification: {e}")
            return False
    
    def send_alert_notification(
        self,
        alert_type: str,
        message: str
    ) -> bool:
        """
        Send alert notification via LINE
        
        Args:
            alert_type: Type of alert (info, warning, error)
            message: Alert message
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.warning("LINE notifications are disabled")
            return False
        
        try:
            emoji = {
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
            }.get(alert_type, "📢")
            
            full_message = f"{emoji} {message}"
            return self._send_message(full_message)
            
        except Exception as e:
            logger.error(f"Error sending LINE alert: {e}")
            return False
    
    def send_result_notification(
        self,
        result_data: Dict[str, Any]
    ) -> bool:
        """
        Send result notification via LINE
        
        Args:
            result_data: Result data with hit/miss information
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.warning("LINE notifications are disabled")
            return False
        
        try:
            message = self._create_result_message(result_data)
            return self._send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending LINE result: {e}")
            return False
    
    def _send_message(self, message: str) -> bool:
        """
        Send message via LINE Notify API
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully
        """
        try:
            payload = {"message": message}
            response = requests.post(
                self.LINE_NOTIFY_URL,
                headers=self.headers,
                data=payload,
                timeout=config.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                logger.info("LINE notification sent successfully")
                return True
            else:
                logger.error(f"LINE API returned status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending LINE message: {e}")
            return False
    
    def _create_prediction_message(self, predictions: Optional[Dict[str, Any]], mode: str) -> str:
        """
        Create prediction message for LINE
        
        Args:
            predictions: Prediction data
            mode: 'today' or 'tomorrow'
            
        Returns:
            Formatted message
        """
        lines = []
        lines.append(f"🚤 ボートレース予想 - {mode.upper()}")
        lines.append(f"📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}")
        lines.append("")
        
        if predictions:
            # High confidence
            if "high_confidence" in predictions and predictions["high_confidence"]:
                lines.append("✅ 確実性の高い3連単:")
                for i, pred in enumerate(predictions["high_confidence"][:3], 1):
                    race_num = pred.get('race_number', i)
                    prediction = pred.get('prediction', [])
                    odds = pred.get('estimated_odds', 0)
                    pred_str = "-".join(str(p) for p in prediction[:3])
                    lines.append(f"  R{race_num}: {pred_str} ({odds:.1f}倍)")
                lines.append("")
            
            # High odds
            if "high_odds" in predictions and predictions["high_odds"]:
                lines.append("🎯 穴確率が高い3連単:")
                for i, pred in enumerate(predictions["high_odds"][:3], 1):
                    race_num = pred.get('race_number', i)
                    prediction = pred.get('prediction', [])
                    odds = pred.get('estimated_odds', 0)
                    pred_str = "-".join(str(p) for p in prediction[:3])
                    lines.append(f"  R{race_num}: {pred_str} ({odds:.1f}倍)")
        
        lines.append("")
        lines.append("⚠️ 参考情報です。自己責任でご判断ください。")
        
        return "\n".join(lines)
    
    def _create_result_message(self, result_data: Dict[str, Any]) -> str:
        """
        Create result message for LINE
        
        Args:
            result_data: Result data
            
        Returns:
            Formatted message
        """
        is_hit = result_data.get("is_hit", False)
        actual_odds = result_data.get("actual_odds", 0)
        race_num = result_data.get("race_number", "")
        
        emoji = "✅" if is_hit else "❌"
        status = "的中" if is_hit else "外れ"
        
        message = f"{emoji} R{race_num}: {status}\n"
        if is_hit:
            message += f"配当: {actual_odds:.1f}倍"
        
        return message
