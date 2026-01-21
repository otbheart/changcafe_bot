# app/bot/middlewares/database.py
"""
Middleware для подачи БД сессии в каждый обработчик.

Middleware выполняется ДО обработчика для всех сообщений/callback'ов.

Логика:
1. Создаем сессию
2. Передаем её обработчику
3. После обработчика закрываем сессию
"""

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from infrastructure.database.base import async_session_maker
from typing import Callable, Any, Awaitable

class DatabaseMiddleware(BaseMiddleware):
    """Middleware который подает AsyncSession в контекст."""
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any]
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)
