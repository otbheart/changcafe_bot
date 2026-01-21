# app/bot/keyboards/client.py
"""
Клавиатуры для клиентов.

Есть два типа кнопок:
1. ReplyKeyboardMarkup — обычные кнопки снизу экрана
2. InlineKeyboardMarkup — кнопки прямо в сообщении
"""

from aiogram.types import (
    InlineKeyboardMarkup,      
    # Кнопки прямо в сообщении
    InlineKeyboardButton,      
    # Одна inline-кнопка
    ReplyKeyboardMarkup,       
    # Обычные кнопки снизу экрана
    KeyboardButton             
    # Одна обычная кнопка
)


def phone_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура для подтверждения номера телефона.
    
    Показывает кнопку "📱 Подтвердить номер телефона"
    с опцией request_contact=True (запрашивает у пользователя номер)
    
    Когда пользователь нажимает эту кнопку, Telegram отправляет его номер.
    
    Вывод:
        ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="📱 Подтвердить номер телефона", request_contact=True)]
        ])
    """
    
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="📱 Подтвердить номер телефона",
                request_contact=True  
                # Запросить номер телефона
            )
        ]],
        resize_keyboard=True,         
        # Кнопка займет всю ширину экрана
        one_time_keyboard=True        
        # Клавиатура скроется после нажатия
    )


def order_decision_keyboard() -> InlineKeyboardMarkup:
    """
    Inline-клавиатура для подтверждения/отмены заказа.
    
    Показывает две кнопки:
    - "✅ Оплатить" (callback_data="order_confirm")
    - "❌ Отменить" (callback_data="order_cancel")
    
    Когда пользователь нажимает кнопку, боту приходит callback_query
    с data = "order_confirm" или "order_cancel"
    """
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Оплатить",
                callback_data="order_confirm"
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="order_cancel"
            )
        ]
    ])

