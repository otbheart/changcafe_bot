# infrastructure/logger.py
"""
📝 ЛОГИРОВАНИЕ

Система для красивого вывода логов в консоль.
Использует structlog для структурированного логирования.
"""

import logging
import sys
from typing import Any

import structlog

# ==========================================
# ИНИЦИАЛИЗАЦИЯ STRUCTLOG
# ==========================================

def setup_logging():
    """
    Инициализирует логирование.
    
    Вызывается один раз при старте приложения.
    """
    
    # Конфигурируем structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()  # Выводит как JSON
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Конфигурируем стандартный logging
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s: %(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

# ==========================================
# ПОЛУЧЕНИЕ ЛОГГЕРА
# ==========================================

logger = structlog.get_logger()

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def log_info(message: str, **kwargs):
    """Логируем информацию."""
    logger.info(message, **kwargs)

def log_error(message: str, **kwargs):
    """Логируем ошибку."""
    logger.error(message, **kwargs)

def log_warning(message: str, **kwargs):
    """Логируем предупреждение."""
    logger.warning(message, **kwargs)

def log_debug(message: str, **kwargs):
    """Логируем отладку."""
    logger.debug(message, **kwargs)
