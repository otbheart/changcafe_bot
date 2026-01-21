# app/bot/handlers/operator.py
"""
Обработчики для оператора.

Здесь живут команды которые доступны ТОЛЬКО оператору:
- Просмотр новых заказов
- Взятие заказа себе
- Отправка ссылки на оплату
- Отправка ссылки на трекинг
- И т.д.

ШАГ 3: ОСНОВНОЙ ФУНКЦИОНАЛ ОПЕРАТОРА
"""

from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
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
# ФИЛЬТР: только оператор
# ==========================================

operator_only = F.from_user.id == config.operator_telegram_id


# ==========================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: Проверка оператора
# ==========================================

async def check_operator(user_id: int) -> bool:
    """
    Проверяет что пользователь = оператор.
    
    ✅ ПРАВИЛЬНО: Проверяем по OPERAOR_TELEGRAM_ID из config
    ❌ НЕПРАВИЛЬНО: Было сравнение с полем role в БД (которое может быть устаревшим)
    """
    return user_id == config.operator_telegram_id


# ==========================================
# КОМАНДА: /operator
# ==========================================

@router.message(Command("operator"), operator_only)
async def cmd_operator(message: types.Message):
    """
    Панель оператора - главное меню.
    
    Доступные действия:
    - Новые заказы (status=NEW)
    - Мои заказы (assigned_to=operator_id)
    - Активные (IN_DELIVERY)
    """
    
    text = (
        "👨‍💼 <b>Панель оператора</b>\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🆕 Новые заказы",
                    callback_data="op_new_orders"
                )],
                [InlineKeyboardButton(
                    text="📦 Мои заказы",
                    callback_data="op_my_orders"
                )],
                [InlineKeyboardButton(
                    text="🚚 В доставке",
                    callback_data="op_in_delivery"
                )],
                [InlineKeyboardButton(
                    text="ℹ️ Справка",
                    callback_data="op_help"
                )],
            ]
        ),
        parse_mode="HTML"
    )
    
    logger.info("operator_panel_opened", operator_id=message.from_user.id)


# ==========================================
# ПРОСМОТР НОВЫХ ЗАКАЗОВ
# ==========================================

@router.callback_query(F.data == "op_new_orders", operator_only)
async def show_new_orders(query: types.CallbackQuery):
    """
    Показывает оператору все НОВЫЕ заказы.
    
    ✅ ИСПРАВЛЕНО:
    - Используем get_new_orders() с selectinload (быстро!)
    - Правильно обрабатываем поля Order
    - Показываем кнопку "Взять заказ"
    """
    
    try:
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            
            # ← ✅ ИСПОЛЬЗУЕМ get_new_orders() (N+1 FIX!)
            orders = await order_repo.get_new_orders(limit=20)
            
            if not orders:
                await query.message.edit_text("✅ Нет новых заказов!")
                return
            
            # Формируем текст со всеми заказами
            text = f"🆕 <b>Новых заказов: {len(orders)}</b>\n\n"
            
            for order in orders:
                # ← ✅ ПРАВИЛЬНЫЕ ПОЛЯ (из models.py)
                text += (
                    f"<code>ID: {order.external_order_id}</code>\n"
                    f"👤 <b>{order.tilda_name}</b>\n"
                    f"📞 {order.tilda_phone}\n"
                    f"📍 {order.address[:50]}...\n"
                    f"💰 {order.base_amount}₽\n"
                    f"⏰ {order.created_at.strftime('%d.%m %H:%M')}\n"
                    f"━━━━━━━━━━━━━\n"
                )
            
            # ← ✅ КНОПКА ДЛЯ ПРОСМОТРА ПЕРВОГО ЗАКАЗА
            if orders:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="📋 Открыть первый",
                            callback_data=f"op_order_view:{orders.id}"
                        )],
                        [InlineKeyboardButton(
                            text="◀️ Назад",
                            callback_data="op_back_to_menu"
                        )],
                    ]
                )
            else:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="◀️ Назад",
                            callback_data="op_back_to_menu"
                        )],
                    ]
                )
            
            await query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            logger.info(
                "operator_new_orders_viewed",
                operator_id=query.from_user.id,
                count=len(orders)
            )
    
    except Exception as e:
        logger.error("show_new_orders_error", error=str(e))
        await query.message.edit_text(f"❌ Ошибка: {str(e)}")


