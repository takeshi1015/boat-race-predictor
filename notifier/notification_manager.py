"""
Notification Manager
Manages all notification operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from notifier.email_notifier import EmailNotifier
from notifier.line_notifier import LineNotifier
from database.db_manager import get_db_manager
from utils.logger import logger


class NotificationManager:
    """Manages email and LINE notifications"""
    
    def __init__(self):
        """Initialize notification manager"""
        self.email_notifier = EmailNotifier()
        self.line_notifier = LineNotifier()
        self.db_manager = get_db_manager()
    
    def send_predictions(
        self,
        predictions: Dict[str, Any],
        mode: str = "today",
        recipients: Optional[List[str]] = None
    ) -> bool:
        """
        Send predictions via email and LINE
        
        Args:
            predictions: Prediction data
            mode: 'today' or 'tomorrow'
            recipients: Optional list of email recipients
            
        Returns:
            True if at least one notification was sent
        """
        logger.info(f"Sending predictions ({mode})")
        
        results = []
        
        # Send email
        email_sent = self.email_notifier.send_prediction_email(
            recipients=recipients,
            predictions=predictions,
            mode=mode
        )
        results.append(email_sent)
        
        # Send LINE
        line_sent = self.line_notifier.send_prediction_notification(
            predictions=predictions,
            mode=mode
        )
        results.append(line_sent)
        
        # Log notification
        success = any(results)
        self._log_notification(
            "prediction",
            f"Predictions sent ({mode})",
            "sent" if success else "failed"
        )
        
        return success
    
    def send_alert(
        self,
        alert_type: str,
        title: str,
        message: str,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """
        Send alert via email and LINE
        
        Args:
            alert_type: Type of alert (info, warning, error)
            title: Alert title
            message: Alert message
            recipients: Optional list of email recipients
            
        Returns:
            True if at least one notification was sent
        """
        logger.info(f"Sending alert: {title}")
        
        results = []
        
        # Send email
        email_sent = self.email_notifier.send_alert_email(
            recipients=recipients,
            subject=title,
            message_text=message
        )
        results.append(email_sent)
        
        # Send LINE
        line_sent = self.line_notifier.send_alert_notification(
            alert_type=alert_type,
            message=f"{title}: {message}"
        )
        results.append(line_sent)
        
        # Log notification
        success = any(results)
        self._log_notification(
            "alert",
            title,
            "sent" if success else "failed",
            message
        )
        
        return success
    
    def send_results(
        self,
        result_data: Dict[str, Any],
        recipients: Optional[List[str]] = None
    ) -> bool:
        """
        Send result notification
        
        Args:
            result_data: Result data
            recipients: Optional list of email recipients
            
        Returns:
            True if notification was sent
        """
        logger.info("Sending result notification")
        
        results = []
        
        # Send LINE result
        line_sent = self.line_notifier.send_result_notification(
            result_data=result_data
        )
        results.append(line_sent)
        
        # Send email result
        email_msg = f"レース {result_data.get('race_number', '')}: "
        if result_data.get("is_hit"):
            email_msg += f"的中! 配当: {result_data.get('actual_odds', 0):.1f}倍"
        else:
            email_msg += "外れました。"
        
        email_sent = self.email_notifier.send_alert_email(
            recipients=recipients,
            subject="レース結果",
            message_text=email_msg
        )
        results.append(email_sent)
        
        # Log notification
        success = any(results)
        self._log_notification(
            "result",
            f"Race {result_data.get('race_number', '')}",
            "sent" if success else "failed"
        )
        
        return success
    
    def _log_notification(
        self,
        notification_type: str,
        subject: str,
        status: str,
        content: str = ""
    ) -> None:
        """
        Log notification to database
        
        Args:
            notification_type: Type of notification
            subject: Subject
            status: Status (sent, failed, pending)
            content: Notification content
        """
        try:
            session = self.db_manager.get_session()
            
            notification_data = {
                "notification_type": notification_type,
                "recipient": "system",
                "subject": subject,
                "content": content,
                "status": status,
            }
            
            self.db_manager.add_notification(session, notification_data)
            session.close()
            
        except Exception as e:
            logger.error(f"Error logging notification: {e}")
