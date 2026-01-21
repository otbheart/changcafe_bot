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
"""

from redis.asyncio.client import Redis
from aiogram.fsm.storage.redis import RedisStorage

from config.settings import config

# ==========================================
# ПОДКЛЮЧАЕМСЯ К REDIS
# ==========================================

# Создаём асинхронное соединение с Redis
redis = Redis.from_url(
    config.redis_url,  # Берём URL из .env (обычно redis://localhost:6379)
    encoding="utf-8",
    decode_responses=True
)

# ==========================================
# СОЗДАЁМ STORAGE ДЛЯ AIOGRAM
# ==========================================

# RedisStorage = хранилище состояний в Redis для aiogram FSM
# FSM = Finite State Machine (конечный автомат)
redis_storage = RedisStorage(redis=redis)

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