# ==========================================
# ПРОСМОТР ЗАКАЗОВ ОПЕРАТОРА
# ==========================================

@router.callback_query(F.data == "op_my_orders", operator_only)
async def show_my_orders(query: types.CallbackQuery):
    """
    Показывает ВСЕ заказы, назначенные оператору.
    
    ← ✅ ИСПОЛЬЗУЕМ get_operator_orders()
    """
    
    try:
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            
            # ← ✅ get_operator_orders() с фильтром по operator_id
            orders = await order_repo.get_operator_orders(
                operator_id=query.from_user.id
            )
            
            if not orders:
                await query.message.edit_text(
                    "📭 У вас нет назначенных заказов.\n\n"
                    "Нажмите '🆕 Новые заказы' чтобы взять заказ!"
                )
                return
            
            # Группируем по статусам
            by_status = {}
            for order in orders:
                status = order.status.value
                if status not in by_status:
                    by_status[status] = []
                by_status[status].append(order)
            
            # Формируем текст
            text = f"📦 <b>Ваши заказы ({len(orders)})</b>\n\n"
            
            for status, status_orders in by_status.items():
                text += f"<b>{status}</b> ({len(status_orders)})\n"
                for order in status_orders[:3]:  # Показываем первые 3 per status
                    text += (
                        f"  • ID {order.external_order_id} - {order.tilda_name}\n"
                    )
                if len(status_orders) > 3:
                    text += f"  ... и еще {len(status_orders) - 3}\n"
                text += "\n"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="op_back_to_menu"
                    )],
                ]
            )
            
            await query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            logger.info(
                "operator_my_orders_viewed",
                operator_id=query.from_user.id,
                count=len(orders)
            )
    
    except Exception as e:
        logger.error("show_my_orders_error", error=str(e))
        await query.message.edit_text(f"❌ Ошибка: {str(e)}")


# ==========================================
# ПРОСМОТР ЗАКАЗОВ В ДОСТАВКЕ
# ==========================================

@router.callback_query(F.data == "op_in_delivery", operator_only)
async def show_in_delivery(query: types.CallbackQuery):
    """
    Показывает заказы, которые сейчас в доставке.
    """
    
    try:
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            
            # ← ✅ Получаем только IN_DELIVERY заказы
            orders = await order_repo.get_operator_orders(
                operator_id=query.from_user.id,
                status=OrderStatus.IN_DELIVERY
            )
            
            if not orders:
                await query.message.edit_text(
                    "✅ Нет заказов в доставке"
                )
                return
            
            text = f"🚚 <b>В доставке ({len(orders)})</b>\n\n"
            
            for order in orders:
                text += (
                    f"ID: <code>{order.external_order_id}</code>\n"
                    f"Клиент: {order.tilda_name}\n"
                    f"📍 {order.delivery_address or order.address}\n"
                    f"🔗 <a href='{order.tracking_link}'>Трекинг</a>\n"
                    f"━━━━━━━━━━━━━\n"
                )
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="op_back_to_menu"
                    )],
                ]
            )
            
            await query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    
    except Exception as e:
        logger.error("show_in_delivery_error", error=str(e))
        await query.message.edit_text(f"❌ Ошибка: {str(e)}")


# ==========================================
# ПРОСМОТР ДЕТАЛЕЙ ЗАКАЗА
# ==========================================

