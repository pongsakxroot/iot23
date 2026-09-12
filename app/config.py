"""
Configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./payment_verification.db"
    
    # API
    api_key: str = "change-me-in-production"
    webhook_secret: str = "change-me-in-production"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Order Configuration
    order_ttl_minutes: int = 10
    base_amount_min: float = 1.00
    base_amount_max: float = 999999.99
    
    # MQTT
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_topic_trigger: str = "device/payment/trigger"
    mqtt_client_id: str = "promptpay-backend"
    
    # LINE Notify
    line_notify_token: Optional[str] = None
    line_notify_enabled: bool = False
    
    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: bool = False
    
    # IMAP Worker
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    imap_email: str = ""
    imap_password: str = ""
    imap_poll_interval: int = 15
    imap_mailbox: str = "INBOX"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
