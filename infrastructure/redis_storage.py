# infrastructure/redis_storage.py
"""
🔴 REDIS STORAGE

Redis хранит состояния пользователей (FSM).
Когда пользователь говорит /start, /order и т.д.
Redis запоминает в каком состоянии он находится.

Пример:
- Пользователь нажал /start → состояние = "main_menu"
- Затем /order → состояние = "choosing_product"
- И т.д.

Без Redis состояния теряются при перезагрузке бота.

Note: On Replit, Redis may not be available. In that case,
we fall back to memory storage.
"""

import os
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import config

# ==========================================
# SETUP STORAGE (Redis if available, else Memory)
# ==========================================

redis = None
redis_storage = None

try:
    from redis.asyncio.client import Redis
    from aiogram.fsm.storage.redis import RedisStorage
    
    redis = Redis.from_url(
        config.redis_url,
        encoding="utf-8",
        decode_responses=True
    )
    redis_storage = RedisStorage(redis=redis)
except Exception as e:
    print(f"⚠️ Redis not available, using MemoryStorage: {e}")
    redis_storage = MemoryStorage()

# ==========================================
# ФУНКЦИЯ: проверить соединение
# ==========================================

async def check_redis_connection():
    """
    Проверяет что Redis живой и отвечает.
    Вызывается при старте приложения для диагностики.
    
    Пример использования:
    try:
        await check_redis_connection()
        print("✅ Redis работает!")
    except Exception as e:
        print(f"❌ Redis не работает: {e}")
    """
    
    if redis is None:
        return False
    
    try:
        await redis.ping()
        return True
    except Exception as e:
        print(f"❌ Redis connection error: {e}")
        return False

# ==========================================
# ЭКСПОРТ
# ==========================================

__all__ = [
    "redis",
    "redis_storage",
    "check_redis_connection",
]