@router.callback_query(F.data.startswith("op_order_view:"), operator_only)
async def show_order_details(query: types.CallbackQuery):
    """
    Показывает полные детали заказа.
    
    ← ✅ ИСПОЛЬЗУЕМ get_by_id_with_relations() для быстрой загрузки!
    """
    
    try:
        order_id = int(query.data.split(":"))
        
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            
            # ← ✅ БЫСТРАЯ ЗАГРУЗКА с relations
            order = await order_repo.get_by_id_with_relations(order_id)
            
            if not order:
                await query.message.edit_text("❌ Заказ не найден")
                return
            
            # Формируем детальный текст
            text = f"<b>📋 Заказ {order.external_order_id}</b>\n\n"
            
            text += "<b>👤 Клиент:</b>\n"
            text += f"  Имя: {order.tilda_name}\n"
            text += f"  Телефон: {order.tilda_phone}\n"
            if order.user:
                text += f"  Telegram: @{order.user.username or 'N/A'}\n"
            
            text += "\n<b>📦 Заказ:</b>\n"
            text += f"  Статус: <b>{order.status.value}</b>\n"
            text += f"  Адрес: {order.address}\n"
            text += f"  Сумма: {order.base_amount}₽\n"
            if order.delivery_cost:
                text += f"  Доставка: {order.delivery_cost}₽\n"
            if order.total_amount:
                text += f"  Итого: <b>{order.total_amount}₽</b>\n"
            
            text += f"\n<b>⏰ История:</b>\n"
            text += f"  Создан: {order.created_at.strftime('%d.%m %H:%M')}\n"
            if order.confirmed_at:
                text += f"  Подтвержден: {order.confirmed_at.strftime('%d.%m %H:%M')}\n"
            if order.paid_at:
                text += f"  Оплачен: {order.paid_at.strftime('%d.%m %H:%M')}\n"
            
            text += "\n<b>📝 Товары:</b>\n"
            if order.items:
                for item in order.items:
                    text += f"  • {item['title']} x{item['quantity']} = {item['price']*item['quantity']}₽\n"
            
            # Кнопки действий в зависимости от статуса
            buttons = []
            
            if order.status == OrderStatus.NEW:
                buttons.append([InlineKeyboardButton(
                    text="✅ Взять заказ",
                    callback_data=f"op_take_order:{order_id}"
                )])
            
            if order.status == OrderStatus.WAITING_OPERATOR:
                buttons.append([InlineKeyboardButton(
                    text="💳 Отправить ссылку на оплату",
                    callback_data=f"op_send_payment:{order_id}"
                )])
                buttons.append([InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"op_cancel_order:{order_id}"
                )])
            
            if order.status == OrderStatus.PAID:
                buttons.append([InlineKeyboardButton(
                    text="🚚 Отправить в доставку",
                    callback_data=f"op_send_delivery:{order_id}"
                )])
            
            if order.status == OrderStatus.IN_DELIVERY:
                buttons.append([InlineKeyboardButton(
                    text="✅ Заказ доставлен",
                    callback_data=f"op_complete_order:{order_id}"
                )])
            
            buttons.append([InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="op_back_to_menu"
            )])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            logger.info(
                "order_details_viewed",
                operator_id=query.from_user.id,
                order_id=order_id,
                status=order.status.value
            )
    
    except Exception as e:
        logger.error("show_order_details_error", error=str(e))
        await query.message.edit_text(f"❌ Ошибка: {str(e)}")


# ==========================================
# ВЗЯТЬ ЗАКАЗ
# ==========================================

