"""
Email Notification Module
Sends predictions via email
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any
from datetime import datetime

import config
from utils.logger import logger


class EmailNotifier:
    """Email notification class"""
    
    def __init__(self):
        """Initialize email notifier"""
        self.smtp_server = config.SMTP_SERVER
        self.smtp_port = config.SMTP_PORT
        self.sender_email = config.EMAIL_ADDRESS
        self.sender_password = config.EMAIL_PASSWORD
        self.enabled = config.USE_EMAIL
    
    def send_prediction_email(
        self,
        recipients: Optional[List[str]] = None,
        subject: str = "ボートレース予想",
        predictions: Optional[Dict[str, Any]] = None,
        mode: str = "today"
    ) -> bool:
        """
        Send prediction email
        
        Args:
            recipients: List of recipient emails
            subject: Email subject
            predictions: Prediction data
            mode: 'today' or 'tomorrow'
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.warning("Email notifications are disabled")
            return False
        
        if recipients is None:
            recipients = config.EMAIL_RECIPIENTS
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = f"{subject} - {mode.upper()}"
            message["From"] = self.sender_email
            message["To"] = ", ".join(recipients)
            
            # Create email body
            body = self._create_email_body(predictions, mode)
            html_body = self._create_html_body(predictions, mode)
            
            # Attach parts
            part1 = MIMEText(body, "plain", "utf-8")
            part2 = MIMEText(html_body, "html", "utf-8")
            message.attach(part1)
            message.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            logger.info(f"Email sent to {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    def send_alert_email(
        self,
        recipients: Optional[List[str]] = None,
        subject: str = "アラート",
        message_text: str = ""
    ) -> bool:
        """
        Send alert email
        
        Args:
            recipients: List of recipient emails
            subject: Email subject
            message_text: Email body text
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.warning("Email notifications are disabled")
            return False
        
        if recipients is None:
            recipients = config.EMAIL_RECIPIENTS
        
        try:
            message = MIMEMultipart()
            message["Subject"] = f"[ALERT] {subject}"
            message["From"] = self.sender_email
            message["To"] = ", ".join(recipients)
            
            message.attach(MIMEText(message_text, "plain", "utf-8"))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            logger.info(f"Alert email sent to {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending alert email: {e}")
            return False
    
    def _create_email_body(self, predictions: Optional[Dict[str, Any]], mode: str) -> str:
        """
        Create plain text email body
        
        Args:
            predictions: Prediction data
            mode: 'today' or 'tomorrow'
            
        Returns:
            Plain text email body
        """
        lines = []
        lines.append("="*60)
        lines.append(f"🚤 ボートレース予想 - {mode.upper()}")
        lines.append("="*60)
        lines.append(f"📅 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
        lines.append("")
        
        if predictions:
            # High confidence
            if "high_confidence" in predictions:
                lines.append("✅ 【確実性の高い3連単】(5レース)")
                lines.append("-"*60)
                for i, pred in enumerate(predictions["high_confidence"][:5], 1):
                    race_num = pred.get('race_number', i)
                    prediction = pred.get('prediction', [])
                    confidence = pred.get('confidence', 0)
                    odds = pred.get('estimated_odds', 0)
                    pred_str = " → ".join(str(p) for p in prediction[:3])
                    lines.append(
                        f"{i}. レース{race_num}: {pred_str} "
                        f"(信頼度: {confidence:.1%}, 推定倍率: {odds:.1f}倍)"
                    )
                lines.append("")
            
            # High odds
            if "high_odds" in predictions:
                lines.append("🎯 【穴確率が高い3連単】(5レース)")
                lines.append("-"*60)
                for i, pred in enumerate(predictions["high_odds"][:5], 1):
                    race_num = pred.get('race_number', i)
                    prediction = pred.get('prediction', [])
                    odds = pred.get('estimated_odds', 0)
                    pred_str = " → ".join(str(p) for p in prediction[:3])
                    lines.append(
                        f"{i}. レース{race_num}: {pred_str} "
                        f"(推定倍率: {odds:.1f}倍)"
                    )
                lines.append("")
        
        lines.append("="*60)
        lines.append("⚠️ このソフトウェアは参考情報です")
        lines.append("実際の購入判断は自己責任で行ってください")
        lines.append("="*60)
        
        return "\n".join(lines)
    
    def _create_html_body(self, predictions: Optional[Dict[str, Any]], mode: str) -> str:
        """
        Create HTML email body
        
        Args:
            predictions: Prediction data
            mode: 'today' or 'tomorrow'
            
        Returns:
            HTML email body
        """
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px;">
                    <h1 style="text-align: center; color: #333;">🚤 ボートレース予想</h1>
                    <p style="text-align: center; color: #666;">{mode.upper()}</p>
                    <p style="text-align: center; color: #999; font-size: 12px;">{datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>
                    <hr style="border: none; border-top: 1px solid #ddd;">
        """
        
        if predictions:
            # High confidence
            if "high_confidence" in predictions:
                html += "<h2 style='color: #4CAF50;'>✅ 確実性の高い3連単 (5レース)</h2>"
                html += "<table style='width: 100%; border-collapse: collapse;'>"
                for i, pred in enumerate(predictions["high_confidence"][:5], 1):
                    race_num = pred.get('race_number', i)
                    prediction = pred.get('prediction', [])
                    confidence = pred.get('confidence', 0)
                    odds = pred.get('estimated_odds', 0)
                    pred_str = " → ".join(str(p) for p in prediction[:3])
                    html += f"<tr style='border-bottom: 1px solid #ddd;'>"
                    html += f"<td style='padding: 10px;'><strong>{i}. レース{race_num}</strong></td>"
                    html += f"<td style='padding: 10px;'>{pred_str}</td>"
                    html += f"<td style='padding: 10px; text-align: right;'>"
                    html += f"信頼度: {confidence:.1%}<br>推定倍率: {odds:.1f}倍"
                    html += f"</td></tr>"
                html += "</table>"
                html += "<br>"
            
            # High odds
            if "high_odds" in predictions:
                html += "<h2 style='color: #2196F3;'>🎯 穴確率が高い3連単 (5レース)</h2>"
                html += "<table style='width: 100%; border-collapse: collapse;'>"
                for i, pred in enumerate(predictions["high_odds"][:5], 1):
                    race_num = pred.get('race_number', i)
                    prediction = pred.get('prediction', [])
                    odds = pred.get('estimated_odds', 0)
                    pred_str = " → ".join(str(p) for p in prediction[:3])
                    html += f"<tr style='border-bottom: 1px solid #ddd;'>"
                    html += f"<td style='padding: 10px;'><strong>{i}. レース{race_num}</strong></td>"
                    html += f"<td style='padding: 10px;'>{pred_str}</td>"
                    html += f"<td style='padding: 10px; text-align: right;'>"
                    html += f"推定倍率: {odds:.1f}倍"
                    html += f"</td></tr>"
                html += "</table>"
        
        html += """
                    <hr style="border: none; border-top: 1px solid #ddd; margin-top: 30px;">
                    <p style="color: #f44336; font-weight: bold;">⚠️ 重要なお知らせ</p>
                    <p style="color: #666; font-size: 12px;">
                        このソフトウェアは参考情報です。実際の購入判断は自己責任で行ってください。
                    </p>
                </div>
            </body>
        </html>
        """
        
        return html
