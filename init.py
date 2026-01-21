# changcafe_bot/__init__.py или в корне проекта
"""
ChangCafe Bot - Telegram бот для заказов.

Структура:
- app/ - основное приложение (бот + API)
  - bot/ - Telegram бот (handlers, middlewares, states)
  - api/ - FastAPI endpoints (webhooks от Tilda)
- config/ - конфигурация (settings.py)
- infrastructure/ - инфраструктура (БД, Redis, логирование)
"""

__version__ = "1.0.0"
__author__ = "OTBheart"
__description__ = "Telegram bot для заказов Chang Cafe из Tilda"
