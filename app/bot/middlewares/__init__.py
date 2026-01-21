# app/bot/middlewares/__init__.py
"""
🔄 MIDDLEWARE (перехватчики)

Middleware срабатывают для КАЖДОГО сообщения.
Используются для:
- Логирования
- Подключения БД к контексту
- Защиты от спама
- И т.д.
"""

from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta

from aiogram import BaseMiddleware, types
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.logger import logger
from infrastructure.database import async_session_maker

# ==========================================
# LOGGING MIDDLEWARE (логирование)
# ==========================================

class LoggingMiddleware(BaseMiddleware):
    """
    Логирует каждое сообщение/событие.
    
    Помогает отладке и мониторингу.
    """
    
    async def __call__(
        self,
        handler: Callable[[types.Message, Dict[str, Any]], Awaitable[Any]],
        event: types.Message,
        data: Dict[str, Any],
    ) -> Any:
        """
        Перехватываем сообщение, логируем его, затем передаём обработчику.
        """
        
        # Логируем информацию о сообщении
        user_id = event.from_user.id
        username = event.from_user.username or "unknown"
        text = event.text or "[media]"
        
        logger.info(
            "message_received",
            user_id=user_id,
            username=username,
            text=text[:50]  # Первые 50 символов
        )
        
        # Передаём дальше обработчику
        return await handler(event, data)

# ==========================================
# DATABASE MIDDLEWARE (подключение БД)
# ==========================================

class DatabaseMiddleware(BaseMiddleware):
    """
    Подключает БД сессию к каждому запросу.
    
    Пример использования в обработчике:
    
    async def my_handler(message: types.Message, session: AsyncSession):
        # session уже готова!
        user = await session.get(User, user_id)
    """
    
    async def __call__(
        self,
        handler: Callable[[types.Update, Dict[str, Any]], Awaitable[Any]],
        event: types.Update,
        data: Dict[str, Any],
    ) -> Any:
        """
        Создаём новую сессию БД и добавляем в контекст.
        """
        
        # Создаём новую сессию
        async with async_session_maker() as session:
            # Добавляем сессию в контекст (будет доступна в обработчике)
            data["session"] = session
            
            try:
                # Передаём дальше
                return await handler(event, data)
            except Exception as e:
                # Если ошибка - откатываем транзакцию
                await session.rollback()
                logger.error("database_error", error=str(e))
                raise
            finally:
                # Закрываем сессию
                await session.close()

# ==========================================
# THROTTLING MIDDLEWARE (защита от спама)
# ==========================================

class ThrottlingMiddleware(BaseMiddleware):
    """
    Защита от спама.
    
    Если пользователь пишет слишком часто - блокируем его на время.
    """
    
    def __init__(self):
        """Инициализация."""
        self.user_requests = {}  # {user_id: [time1, time2, ...]}
        self.max_requests = 10   # Максимум 10 сообщений
        self.time_window = 5     # За 5 секунд
    
    async def __call__(
        self,
        handler: Callable[[types.Update, Dict[str, Any]], Awaitable[Any]],
        event: types.Update,
        data: Dict[str, Any],
    ) -> Any:
        """Проверяем спам и передаём в обработчик."""
        
        # Получаем user_id
        if event.message:
            user_id = event.message.from_user.id
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
        else:
            return await handler(event, data)
        
        # Инициализируем список если первый раз
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        now = datetime.now()
        
        # Удаляем старые запросы (старше time_window секунд)
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if now - req_time < timedelta(seconds=self.time_window)
        ]
        
        # Проверяем не превышен ли лимит
        if len(self.user_requests[user_id]) >= self.max_requests:
            logger.warning("throttling_limit_exceeded", user_id=user_id)
            
            if event.message:
                await event.message.answer(
                    "⏱️ Ты пишешь слишком часто. Подожди немного!"
                )
            
            return
        
        # Добавляем текущий запрос в список
        self.user_requests[user_id].append(now)
        
        # Передаём дальше
        return await handler(event, data)

# ==========================================
# ЭКСПОРТ
# ==========================================

__all__ = [
    "LoggingMiddleware",
    "DatabaseMiddleware",
    "ThrottlingMiddleware",
]
