# app/bot/middlewares/logging.py
"""
Middleware для логирования всех событий.
"""

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Any, Awaitable
import structlog

logger = structlog.get_logger()

class LoggingMiddleware(BaseMiddleware):
    """Middleware который логирует все события."""
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            logger.info(
                "message_received",
                user_id=event.from_user.id,
                username=event.from_user.username,
                text=event.text[:50] if event.text else None
            )
        elif isinstance(event, CallbackQuery):
            logger.info(
                "callback_received",
                user_id=event.from_user.id,
                callback_data=event.data
            )
        
        return await handler(event, data)
