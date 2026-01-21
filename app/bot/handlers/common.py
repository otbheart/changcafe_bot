# app/bot/handlers/common.py
"""
Обработчики которые работают для всех пользователей.

Здесь:
- Обработка контакта (номер телефона)
- Обработка ошибок
- Fallback сообщения
"""

from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import User
from infrastructure.logger import logger

router = Router()

# ==========================================
# КОМАНДА: /help
# ==========================================

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Справка по командам."""
    
    help_text = """
🤖 Доступные команды:

/start - Главное меню
/help - Эта справка
/status - Статус текущего заказа
/cancel - Отмена операции

Если у тебя есть вопросы - пиши оператору кнопкой "💬 Написать оператору"
    """
    
    await message.answer(help_text)
    logger.info("help_command", user_id=message.from_user.id)

# ==========================================
# ОБРАБОТКА КОНТАКТА (номер телефона)
# ==========================================

@router.message(F.contact)
async def handle_contact(message: types.Message, session: AsyncSession):
    """
    Обработка когда пользователь отправил свой контакт.
    
    Это когда клиент нажимает на кнопку "📱 Поделиться номером"
    """
    
    phone = message.contact.phone_number
    user_id = message.from_user.id
    
    # Обновляем номер в БД
    from sqlalchemy import select, update
    
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalars().first()
    
    if user:
        stmt = update(User).where(User.user_id == user_id).values(phone=phone)
        await session.execute(stmt)
        await session.commit()
        
        await message.answer(f"✅ Спасибо! Твой номер сохранен: {phone}")
        logger.info("phone_saved", user_id=user_id, phone=phone)
    else:
        await message.answer("❌ Ошибка: пользователь не найден")
        logger.error("user_not_found", user_id=user_id)

# ==========================================
# FALLBACK (ловушка для неизвестных команд)
# ==========================================

@router.message()
async def echo_or_unknown(message: types.Message):
    """
    Если ничего не сработало - этот обработчик.
    
    Это последняя ловушка для непонятных сообщений.
    """
    
    await message.answer(
        "🤔 Не понимаю что ты имеешь в виду.\n\n"
        "Выбери действие из меню или напиши /help"
    )
    
    logger.warning("unknown_message", user_id=message.from_user.id, text=message.text)
