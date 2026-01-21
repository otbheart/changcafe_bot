# app/bot/handlers/client.py
"""
Обработчики для клиента (заказчика).

Здесь живут команды которые доступны КЛИЕНТУ:
- Запуск с deep link (/start order_ID)
- Просмотр своего заказа
- Подтверждение номера телефона
- Отправка сообщения оператору
- Получение уведомлений о статусе

ШАГ 4: HANDLERS КЛИЕНТА
"""

from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from infrastructure.database.base import async_session_maker
from infrastructure.database.repositories import (
    OrderRepository,
    UserRepository,
    MessageRepository
)
from infrastructure.database.models import OrderStatus

import structlog

logger = structlog.get_logger()

router = Router()

bot = Bot(token=config.bot_token)


# ==========================================
# 📝 STATE MACHINE (для ввода данных)
# ==========================================

class ClientStates(StatesGroup):
    """Состояния клиента"""
    
    waiting_phone_confirmation = State()  # Ожидаем подтверждения номера
    waiting_message_to_operator = State()  # Ожидаем сообщение оператору


# ==========================================
# КОМАНДА: /start [order_external_id]
# ==========================================

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Запуск бота с deep link.
    
    Варианты:
    1. /start (без параметров) - просто запуск
    2. /start order_12345 - запуск с привязкой к заказу
    
    ✅ ПРАВИЛЬНО:
    - Парсим аргумент order_ID
    - Ищем заказ в БД
    - Показываем детали заказа
    """
    
    try:
        # Достаём аргумент из команды (/start order_123)
        args = message.text.split()
        order_external_id = args if len(args) > 1 else None
        
        logger.info(
            "client_start",
            user_id=message.from_user.id,
            order_external_id=order_external_id
        )
        
        # Если есть order_id - показываем заказ
        if order_external_id:
            async with async_session_maker() as session:
                order_repo = OrderRepository(session)
                user_repo = UserRepository(session)
                
                # Ищем заказ по external_id
                order = await order_repo.get_by_external_id(order_external_id)
                
                if not order:
                    await message.answer(
                        "❌ Заказ не найден.\n\n"
                        "Проверьте ссылку или обратитесь в поддержку."
                    )
                    return
                
                # ← ✅ Создаём или обновляем пользователя
                user = await user_repo.get_or_create(
                    user_id=message.from_user.id,
                    username=message.from_user.username or "unknown",
                    first_name=message.from_user.first_name or "",
                    phone=None  # Пока не подтверждён
                )
                
                # ← ✅ Связываем пользователя с заказом
                if not order.user_id:
                    await order_repo.assign_user_to_order(
                        order_id=order.id,
                        user_id=user.id
                    )
                
                # Показываем заказ
                await show_order_to_client(message, order, state)
                return
        
        # Если без параметров - показываем главное меню
        text = (
            "👋 <b>Добро пожаловать в Chang Cafe!</b>\n\n"
            "Здесь вы можете:\n"
            "• 📦 Отследить свой заказ\n"
            "• 💬 Связаться с оператором\n\n"
            "Если у вас есть ссылка на заказ - нажмите на неё 🎯"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="📦 У меня есть заказ",
                    callback_data="client_i_have_order"
                )],
                [InlineKeyboardButton(
                    text="❓ Помощь",
                    callback_data="client_help"
                )],
            ]
        )
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    except Exception as e:
        logger.error("cmd_start_error", error=str(e))
        await message.answer(f"❌ Ошибка: {str(e)}")


# ==========================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: Показать заказ
# ==========================================

async def show_order_to_client(
    message: types.Message,
    order,
    state: FSMContext
):
    """
    Показывает клиенту информацию о его заказе.
    
    ← ✅ Вся информация в одном сообщении
    """
    
    text = f"<b>📦 Ваш заказ {order.external_order_id}</b>\n\n"
    
    text += f"<b>📍 Адрес доставки:</b>\n{order.address}\n\n"
    
    text += f"<b>💰 Сумма:</b>\n"
    text += f"  Товары: {order.base_amount}₽\n"
    if order.delivery_cost:
        text += f"  Доставка: {order.delivery_cost}₽\n"
    if order.total_amount:
        text += f"  <b>Итого: {order.total_amount}₽</b>\n"
    
    text += f"\n<b>📊 Статус:</b>\n"
    
    # Показываем статус красивенько
    status_emoji = {
        OrderStatus.NEW: "🆕",
        OrderStatus.AWAITING_CONFIRMATION: "⏳",
        OrderStatus.WAITING_OPERATOR: "⏳",
        OrderStatus.AWAITING_PAYMENT: "💳",
        OrderStatus.PAID: "✅",
        OrderStatus.IN_DELIVERY: "🚚",
        OrderStatus.COMPLETED: "✅",
        OrderStatus.CANCELLED: "❌",
    }
    
    emoji = status_emoji.get(order.status, "❓")
    text += f"  {emoji} <b>{order.status.value}</b>\n"
    
    text += f"\n<b>📝 Товары:</b>\n"
    if order.items:
        for item in order.items:
            text += f"  • {item['title']} x{item['quantity']} = {item['price']*item['quantity']}₽\n"
    
    # Кнопки действий
    buttons = []
    
    # Если заказ ждет подтверждения - кнопка подтверждения
    if order.status == OrderStatus.AWAITING_CONFIRMATION:
        buttons.append([InlineKeyboardButton(
            text="✅ Подтвердить заказ",
            callback_data=f"client_confirm_order:{order.id}"
        )])
    
    # Если нужно ввести номер телефона
    if not order.user or not order.user.phone:
        buttons.append([InlineKeyboardButton(
            text="📞 Подтвердить номер",
            callback_data=f"client_confirm_phone:{order.id}"
        )])
    
    # Если оплачен или в доставке - кнопка с ссылкой на трекинг
    if order.status == OrderStatus.IN_DELIVERY and order.tracking_link:
        buttons.append([InlineKeyboardButton(
            text="🔗 Отследить доставку",
            url=order.tracking_link
        )])
    
    # Кнопка написать оператору
    buttons.append([InlineKeyboardButton(
        text="💬 Написать оператору",
        callback_data=f"client_message_operator:{order.id}"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Сохраняем order_id в state для дальнейших действий
    await state.update_data(order_id=order.id, external_order_id=order.external_order_id)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    logger.info(
        "order_shown_to_client",
        user_id=message.from_user.id,
        order_id=order.id,
        status=order.status.value
    )


# ==========================================
# ПОДТВЕРЖДЕНИЕ НОМЕРА ТЕЛЕФОНА
# ==========================================

@router.callback_query(F.data.startswith("client_confirm_phone:"))
async def confirm_phone_request(query: types.CallbackQuery, state: FSMContext):
    """
    Клиент нажимает кнопку "Подтвердить номер".
    Запрашиваем номер телефона.
    """
    
    try:
        order_id = int(query.data.split(":"))
        
        await state.update_data(order_id=order_id)
        await state.set_state(ClientStates.waiting_phone_confirmation)
        
        await query.message.edit_text(
            "📞 <b>Подтвердите ваш номер телефона</b>\n\n"
            "Отправьте номер в формате:\n"
            "<code>+7 (999) 123-45-67</code>\n\n"
            "или используйте кнопку ниже 👇",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📱 Отправить номер из профиля",
                        request_contact=True
                    )],
                    [InlineKeyboardButton(
                        text="◀️ Отмена",
                        callback_data=f"client_back_to_order:{order_id}"
                    )],
                ]
            ),
            parse_mode="HTML"
        )
        
        logger.info(
            "phone_confirmation_requested",
            user_id=query.from_user.id,
            order_id=order_id
        )
    
    except Exception as e:
        logger.error("confirm_phone_request_error", error=str(e))
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.message(ClientStates.waiting_phone_confirmation)
async def receive_phone_confirmation(message: types.Message, state: FSMContext):
    """
    Получаем номер телефона от клиента (текст или контакт).
    """
    
    try:
        data = await state.get_data()
        order_id = data.get("order_id")
        
        # Обрабатываем контакт (request_contact)
        if message.contact:
            phone = message.contact.phone_number
        else:
            # Обрабатываем текст
            phone = message.text
        
        # Валидируем номер (простая проверка)
        phone_clean = ''.join(c for c in phone if c.isdigit())
        if len(phone_clean) < 10:
            await message.answer(
                "❌ Номер слишком короткий. Попробуйте ещё раз."
            )
            return
        
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            user_repo = UserRepository(session)
            
            # Обновляем номер телефона пользователя
            user = await user_repo.get_by_id(message.from_user.id)
            if user:
                await user_repo.update(
                    user_id=message.from_user.id,
                    phone=phone
                )
            
            # Обновляем номер в заказе
            order = await order_repo.get_by_id(order_id)
            if order:
                await order_repo.update(
                    order_id=order_id,
                    tilda_phone=phone
                )
            
            # Показываем заказ заново
            order = await order_repo.get_by_id_with_relations(order_id)
            await message.answer("✅ Номер сохранён!")
            await show_order_to_client(message, order, state)
            
            logger.info(
                "phone_confirmed",
                user_id=message.from_user.id,
                order_id=order_id,
                phone=phone
            )
        
        await state.clear()
    
    except Exception as e:
        logger.error("receive_phone_confirmation_error", error=str(e))
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


# ==========================================
# ОТПРАВКА СООБЩЕНИЯ ОПЕРАТОРУ
# ==========================================

@router.callback_query(F.data.startswith("client_message_operator:"))
async def message_operator_request(query: types.CallbackQuery, state: FSMContext):
    """
    Клиент нажимает "Написать оператору".
    Запрашиваем сообщение.
    """
    
    try:
        order_id = int(query.data.split(":"))
        
        await state.update_data(order_id=order_id)
        await state.set_state(ClientStates.waiting_message_to_operator)
        
        await query.message.edit_text(
            "💬 <b>Напишите ваше сообщение оператору</b>\n\n"
            "Оператор ответит вам в этом чате 👇",
            parse_mode="HTML"
        )
        
        logger.info(
            "message_to_operator_requested",
            user_id=query.from_user.id,
            order_id=order_id
        )
    
    except Exception as e:
        logger.error("message_operator_request_error", error=str(e))
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.message(ClientStates.waiting_message_to_operator)
async def receive_message_for_operator(message: types.Message, state: FSMContext):
    """
    Получаем сообщение от клиента и сохраняем его.
    Отправляем оператору уведомление.
    """
    
    try:
        data = await state.get_data()
        order_id = data.get("order_id")
        external_order_id = data.get("external_order_id")
        
        client_message = message.text
        
        async with async_session_maker() as session:
            message_repo = MessageRepository(session)
            order_repo = OrderRepository(session)
            
            # ← ✅ Сохраняем сообщение в БД
            saved_message = await message_repo.create(
                order_id=order_id,
                user_id=message.from_user.id,
                sender_type="client",  # client или operator
                text=client_message
            )
            
            # Уведомляем оператора
            try:
                operator_text = (
                    f"💬 <b>Новое сообщение от клиента</b>\n\n"
                    f"Заказ: <code>{external_order_id}</code>\n"
                    f"Клиент: {message.from_user.first_name or 'Неизвестно'}\n\n"
                    f"<b>Сообщение:</b>\n"
                    f"{client_message}"
                )
                
                await bot.send_message(
                    chat_id=config.operator_telegram_id,
                    text=operator_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(
                    "failed_to_notify_operator",
                    order_id=order_id,
                    error=str(e)
                )
            
            # Подтверждаем клиенту
            await message.answer(
                "✅ Сообщение отправлено оператору!\n\n"
                "Ответ придёт вам сюда 📬"
            )
            
            logger.info(
                "client_message_saved",
                order_id=order_id,
                user_id=message.from_user.id,
                message_length=len(client_message)
            )
        
        await state.clear()
    
    except Exception as e:
        logger.error("receive_message_for_operator_error", error=str(e))
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


# ==========================================
# КНОПКА: Назад к заказу
# ==========================================

@router.callback_query(F.data.startswith("client_back_to_order:"))
async def back_to_order(query: types.CallbackQuery, state: FSMContext):
    """Возвращает клиента к просмотру заказа."""
    
    try:
        order_id = int(query.data.split(":"))
        
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            order = await order_repo.get_by_id_with_relations(order_id)
            
            if order:
                await show_order_to_client(query.message, order, state)
            else:
                await query.message.edit_text("❌ Заказ не найден")
        
        await query.answer()
    
    except Exception as e:
        logger.error("back_to_order_error", error=str(e))
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# ==========================================
# СПРАВКА
# ==========================================

@router.callback_query(F.data == "client_help")
async def show_help(query: types.CallbackQuery):
    """Показывает справку для клиента."""
    
    text = (
        "<b>ℹ️ Справка</b>\n\n"
        "<b>Как отследить заказ?</b>\n"
        "1. Нажмите на ссылку из письма\n"
        "2. Вы увидите статус вашего заказа\n\n"
        "<b>Как связаться с оператором?</b>\n"
        "1. Нажмите кнопку 'Написать оператору'\n"
        "2. Напишите ваше сообщение\n"
        "3. Оператор ответит в этом чате\n\n"
        "<b>Что означают статусы?</b>\n"
        "  🆕 Новый - заказ только что создан\n"
        "  ⏳ В обработке - оператор готовит заказ\n"
        "  💳 Ожидание оплаты - выберите способ оплаты\n"
        "  ✅ Оплачено - заказ готов к отправке\n"
        "  🚚 В доставке - курьер едет к вам\n"
        "  ✅ Доставлено - заказ получен"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="client_i_have_order"
            )],
        ]
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
