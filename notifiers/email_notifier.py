"""
メール通知機能
SMTP経由でメール通知を送信
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config
from utils.logger import setup_logger

logger = setup_logger(__name__)


class EmailNotifier:
    """メール通知クラス"""
    
    def __init__(self):
        self.config = Config()
        self.sender_email = self.config.EMAIL_ADDRESS
        self.sender_password = self.config.EMAIL_PASSWORD
        self.smtp_server = self.config.SMTP_SERVER
        self.smtp_port = self.config.SMTP_PORT
        self.recipients = self.config.EMAIL_RECIPIENTS.split(',')
    
    def send_predictions(self, predictions, title="予測結果"):
        """予測結果をメール送信"""
        try:
            if not self.config.USE_EMAIL:
                logger.info("メール通知は無効です")
                return
            
            subject = f"🚤 ボートレース予測: {title}"
            body = self._format_predictions_body(predictions, title)
            
            self._send_email(subject, body)
            logger.info("✅ 予測結果のメールを送信しました")
        except Exception as e:
            logger.error(f"予測メール送信エラー: {e}", exc_info=True)
    
    def send_alert(self, message):
        """アラートメッセージを送信"""
        try:
            if not self.config.USE_EMAIL:
                return
            
            subject = "⚠️ ボートレース予測: アラート"
            body = f"アラート通知\n\n{message}\n\n送信時刻: {self._get_timestamp()}"
            
            self._send_email(subject, body)
            logger.info("✅ アラートメールを送信しました")
        except Exception as e:
            logger.error(f"アラートメール送信エラー: {e}", exc_info=True)
    
    def _send_email(self, subject, body):
        """メール送信の実処理"""
        try:
            # メッセージを作成
            message = MIMEMultipart()
            message["From"] = self.sender_email
            message["To"] = ", ".join(self.recipients)
            message["Subject"] = subject
            
            # 本文を追加
            message.attach(MIMEText(body, "plain", "utf-8"))
            
            # SMTP接続してメール送信
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            logger.info(f"メール送信成功: {subject}")
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP認証エラー: メールアドレスまたはパスワードが不正です")
            raise
        except Exception as e:
            logger.error(f"メール送信エラー: {e}")
            raise
    
    def _format_predictions_body(self, predictions, title):
        """予測結果をメール本文にフォーマット"""
        body = f"ボートレース予測結果\n\n"
        body += f"【{title}】\n"
        body += f"送信時刻: {self._get_timestamp()}\n\n"
        body += "=" * 60 + "\n\n"
        
        for i, pred in enumerate(predictions, 1):
            body += f"【第{i}レース】\n"
            body += f"日付: {pred.get('date', 'N/A')}\n"
            body += f"予測結果: {pred.get('prediction', 'N/A')}\n"
            body += f"信頼度: {pred.get('confidence', 0):.1%}\n"
            body += "-" * 60 + "\n\n"
        
        body += "=" * 60 + "\n"
        body += "【注意事項】\n"
        body += "・この予測は参考情報です\n"
        body += "・投資判断は自己責任でお願いします\n"
        
        return body
    
    @staticmethod
    def _get_timestamp():
        """タイムスタンプを取得"""
        from datetime import datetime
        return datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
