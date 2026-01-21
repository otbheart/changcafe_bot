# app/bot/keyboards/operator.py
"""
Клавиатуры для оператора.
Более сложные, потому что у оператора больше действий.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from infrastructure.database.models import User


def order_notification_keyboard(order_id: int, user: User = None) -> InlineKeyboardMarkup:
    """
    Клавиатура при уведомлении оператора о новом заказе.
    
    Содержит:
    - Кнопка "Написать в личку" (если есть username)
    - Кнопка "Написать через бота" (если нет username)
    - Кнопка "Позвонить" (всегда)
    - Кнопка "Взять в работу" (всегда)
    - Кнопка "В отказ" (всегда)
    """
    buttons = []
    
    # Если у клиента есть username, показываем кнопку "Написать в личку"
    if user and user.username:
        buttons.append([
            InlineKeyboardButton(
                text="💬 Написать в личку",
                url=f"tg://resolve?domain={user.username}"
                
                # tg://resolve = протокол для открытия профиля в Telegram
            )
        ])
    
    # Если нет username, показываем "Написать через бота"
    elif user:
        buttons.append([
            InlineKeyboardButton(
                text="✉️ Написать через бота",
                callback_data=f"chat_start:{order_id}"
            )
        ])
    
    # Кнопка для звонка
    buttons.append([
        InlineKeyboardButton(
            text="📞 Позвонить",
            url=f"tel:{user.phone}" if user and user.phone else "https://t.me"
            
            # tel: = протокол для звонка
        )
    ])
    
    # Кнопки "Взять в работу" и "В отказ"
    buttons.append([
        InlineKeyboardButton(
            text="✅ Взять в работу",
            callback_data=f"take_order:{order_id}"
        ),
        InlineKeyboardButton(
            text="❌ В отказ",
            callback_data=f"reject_order:{order_id}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def operator_order_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для управления заказом (после того как оператор его взял).
    
    Содержит кнопки:
    - Отправить ссылку на оплату
    - Подтвердить оплату
    - Отправить трекинг
    - Завершить заказ
    """
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 Отправить ссылку на оплату",
                callback_data=f"send_payment_link:{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Подтвердить оплату",
                callback_data=f"confirm_payment:{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🚚 Отправить трекинг",
                callback_data=f"send_tracking:{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Завершить заказ",
                callback_data=f"complete_order:{order_id}"
            )
        ]
    ])

