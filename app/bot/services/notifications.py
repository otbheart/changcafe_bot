# app/bot/services/notifications.py
"""
Сервис для отправки уведомлений оператору.
"""

from aiogram import Bot
from infrastructure.database.models import Order
from app.bot.keyboards.operator import order_notification_keyboard
from app.bot.utils.text import order_card_text
from config.settings import config
import structlog

logger = structlog.get_logger()
bot = Bot(token=config.bot_token)

async def notify_operator_new_order(order: Order, deep_link: str):
    """Отправляет оператору уведомление о новом заказе."""
    try:
        order_text = order_card_text(order, for_operator=True)
        
        text = (
            f"{order_text}\n\n"
            f"🔗 Deep Link: {deep_link}\n\n"
            f"📊 Статус: Ожидает подтверждения в Telegram"
        )
        
        await bot.send_message(
            chat_id=config.operator_telegram_id,
            text=text,
            reply_markup=order_notification_keyboard(order.id)
        )
        
        logger.info("operator_notified", order_id=order.id)
    
    except Exception as e:
        logger.error("notification_error", error=str(e))
