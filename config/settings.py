# config/settings.py
"""
Settings файл - здесь живут все настройки приложения.

Логика: когда приложение запускается, оно читает .env файл
и создает объект 'config' со всеми необходимыми значениями.

Если какое-то значение из .env потеряется или будет неправильного типа,
Pydantic сразу выдаст ошибку и подскажет что не так.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional

class Settings(BaseSettings):
    """
    Основной класс настроек.
    
    BaseSettings = специальный класс Pydantic который:
    1. Автоматически читает .env файл
    2. Валидирует типы (BOT_TOKEN должен быть str, API_PORT должен быть int)
    3. Выдает ошибку если обязательное поле пусто
    """
    
    # ==========================================
    # TELEGRAM BOT
    # ==========================================
    bot_token: str = ""
    bot_username: str = "changcafe_bot"
    operator_telegram_id: Optional[int] = None
    
    # ==========================================
    # DATABASE
    # ==========================================
    database_url: str = ""
    
    # ==========================================
    # REDIS
    # ==========================================
    redis_url: str = "redis://localhost:6379/0"
    
    # ==========================================
    # API
    # ==========================================
    api_host: str = "0.0.0.0"
    api_port: int = 5000
    api_webhook_secret: str = "default_secret"
    
    # ==========================================
    # WEBHOOK
    # ==========================================
    tilda_webhook_url: str = ""
    webhook_signing_secret: str = "default_webhook_secret"
    
    # ==========================================
    # ENVIRONMENT
    # ==========================================
    environment: Literal["development", "production"] = "development"
    debug: bool = True
    
    # Конфигурация Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False
    )
    
    @property
    def async_database_url(self) -> str:
        """Convert standard PostgreSQL URL to asyncpg format"""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=disable" in url:
            url = url.replace("?sslmode=disable", "")
        return url
    
    @property
    def webhook_url(self) -> str:
        """Generate the webhook URL"""
        return self.tilda_webhook_url or f"http://{self.api_host}:{self.api_port}/api/webhook/tilda"

config = Settings()
