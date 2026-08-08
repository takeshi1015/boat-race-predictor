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
        mode: str = "today",
        hit_rate: float = 0.0,
    ) -> bool:
        """
        Send prediction email
        
        Args:
            recipients: List of recipient emails
            subject: Email subject
            predictions: Prediction data (dict with "high_confidence" and "high_odds" keys)
            mode: 'today' or 'tomorrow'
            hit_rate: 過去30日の的中率
            
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
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = ", ".join(recipients)
            
            # Create email body
            body = self._create_email_body(predictions, mode, hit_rate)
            html_body = self._create_html_body(predictions, mode, hit_rate)
            
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
    
    def _create_email_body(self, predictions: Optional[Dict[str, Any]], mode: str, hit_rate: float = 0.0) -> str:
        """
        Create plain text email body
        
        Args:
            predictions: Prediction data (dict with "high_confidence" and "high_odds" keys)
            mode: 'today' or 'tomorrow'
            hit_rate: 過去30日の的中率
            
        Returns:
            Plain text email body
        """
        label = "翌日" if mode == "tomorrow" else "当日"
        lines = []
        lines.append("=" * 60)
        lines.append(f"🚤 ボートレース予測 {label}の推奨")
        lines.append("=" * 60)
        lines.append(f"📅 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
        lines.append("")
        
        if predictions:
            # High confidence
            high_conf = predictions.get("high_confidence", [])
            if high_conf:
                lines.append("🎯 確実性の高い予想 TOP 5")
                lines.append("-" * 60)
                for i, pred in enumerate(high_conf[:5], 1):
                    place = pred.get("place") or pred.get("venue", "不明")
                    race_num = pred.get("race_number", i)
                    prediction = pred.get("predicted_order") or pred.get("prediction", [])
                    confidence = pred.get("confidence", 0)
                    odds = pred.get("estimated_odds", 0)
                    stars = "⭐" * round(confidence * 5)
                    pred_str = "-".join(str(p) for p in prediction[:3])
                    lines.append(
                        f"{i}. {place}競艇場 {race_num}レース | 推奨: {pred_str} | "
                        f"信頼度: {stars} {confidence:.2f}"
                    )
                lines.append("")
            
            # High odds (upset)
            high_odds = predictions.get("high_odds", [])
            if high_odds:
                lines.append("💰 穴狙い予想 TOP 5")
                lines.append("-" * 60)
                for i, pred in enumerate(high_odds[:5], 1):
                    place = pred.get("place") or pred.get("venue", "不明")
                    race_num = pred.get("race_number", i)
                    prediction = pred.get("predicted_order") or pred.get("prediction", [])
                    odds = pred.get("estimated_odds", 0)
                    upset = pred.get("upset_score", 0)
                    upset_stars = "⭐" * round(upset * 5)
                    pred_str = "-".join(str(p) for p in prediction[:3])
                    lines.append(
                        f"{i}. {place}競艇場 {race_num}レース | 推奨: {pred_str} | "
                        f"穴度: {upset_stars} | 推定倍率: {odds:.1f}倍"
                    )
                lines.append("")
        
        if hit_rate > 0:
            lines.append(f"📈 今月の成績: 的中率 {hit_rate:.1%} （過去30日平均）")
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("⚠️ このソフトウェアは参考情報です")
        lines.append("実際の購入判断は自己責任で行ってください")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _create_html_body(self, predictions: Optional[Dict[str, Any]], mode: str, hit_rate: float = 0.0) -> str:
        """
        Create HTML email body
        
        Args:
            predictions: Prediction data (dict with "high_confidence" and "high_odds" keys)
            mode: 'today' or 'tomorrow'
            hit_rate: 過去30日の的中率
            
        Returns:
            HTML email body
        """
        label = "翌日" if mode == "tomorrow" else "当日"
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px;">
                    <h1 style="text-align: center; color: #333;">🚤 ボートレース予測</h1>
                    <p style="text-align: center; color: #666;">{label}の推奨</p>
                    <p style="text-align: center; color: #999; font-size: 12px;">{datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>
                    <hr style="border: none; border-top: 1px solid #ddd;">
        """
        
        if predictions:
            # High confidence
            high_conf = predictions.get("high_confidence", [])
            if high_conf:
                html += "<h2 style='color: #4CAF50;'>🎯 確実性の高い予想 TOP 5</h2>"
                html += "<table style='width: 100%; border-collapse: collapse;'>"
                for i, pred in enumerate(high_conf[:5], 1):
                    place = pred.get("place") or pred.get("venue", "不明")
                    race_num = pred.get("race_number", i)
                    prediction = pred.get("predicted_order") or pred.get("prediction", [])
                    confidence = pred.get("confidence", 0)
                    odds = pred.get("estimated_odds", 0)
                    stars = "⭐" * round(confidence * 5)
                    pred_str = "-".join(str(p) for p in prediction[:3])
                    html += f"<tr style='border-bottom: 1px solid #ddd;'>"
                    html += f"<td style='padding: 10px;'><strong>{i}. {place}競艇場 {race_num}レース</strong></td>"
                    html += f"<td style='padding: 10px;'>推奨: {pred_str}</td>"
                    html += f"<td style='padding: 10px; text-align: right;'>"
                    html += f"信頼度: {stars} {confidence:.2f}<br>推定倍率: {odds:.1f}倍"
                    html += f"</td></tr>"
                html += "</table><br>"
            
            # High odds (upset)
            high_odds = predictions.get("high_odds", [])
            if high_odds:
                html += "<h2 style='color: #2196F3;'>💰 穴狙い予想 TOP 5</h2>"
                html += "<table style='width: 100%; border-collapse: collapse;'>"
                for i, pred in enumerate(high_odds[:5], 1):
                    place = pred.get("place") or pred.get("venue", "不明")
                    race_num = pred.get("race_number", i)
                    prediction = pred.get("predicted_order") or pred.get("prediction", [])
                    odds = pred.get("estimated_odds", 0)
                    upset = pred.get("upset_score", 0)
                    upset_stars = "⭐" * round(upset * 5)
                    pred_str = "-".join(str(p) for p in prediction[:3])
                    html += f"<tr style='border-bottom: 1px solid #ddd;'>"
                    html += f"<td style='padding: 10px;'><strong>{i}. {place}競艇場 {race_num}レース</strong></td>"
                    html += f"<td style='padding: 10px;'>推奨: {pred_str}</td>"
                    html += f"<td style='padding: 10px; text-align: right;'>"
                    html += f"穴度: {upset_stars}<br>推定倍率: {odds:.1f}倍"
                    html += f"</td></tr>"
                html += "</table>"
        
        if hit_rate > 0:
            html += f"<br><p style='color: #FF9800; font-weight: bold;'>"
            html += f"📈 今月の成績: 的中率 {hit_rate:.1%} （過去30日平均）</p>"
        
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
