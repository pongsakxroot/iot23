"""
Notification service for LINE Notify and Telegram
"""
import requests
from app.config import settings
from app.models import Order
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Send notifications via LINE Notify and/or Telegram"""
    
    def __init__(self):
        self.line_enabled = settings.line_notify_enabled
        self.line_token = settings.line_notify_token
        self.telegram_enabled = settings.telegram_enabled
        self.telegram_bot_token = settings.telegram_bot_token
        self.telegram_chat_id = settings.telegram_chat_id
    
    def send_payment_notification(self, order: Order) -> dict:
        """
        Send payment notification to configured channels
        
        Args:
            order: The paid order
        
        Returns:
            Dict with status of each channel
        """
        message = self._format_payment_message(order)
        
        results = {
            "line": None,
            "telegram": None
        }
        
        if self.line_enabled and self.line_token:
            results["line"] = self._send_line_notify(message)
        
        if self.telegram_enabled and self.telegram_bot_token and self.telegram_chat_id:
            results["telegram"] = self._send_telegram(message)
        
        return results
    
    def _format_payment_message(self, order: Order) -> str:
        """Format payment notification message"""
        paid_at = order.paid_at.strftime("%Y-%m-%d %H:%M:%S") if order.paid_at else "N/A"
        
        message = f"""
💰 ชำระเงินสำเร็จ / Payment Received

รหัสออเดอร์ / Order ID: {order.id}
จำนวนเงิน / Amount: {order.expected_amount:.2f} บาท
ยอดหลัก / Base Amount: {order.base_amount:.2f} บาท
เวลาชำระ / Paid At: {paid_at}
"""
        
        if order.customer_ref:
            message += f"อ้างอิง / Reference: {order.customer_ref}\n"
        
        return message.strip()
    
    def _send_line_notify(self, message: str) -> bool:
        """
        Send notification via LINE Notify
        
        Args:
            message: Message to send
        
        Returns:
            True if successful, False otherwise
        """
        try:
            url = "https://notify-api.line.me/api/notify"
            headers = {
                "Authorization": f"Bearer {self.line_token}"
            }
            data = {
                "message": message
            }
            
            response = requests.post(url, headers=headers, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("LINE Notify sent successfully")
                return True
            else:
                logger.error(f"LINE Notify failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"LINE Notify error: {e}")
            return False
    
    def _send_telegram(self, message: str) -> bool:
        """
        Send notification via Telegram
        
        Args:
            message: Message to send
        
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully")
                return True
            else:
                logger.error(f"Telegram failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False


# Singleton instance
notifier = NotificationService()
