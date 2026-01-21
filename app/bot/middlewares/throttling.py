# app/bot/middlewares/throttling.py
"""
Middleware для защиты от спама (throttling).

Ограничивает количество запросов от одного пользователя за определённый период.
Например: максимум 10 сообщений в 5 секунд.
"""

from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta

from aiogram import BaseMiddleware, types

from infrastructure.logger import logger

class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware для защиты от спама.
    
    Отслеживает сколько сообщений приходит от каждого пользователя
    и блокирует если они спамят.
    """
    
    def __init__(self):
        """Инициализация."""
        # Словарь где ключ - user_id, значение - список времён сообщений
        self.user_requests = {}
        # Максимум 10 сообщений в 5 секунд
        self.max_requests = 10
        self.time_window = 5
    
    async def __call__(
        self,
        handler: Callable[[types.Update, Dict[str, Any]], Awaitable[Any]],
        event: types.Update,
        data: Dict[str, Any],
    ) -> Any:
        """
        Проверяем спам и передаём в обработчик.
        """
        
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
            
            # Отправляем предупреждение только если это сообщение (не callback)
            if event.message:
                await event.message.answer(
                    "⏱️ Ты пишешь слишком часто. Подождй немного!"
                )
            
            return  # Не передаём дальше
        
        # Добавляем текущий запрос в список
        self.user_requests[user_id].append(now)
        
        # Передаём в обработчик
        return await handler(event, data)
