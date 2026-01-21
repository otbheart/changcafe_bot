# config/settings.py
"""
Settings файл - здесь живут все настройки приложения.

Логика: когда приложение запускается, оно читает .env файл
и создает объект 'config' со всеми необходимыми значениями.

Если какое-то значение из .env потеряется или будет неправильного типа,
Pydantic сразу выдаст ошибку и подскажет что не так.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

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
    bot_token: str
    bot_username: str
    operator_telegram_id: int
    
    # ==========================================
    # DATABASE
    # ==========================================
    database_url: str
    
    # ==========================================
    # REDIS
    # ==========================================
    redis_url: str
    
    # ==========================================
    # API
    # ==========================================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_webhook_secret: str
    
    # ==========================================
    # WEBHOOK
    # ==========================================
    tilda_webhook_url: str
    webhook_signing_secret: str
    
    # ==========================================
    # ENVIRONMENT
    # ==========================================
    environment: Literal["development", "production"] = "production"
    debug: bool = False
    
    # Конфигурация Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",  # Читаем из .env файла
        extra="ignore",  # Игнорируем неизвестные переменные
        case_sensitive=False  # BOT_TOKEN == bot_token
    )

# Создаем глобальный объект config
# Используется везде в приложении: from config.settings import config
config = Settings()
