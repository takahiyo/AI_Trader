"""
AI_Trader 異常通知モジュール

API接続断、メモリリーク、EA停止等を検知した際に
メールまたはLINE通知を送信する。
"""

import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class Notifier:
    """異常通知。"""

    def __init__(self, config):
        self.config = config
        self.email_enabled = config.get("monitoring.notification.email.enabled", False)
        self.line_enabled = config.get("monitoring.notification.line.enabled", False)

    def send_critical(self, message: str) -> None:
        """緊急通知（プロセス停止等）。"""
        full_msg = f"[CRITICAL] {datetime.now().isoformat()} {message}"
        logger.critical(full_msg)
        self._dispatch(f"AI_Trader 緊急: {message}", full_msg)

    def send_error(self, message: str) -> None:
        """エラー通知。"""
        full_msg = f"[ERROR] {datetime.now().isoformat()} {message}"
        logger.error(full_msg)
        self._dispatch(f"AI_Trader エラー: {message}", full_msg)

    def send_info(self, message: str) -> None:
        """情報通知。"""
        self._dispatch(f"AI_Trader: {message}", message)

    def _dispatch(self, subject: str, body: str) -> None:
        """全有効チャネルに通知を送信する。"""
        if self.email_enabled:
            self._send_email(subject, body)
        if self.line_enabled:
            self._send_line(body)

    def _send_email(self, subject: str, body: str) -> None:
        """メール送信。"""
        try:
            smtp_server = self.config.get("monitoring.notification.email.smtp_server", "")
            smtp_port = self.config.get("monitoring.notification.email.smtp_port", 587)
            sender = self.config.get("monitoring.notification.email.sender", "")
            password = self.config.get("monitoring.notification.email.password", "")
            recipients = self.config.get("monitoring.notification.email.recipients", [])

            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)

            logger.info(f"メール送信成功: {subject}")
        except Exception as e:
            logger.error(f"メール送信失敗: {e}")

    def _send_line(self, message: str) -> None:
        """LINE Notify送信。"""
        try:
            token = self.config.get("monitoring.notification.line.token", "")
            headers = {"Authorization": f"Bearer {token}"}
            data = {"message": message}
            resp = requests.post(
                "https://notify-api.line.me/api/notify",
                headers=headers,
                data=data,
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info("LINE通知成功")
            else:
                logger.error(f"LINE通知失敗: {resp.status_code}")
        except Exception as e:
            logger.error(f"LINE通知失敗: {e}")