@router.callback_query(F.data.startswith("op_take_order:"), operator_only)
async def take_order(query: types.CallbackQuery):
    """
    Оператор берет заказ себе.
    
    ← ✅ assign_to_operator()
    """
    
    try:
        order_id = int(query.data.split(":"))
        
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            
            # ← ✅ Назначаем заказ оператору
            order = await order_repo.assign_to_operator(
                order_id=order_id,
                operator_id=query.from_user.id
            )
            
            # Уведомляем клиента
            if order.user:
                try:
                    await bot.send_message(
                        chat_id=order.user.user_id,
                        text=(
                            f"✅ Ваш заказ <code>{order.external_order_id}</code> "
                            f"взят в обработку!\n\n"
                            f"Скоро получите информацию о доставке 🚚"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(
                        "failed_to_notify_client",
                        order_id=order_id,
                        error=str(e)
                    )
            
            # Уведомляем оператора
            await query.answer("✅ Заказ взят!", show_alert=False)
            
            # Обновляем сообщение
            await show_order_details(query)
            
            logger.info(
                "order_taken",
                operator_id=query.from_user.id,
                order_id=order_id
            )
    
    except Exception as e:
        logger.error("take_order_error", error=str(e))
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# ==========================================
# ОТПРАВИТЬ ССЫЛКУ НА ОПЛАТУ
# ==========================================

@router.callback_query(F.data.startswith("op_send_payment:"), operator_only)
async def send_payment_link(query: types.CallbackQuery, state: FSMContext):
    """
    Оператор отправляет ссылку на оплату клиенту.
    
    Запрашиваем ссылку у оператора.
    """
    
    try:
        order_id = int(query.data.split(":"))
        
        # Сохраняем order_id в state для дальнейшей обработки
        await state.update_data(order_id=order_id)
        
        await query.message.edit_text(
            "💳 Отправьте ссылку на оплату в формате:\n\n"
            "<code>https://yookassa.ru/checkout/...</code>",
            parse_mode="HTML"
        )
        
        # ← ✅ Устанавливаем state чтобы поймать следующее сообщение
        await state.set_state("waiting_payment_link")
        
        logger.info(
            "waiting_payment_link",
            operator_id=query.from_user.id,
            order_id=order_id
        )
    
    except Exception as e:
        logger.error("send_payment_link_error", error=str(e))
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.message(F.text.startswith("http"), StateFilter("waiting_payment_link"), operator_only)
async def receive_payment_link(message: types.Message, state: FSMContext):
    """
    Получаем ссылку на оплату от оператора и сохраняем ее.
    """
    
    try:
        data = await state.get_data()
        order_id = data.get("order_id")
        payment_link = message.text
        
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            
            # ← ✅ Сохраняем ссылку и меняем статус
            order = await order_repo.set_payment_link(
                order_id=order_id,
                payment_link=payment_link
            )
            
            # Отправляем ссылку клиенту
            if order.user:
                try:
                    await bot.send_message(
                        chat_id=order.user.user_id,
                        text=(
                            f"💳 <b>Оплата заказа {order.external_order_id}</b>\n\n"
                            f"Перейдите по ссылке для оплаты:\n"
                            f"{payment_link}\n\n"
                            f"Сумма: {order.total_amount or order.base_amount}₽"
                        ),
                        parse_mode="HTML"
                    )
                    
                    await message.answer(
                        f"✅ Ссылка на оплату отправлена клиенту!"
                    )
                except Exception as e:
                    logger.error(
                        "failed_to_send_payment_link",
                        order_id=order_id,
                        error=str(e)
                    )
                    await message.answer(
                        f"⚠️ Ошибка отправки клиенту, но ссылка сохранена"
                    )
            
            logger.info(
                "payment_link_saved",
                operator_id=message.from_user.id,
                order_id=order_id
            )
        
        await state.clear()
    
    except Exception as e:
        logger.error("receive_payment_link_error", error=str(e))
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


# ==========================================
# КНОПКА: Назад в меню
# ==========================================

@router.callback_query(F.data == "op_back_to_menu", operator_only)
async def back_to_menu(query: types.CallbackQuery):
    """Возвращает в главное меню оператора."""
    await cmd_operator(query.message)
    await query.answer()


# ==========================================
# СПРАВКА
# ==========================================

@router.callback_query(F.data == "op_help", operator_only)
async def show_help(query: types.CallbackQuery):
    """Показывает справку по использованию."""
    
    text = (
        "<b>ℹ️ Справка оператора</b>\n\n"
        "<b>Статусы заказов:</b>\n"
        "  🆕 NEW - новый заказ из Tilda\n"
        "  ⏳ AWAITING_CONFIRMATION - ждет подтверждения от клиента\n"
        "  ⏳ WAITING_OPERATOR - ждет оператора\n"
        "  💳 AWAITING_PAYMENT - ждет оплаты\n"
        "  ✅ PAID - оплачен\n"
        "  🚚 IN_DELIVERY - в доставке\n"
        "  ✅ COMPLETED - завершен\n\n"
        "<b>Ваши действия:</b>\n"
        "  1. Смотрите новые заказы\n"
        "  2. Берете заказ кнопкой 'Взять'\n"
        "  3. Отправляете ссылку на оплату\n"
        "  4. Когда оплачено - отправляете в доставку\n"
        "  5. Когда доставлено - отмечаете как завершено"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="op_back_to_menu"
            )],
        ]
    )
    
    await query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
