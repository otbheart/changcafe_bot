# Chang Cafe Bot - ПОЛНЫЙ КОД

## СТРУКТУРА ПРОЕКТА


## ./app/__init__.py
```python
# app/__init__.py
"""Инициализация приложения."""

__version__ = "1.0.0"
```

## ./app/api/__init__.py
```python
# app/api/__init__.py
"""
🌐 API ROUTES (маршруты FastAPI)

Вебхуки от Tilda приходят сюда.
Когда кто-то оформит заказ на сайте - Tilda отправит POST запрос сюда.
"""

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from infrastructure.logger import logger
from infrastructure.database import async_session_maker
from app.models import User, Order, OrderItem

# ==========================================
# СОЗДАЁМ ROUTER
# ==========================================

webhooks_router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# ==========================================
# ВЕБХУК ОТ TILDA
# ==========================================

@webhooks_router.post("/tilda/order")
async def tilda_order_webhook(request: Request):
    """
    📨 Получаем данные заказа от Tilda.
    
    Когда клиент оформит заказ на сайте - Tilda отправит сюда POST запрос.
    
    Пример данных от Tilda:
    {
        "orderId": "123456",
        "customerName": "Иван Петров",
        "customerPhone": "+7 999 123 45 67",
        "customerEmail": "ivan@mail.ru",
        "orderPrice": "650.00",
        "orderItems": [
            {"title": "Капучино", "quantity": "2", "price": "250.00"},
            {"title": "Круассан", "quantity": "1", "price": "150.00"}
        ]
    }
    """
    
    try:
        # Получаем JSON данные из запроса
        data = await request.json()
        logger.info("webhook_received", data=data)
        
        # Извлекаем нужные данные
        order_id = data.get("orderId", "unknown")
        customer_name = data.get("customerName", "Unknown")
        customer_phone = data.get("customerPhone", "")
        customer_email = data.get("customerEmail", "")
        order_price = float(data.get("orderPrice", 0))
        order_items = data.get("orderItems", [])
        
        # ==========================================
        # СОХРАНЯЕМ В БД
        # ==========================================
        
        async with async_session_maker() as session:
            # 1. Создаём или получаем пользователя
            user = await session.query(User).filter(
                User.phone == customer_phone
            ).first()
            
            if not user:
                user = User(
                    name=customer_name,
                    phone=customer_phone,
                    email=customer_email,
                )
                session.add(user)
                await session.flush()  # Получаем user.id
            
            # 2. Создаём заказ
            order = Order(
                tilda_order_id=order_id,
                user_id=user.id,
                total_price=order_price,
                status="new",
                payment_status="unpaid",
            )
            session.add(order)
            await session.flush()  # Получаем order.id
            
            # 3. Добавляем товары в заказ
            for item in order_items:
                item_name = item.get("title", "Unknown Product")
                item_qty = int(item.get("quantity", 1))
                item_price = float(item.get("price", 0))
                item_total = item_qty * item_price
                
                order_item = OrderItem(
                    order_id=order.id,
                    product_name=item_name,
                    quantity=item_qty,
                    price=item_price,
                    total=item_total,
                )
                session.add(order_item)
            
            # 4. Коммитим все изменения
            await session.commit()
            
            logger.info(
                "order_created",
                order_id=order_id,
                customer=customer_name,
                total=order_price
            )
        
        # ==========================================
        # ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ ОПЕРАТОРУ
        # ==========================================
        
        # Здесь будет отправка уведомления в Telegram оператору
        # TODO: Реализовать когда добавим бот функционал
        
        # Пока просто логируем
        logger.info(
            "operator_should_be_notified",
            order_id=order_id,
            customer_name=customer_name
        )
        
        # ==========================================
        # ОТПРАВЛЯЕМ ОТВЕТ TILDA
        # ==========================================
        
        # Tilda ожидает ответ "ok" чтобы знать что всё обработалось
        return {"status": "ok"}
        
    except Exception as e:
        logger.error("webhook_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# HEALTH CHECK (проверка что API живой)
# ==========================================

@webhooks_router.get("/health")
async def health_check():
    """
    Проверка что сервер живой.
    
    Используется для мониторинга.
    """
    return {
        "status": "healthy",
        "version": "1.0.0"
    }

# ==========================================
# ЭКСПОРТ
# ==========================================

__all__ = ["webhooks_router"]
```

## ./app/api/app.py
```python
# app/api/app.py
"""
FastAPI приложение для обработки вебхуков от Tilda.

FastAPI = веб-фреймворк для создания REST API.

В нашем случае нам нужен FastAPI для обработки POST запроса
когда Tilda отправляет данные о новом заказе.
"""

from fastapi import FastAPI

from app.api.webhooks.tilda import router as tilda_router  
# Импортируем роутер вебхуков

from infrastructure.database.base import init_db, close_db


# Создаем FastAPI приложение
app = FastAPI(
    title="Chang Cafe Bot API",
    description="API для обработки вебхуков от Tilda"
)


# ==========================================
# EVENT: Startup (при старте приложения)
# ==========================================

@app.on_event("startup")
async def startup():
    """
    Вызывается один раз при старте приложения.
    Инициализируем БД (создаем таблицы если их нет).
    """
    
    await init_db()


# ==========================================
# EVENT: Shutdown (при выключении приложения)
# ==========================================

@app.on_event("shutdown")
async def shutdown():
    """
    Вызывается один раз при выключении приложения.
    Закрываем соединения с БД.
    """
    
    await close_db()


# ==========================================
# ENDPOINT: Health check
# ==========================================

@app.get("/health")
async def health_check():
    """
    Простой endpoint для проверки что приложение живо.
    
    Используется для мониторинга (Docker, Kubernetes и т.д.).
    
    Пример:
        GET /health
        → {"status": "ok", "service": "changcafe_bot"}
    """
    
    return {
        "status": "ok",
        "service": "changcafe_bot"
    }


# ==========================================
# РЕГИСТРИРУЕМ РОУТЕР
# ==========================================


# Все endpoints из tilda.py будут доступны как /api/webhook/...
app.include_router(tilda_router, prefix="/api/webhook")

```

## ./app/api/webhooks/__init__.py
```python
# app/api/webhooks/__init__.py
"""Инициализация вебхуков."""

from .tilda import router

__all__ = ["router"]
```

## ./app/api/webhooks/tilda.py
```python
# app/api/webhooks/tilda.py
"""
Обработчик вебхука от Tilda.

Когда пользователь оформляет заказ на сайте changcafe.ru,
Tilda отправляет POST запрос на наш сервер.

Мы обрабатываем этот запрос, сохраняем заказ в БД,
и отправляем уведомление оператору.
"""

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from pydantic import BaseModel

from typing import Optional

from decimal import Decimal

import structlog


from infrastructure.database.base import async_session_maker

from infrastructure.database.repositories import OrderRepository

#from app.bot.services.notifications import notify_operator_new_order

from config.settings import config

from aiogram import Bot

logger = structlog.get_logger()
router = APIRouter(prefix="/webhook/tilda")

bot = Bot(token=config.bot_token)


# ==========================================
# МОДЕЛЬ ДАННЫХ: Webhook от Tilda
# ==========================================

class TildaWebhookPayload(BaseModel):
    """
    Pydantic модель для валидации данных от Tilda.
    
    Когда приходит POST запрос, FastAPI автоматически
    проверит что все поля имеют правильный тип.
    """
    formid: str                    
    # Order ID из Tilda
    name: str                      
    # Имя клиента
    phone: str                     
    # Телефон
    street: str                    
    # Улица
    home: str                      
    # Дом
    apartment: Optional[str] = None  
    # Квартира (опционально)
    amount: Decimal               
    # Сумма
    
    class Config:
        extra = "allow"   
        # Разрешаем дополнительные поля (Tilda может отправить ещё что-то)


# ==========================================
# ENDPOINT: POST /api/webhook/tilda
# ==========================================

@router.post("/")
async def handle_tilda_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Webhook endpoint для Tilda.
    
    Когда Tilda отправляет данные о новом заказе, этот endpoint его обрабатывает.
    
    Логика:
    1. Получаем данные из запроса
    2. Валидируем их (проверяем что всё заполнено правильно)
    3. Проверяем что заказа ещё нет в БД (защита от дубликатов)
    4. Создаем заказ в БД
    5. Генерируем deep link для клиента
    6. Отправляем оператору уведомление (в фоне)
    7. Возвращаем OK ответ Tilda
    """
    
    try:
        
        # ==========================================
        # ШАГ 1: Получаем данные
        # ==========================================
        
        # Из POST запроса берем form data
        
        # Tilda отправляет данные в формате multipart/form-data
try:
    form_data = await request.form()
except:
    payload = await request.json()
    form_data = payload
        
        logger.info(
            "tilda_webhook_received",
            form_data_keys=list(form_data.keys())
        )
        
        # ==========================================
        # ШАГ 2: Валидируем обязательные поля
        # ==========================================
        
        order_id = form_data.get("formid")
        
        if not order_id:
            logger.error("webhook_validation_failed", reason="missing_formid")
            
            raise HTTPException(400, "Missing formid")
        
        # ==========================================
        # ШАГ 3: Работаем с БД
        # ==========================================
        
        async with async_session_maker() as session:
            order_repo = OrderRepository(session)
            
            # Проверяем, не обработан ли уже этот заказ
            
            # Это защита от дубликатов (если Tilda отправит два раза)
            existing = await order_repo.get_by_external_id(order_id)
            
            if existing:
                logger.warning("duplicate_order", order_id=order_id)
                
                # Возвращаем OK (чтобы Tilda не пробовала ещё раз)
                
                return {"status": "ok", "message": "Already processed"}
            
            # ==========================================
            # ШАГ 4: Собираем товары
            # ==========================================
            
            # Tilda отправляет товары в таком формате:
            # payment[0][title] = "Пицца "
            # payment[0][price] = "690"
            # payment[0][quantity] = "1"
            # payment[1][title] = "Кола "
            # и т.д.
            
            items = []
            i = 0
            
            while f"payment[{i}][title]" in form_data:
                
                # Для каждого товара создаем словарь
                items.append({
                    "title": form_data.get(f"payment[{i}][title]"),
                    "price": float(form_data.get(f"payment[{i}][price]", 0)),
                    "quantity": int(form_data.get(f"payment[{i}][quantity]", 1)),
                    "sku": form_data.get(f"payment[{i}][sku]")
                })
                i += 1
            
            # ==========================================
            # ШАГ 5: Собираем адрес
            # ==========================================
            
            address_parts = [
                form_data.get("street", ""),      
                # Улица
                f"д. {form_data.get('home', '')}", 
                # Дом
            ]
            
            if form_data.get("apartment"):
                address_parts.append(f"кв. {form_data.get('apartment')}")  
                # Квартира
            
            # Объединяем в одну строку
            full_address = ", ".join(filter(None, address_parts))
            
            # filter(None, ...) = убирает пустые строки
            
            # ==========================================
            # ШАГ 6: Создаем заказ в БД
            # ==========================================
            
            order = await order_repo.create_from_webhook(
                external_order_id=order_id,
                tilda_name=form_data.get("name", "Guest"),
                tilda_phone=form_data.get("phone", ""),
                address=full_address,
                items=items,
                base_amount=float(form_data.get("amount", 0))
            )
            
            # ==========================================
            # ШАГ 7: Генерируем deep link
            # ==========================================
            
            # Deep link = ссылка которая откроет бота и передаст order_id
            deep_link = f"https://t.me/{config.bot_username}?start=order_{order_id}"
            
            logger.info(
                "order_created",
                order_id=order_id,
                deep_link=deep_link
            )
            
            # ==========================================
            # ШАГ 8: Отправляем оператору уведомление в фоне
            # ==========================================
            
            # background_tasks = очередь задач которые выполняются в фоне
            
            # Это нужно чтобы не ждать отправки уведомления перед ответом Tilda
            
            #background_tasks.add_task(
            #    notify_operator_new_order,
            #    order=order,
            #    deep_link=deep_link
            #)
        
        # ==========================================
        # ШАГ 9: Возвращаем ответ
        # ==========================================
        
        return {
            "status": "ok",
            "order_id": order_id,
            "deep_link": deep_link
        }
    
    # ==========================================
    # ОБРАБОТКА ОШИБОК
    # ==========================================
    except HTTPException:
        
        # FastAPI HTTPException = это intentional ошибка которую мы кидаем
        
        raise
    
    except Exception as e:
        
        # Неожиданная ошибка = логируем и возвращаем 500
        logger.error("webhook_error", error=str(e))
        
        raise HTTPException(500, "Internal error")

```

## ./app/bot/__init__.py
```python
# app/bot/__init__.py
"""Инициализация бота."""

from .handlers import main_router

__all__ = ["main_router"]
```

## ./app/bot/filters/__init__.py
```python
# app/bot/filters/__init__.py
"""Инициализация фильтров."""

from .is_operator import IsOperatorFilter

__all__ = ["IsOperatorFilter"]
```

## ./app/bot/filters/role.py
```python
# app/bot/filters/role.py
"""
Фильтры в aiogram — это способ ограничить доступ к определенным обработчикам.

Пример:
    @router.message(Command("admin"), IsOperator())
    async def admin_command(message: Message):
        # Эта команда выполнится ТОЛЬКО если пользователь оператор
        await message.answer("Привет, оператор!")

Если клиент попробует выполнить эту команду, ничего не произойдет.
"""

from aiogram.filters import BaseFilter

from aiogram import types

from infrastructure.database.models import UserRole

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.repositories import UserRepository


class IsOperator(BaseFilter):
    """
    Фильтр: проверяет, что пользователь — оператор.
    
    Пример:
        @router.callback_query(F.data.startswith("take_order:"), IsOperator())
        async def handle_take_order(callback: CallbackQuery):
            # Выполнится только если это оператор
            ...
    """
    
    
    async def __call__(
        self,
        message: types.Message,
        session: AsyncSession
    ) -> bool:
        """
        Aiogram вызовет эту функцию перед обработчиком.
        
        Возвращаем True = разрешить обработчику выполниться
        Возвращаем False = запретить (обработчик не выполнится)
        """
        repo = UserRepository(session)
        user = await repo.get_by_id(message.from_user.id)
        
        # Если юзер есть И его роль == operator, возвращаем True
        return user and user.role == UserRole.OPERATOR


class IsClient(BaseFilter):
    """
    Фильтр: проверяет, что пользователь — клиент.
    """
    
    
    async def __call__(
        self,
        message: types.Message,
        session: AsyncSession
    ) -> bool:
        repo = UserRepository(session)
        user = await repo.get_by_id(message.from_user.id)
        
        return user and user.role == UserRole.CLIENT


class IsValidOrder(BaseFilter):
    """
    Фильтр: проверяет, что заказ существует и валиден.
    
    Пример:
        @router.callback_query(IsValidOrder(order_id_arg="order_id"))
        async def handle_order(callback: CallbackQuery):
            # Выполнится только если заказ существует
            ...
    """
    
    
    def __init__(self, order_id_arg: str = "order_id"):
        """
        order_id_arg — имя параметра, где лежит ID заказа
        """
        self.order_id_arg = order_id_arg
    
    
    async def __call__(
        self,
        message: types.Message,
        session: AsyncSession
    ) -> bool:
        
        # TODO: реализовать проверку
        
        return True

```

## ./app/bot/handlers/__init__.py
```python
# app/bot/handlers/__init__.py
"""
🤖 BOT HANDLERS (обработчики команд)

Все команды бота (/start, /help, /order и т.д.)
"""

from aiogram import Router

# ==========================================
# СОЗДАЁМ MAIN ROUTER
# ==========================================

# Router = маршрутизатор для обработки команд
main_router = Router()

# ==========================================
# ИМПОРТИРУЕМ ВСЕ ОБРАБОТЧИКИ
# ==========================================

# Здесь будут импортироваться все обработчики:
# from .commands import command_router
# from .orders import order_router
# и т.д.

# И затем их нужно подключить:
# main_router.include_router(command_router)
# main_router.include_router(order_router)

# ==========================================
# БАЗОВЫЙ ОБРАБОТЧИК (заглушка)
# ==========================================

from aiogram import types
from aiogram.filters import Command

@main_router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Привет! Это бот Chang Cafe\n"
        "Добро пожаловать! 🎉"
    )

@main_router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    await message.answer(
        "ℹ️ <b>Справка</b>\n\n"
        "/start - Главное меню\n"
        "/help - Этот текст"
    )

# ==========================================
# ЭКСПОРТ
# ==========================================

__all__ = ["main_router"]
```

## ./app/bot/handlers/client.py
```python
# app/bot/handlers/client.py
"""
Обработчики для клиентов.

Здесь живут все команды и кнопки для обычных пользователей:
- /start
- "Оформить заказ"
- Ввод номера телефона
- Подтверждение заказа
- И т.д.
"""

from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states import OrderState
from infrastructure.database.models import User, UserRole, Order, OrderStatus
from infrastructure.logger import logger

# Создаем роутер для клиентских обработчиков
router = Router()

# ==========================================
# ФИЛЬТР: только клиенты (не операторы)
# ==========================================

client_only = StateFilter(UserRole.CLIENT)

# ==========================================
# КОМАНДА: /start
# ==========================================

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик команды /start.
    
    Логика:
    1. Проверяем есть ли пользователь в БД
    2. Если нет - создаём
    3. Выводим приветственное сообщение
    """
    
    user_id = message.from_user.id
    
    # Проверяем есть ли пользователь в БД
    from sqlalchemy import select
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalars().first()
    
    # Если пользователя нет - создаём
    if not user:
        user = User(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name or "Пользователь",
            last_name=message.from_user.last_name,
            role=UserRole.CLIENT
        )
        session.add(user)
        await session.commit()
        logger.info("new_user_created", user_id=user_id, username=message.from_user.username)
    
    # Выводим приветствие
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать в Chang Cafe бот! 🍽️\n\n"
        "Здесь ты можешь:\n"
        "• Оформить заказ\n"
        "• Узнать статус текущего заказа\n"
        "• Связаться с оператором\n\n"
        "Что ты хочешь сделать?",
        reply_markup=get_main_menu()
    )
    
    logger.info("start_command", user_id=user_id)

# ==========================================
# ГЛАВНОЕ МЕНЮ
# ==========================================

def get_main_menu() -> ReplyKeyboardMarkup:
    """Кнопки главного меню."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Оформить заказ")],
            [KeyboardButton(text="📦 Мои заказы")],
            [KeyboardButton(text="💬 Написать оператору")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

# ==========================================
# КНОПКА: "Оформить заказ"
# ==========================================

@router.message(F.text == "📋 Оформить заказ")
async def order_start(message: types.Message, state: FSMContext):
    """
    Начало процесса оформления заказа.
    
    Логика:
    1. Переходим в состояние OrderState.waiting_for_order_data
    2. Выводим инструкцию
    """
    
    await state.set_state(OrderState.waiting_for_order_data)
    
    await message.answer(
        "📝 Отправь мне ссылку на свой заказ из Tilda или данные заказа:\n\n"
        "Нужны:\n"
        "• Номер заказа\n"
        "• Что заказал\n"
        "• Сумма\n\n"
        "Или просто скопируй и пришли информацию с сайта.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )
    
    logger.info("order_start", user_id=message.from_user.id)

# ==========================================
# ПОЛУЧЕНИЕ ДАННЫХ ЗАКАЗА
# ==========================================

@router.message(OrderState.waiting_for_order_data)
async def order_data_received(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Получение данных заказа от клиента.
    
    Логика:
    1. Сохраняем данные заказа
    2. Просим подтвердить
    """
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена. Вернись в главное меню.", reply_markup=get_main_menu())
        return
    
    # Сохраняем данные в состояние FSM
    await state.update_data(order_info=message.text)
    
    # Переходим к подтверждению
    await state.set_state(OrderState.waiting_for_confirmation)
    
    await message.answer(
        f"✅ Получил твои данные:\n\n{message.text}\n\n"
        "Всё верно?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data="confirm_order"),
                    InlineKeyboardButton(text="❌ Нет", callback_data="cancel_order"),
                ]
            ]
        )
    )

# ==========================================
# ПОДТВЕРЖДЕНИЕ ЗАКАЗА
# ==========================================

@router.callback_query(F.data == "confirm_order", OrderState.waiting_for_confirmation)
async def confirm_order(query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Подтверждение заказа клиентом.
    
    Логика:
    1. Создаём заказ в БД
    2. Уведомляем оператора
    3. Показываем клиенту статус
    """
    
    data = await state.get_data()
    order_info = data.get("order_info", "")
    
    # Создаём заказ в БД
    order = Order(
        external_order_id=f"manual_{query.from_user.id}_{query.message.message_id}",
        user_id=query.from_user.id,
        tilda_name=order_info,
        status=OrderStatus.AWAITING_CONFIRMATION,
        customer_phone=None,  # Попросим позже если нужно
        customer_name=query.from_user.first_name,
        raw_data={"source": "telegram", "info": order_info}
    )
    
    session.add(order)
    await session.commit()
    
    # Очищаем состояние
    await state.clear()
    
    # Отвечаем клиенту
    await query.message.edit_text(
        "✅ Заказ создан!\n\n"
        "📍 Статус: Ожидание подтверждения оператором\n"
        "🆔 ID заказа: " + order.external_order_id + "\n\n"
        "Оператор свяжется с тобой в ближайшее время!"
    )
    
    # Говорим что нужно делать дальше
    await query.message.answer(
        "Что дальше?",
        reply_markup=get_main_menu()
    )
    
    logger.info("order_confirmed", user_id=query.from_user.id, order_id=order.id)

# ==========================================
# ОТМЕНА ПОДТВЕРЖДЕНИЯ
# ==========================================

@router.callback_query(F.data == "cancel_order", OrderState.waiting_for_confirmation)
async def cancel_order_confirmation(query: types.CallbackQuery, state: FSMContext):
    """Если клиент сказал что данные неверные."""
    
    await state.set_state(OrderState.waiting_for_order_data)
    
    await query.message.edit_text(
        "Окей, попробуем ещё раз.\n\n"
        "Отправь данные заказа:"
    )
    
    logger.info("order_confirmation_cancelled", user_id=query.from_user.id)
```

## ./app/bot/handlers/common.py
```python
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
```

## ./app/bot/handlers/operator.py
```python
# app/bot/handlers/operator.py
"""
Обработчики для оператора.

Здесь живут команды которые доступны ТОЛЬКО оператору:
- Просмотр новых заказов
- Подтверждение заказа
- Отправка ссылки на оплату
- И т.д.
"""

from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from config.settings import config
from infrastructure.database.models import User, Order, OrderStatus, UserRole
from infrastructure.logger import logger

router = Router()

# ==========================================
# ФИЛЬТР: только оператор
# ==========================================

def is_operator_filter(message: types.Message) -> bool:
    """Проверяет что это оператор."""
    return message.from_user.id == config.operator_telegram_id

operator_only = F.from_user.id == config.operator_telegram_id

# ==========================================
# КОМАНДА: /operator
# ==========================================

@router.message(Command("operator"), operator_only)
async def cmd_operator(message: types.Message):
    """Панель оператора."""
    
    await message.answer(
        "👨‍💼 Панель оператора\n\n"
        "Доступные действия:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Новые заказы", callback_data="operator_new_orders")],
                [InlineKeyboardButton(text="📦 Все заказы", callback_data="operator_all_orders")],
                [InlineKeyboardButton(text="👥 Пользователи", callback_data="operator_users")],
                [InlineKeyboardButton(text="🔔 Уведомления", callback_data="operator_notifications")],
            ]
        )
    )
    
    logger.info("operator_panel_opened", user_id=message.from_user.id)

# ==========================================
# ПРОСМОТР НОВЫХ ЗАКАЗОВ
# ==========================================

@router.callback_query(F.data == "operator_new_orders", operator_only)
async def show_new_orders(query: types.CallbackQuery, session: AsyncSession):
    """Показывает оператору все новые заказы."""
    
    # Получаем все новые заказы
    stmt = select(Order).where(Order.status == OrderStatus.NEW).order_by(Order.id.desc())
    result = await session.execute(stmt)
    orders = result.scalars().all()
    
    if not orders:
        await query.message.edit_text("✅ Нет новых заказов")
        return
    
    # Формируем текст со всеми заказами
    text = f"📋 Новых заказов: {len(orders)}\n\n"
    
    for order in orders[:10]:  # Показываем первые 10
        text += (
            f"🆔 {order.external_order_id}\n"
            f"👤 {order.customer_name}\n"
            f"📞 {order.customer_phone or 'не указан'}\n"
            f"💰 {order.customer_sum or 'не указана'}\n"
            f"⏰ {order.created_at.strftime('%d.%m %H:%M')}\n\n"
        )
    
    await query.message.edit_text(text)
    
    logger.info("operator_new_orders_viewed", operator_id=query.from_user.id, count=len(orders))

# ==========================================
# ПРОСМОТР ВСЕХ ЗАКАЗОВ
# ==========================================

@router.callback_query(F.data == "operator_all_orders", operator_only)
async def show_all_orders(query: types.CallbackQuery, session: AsyncSession):
    """Показывает оператору все заказы (по статусам)."""
    
    # Подсчитываем заказы по статусам
    stats = {}
    for status in OrderStatus:
        stmt = select(Order).where(Order.status == status)
        result = await session.execute(stmt)
        count = len(result.scalars().all())
        stats[status] = count
    
    # Формируем текст
    text = "📊 Статистика заказов:\n\n"
    for status, count in stats.items():
        text += f"{status.value}: {count}\n"
    
    await query.message.edit_text(text)
    logger.info("operator_all_orders_viewed", operator_id=query.from_user.id)

# ==========================================
# ОТПРАВКА ССЫЛКИ НА ОПЛАТУ
# ==========================================

@router.message(operator_only)
async def operator_send_payment_link(message: types.Message, session: AsyncSession):
    """
    Оператор может отправить ссылку на оплату клиенту.
    
    Используется для ручного ввода команды вида:
    /pay <order_id> <payment_link>
    """
    
    if not message.text or not message.text.startswith("/pay"):
        return
    
    try:
        # Парсим команду: /pay <order_id> <payment_link>
        parts = message.text.split(maxsplit=2)
        
        if len(parts) < 3:
            await message.answer("❌ Формат: /pay <order_id> <payment_link>")
            return
        
        order_id = parts[1]
        payment_link = parts[2]
        
        # Находим заказ
        stmt = select(Order).where(Order.external_order_id == order_id)
        result = await session.execute(stmt)
        order = result.scalars().first()
        
        if not order:
            await message.answer(f"❌ Заказ {order_id} не найден")
            return
        
        # Обновляем статус и сохраняем ссылку
        stmt = update(Order).where(Order.id == order.id).values(
            status=OrderStatus.AWAITING_PAYMENT,
            payment_link=payment_link
        )
        await session.execute(stmt)
        await session.commit()
        
        # Уведомляем клиента (нужна функция из notifications)
        await message.answer(
            f"✅ Ссылка на оплату отправлена клиенту:\n{payment_link}"
        )
        
        logger.info("payment_link_sent", order_id=order_id, operator_id=message.from_user.id)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        logger.error("operator_error", error=str(e))
```

## ./app/bot/keyboards/__init__.py
```python
# app/bot/keyboards/__init__.py
"""Инициализация клавиатур."""

from .client import get_main_menu, get_order_confirmation_kb
from .operator import get_operator_menu

__all__ = ["get_main_menu", "get_order_confirmation_kb", "get_operator_menu"]
```

## ./app/bot/keyboards/client.py
```python
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

```

## ./app/bot/keyboards/operator.py
```python
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

```

## ./app/bot/middlewares/__init__.py
```python
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
```

## ./app/bot/middlewares/database.py
```python
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
```

## ./app/bot/middlewares/logging.py
```python
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
```

## ./app/bot/middlewares/throttling.py
```python
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
```

## ./app/bot/services/__init__.py
```python
# app/bot/services/__init__.py
"""Инициализация сервисов."""

from .notifications import NotificationService

__all__ = ["NotificationService"]
```

## ./app/bot/services/notifications.py
```python
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
```

## ./app/bot/services/orders.py
```python
# app/bot/services/orders.py
"""
Сервис заказов.

Бизнес-логика для работы с заказами:
- Создание
- Обновление статуса
- Отправка оплаты
- И т.д.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import Order, OrderStatus, User
from infrastructure.logger import logger

class OrderService:
    """Сервис для работы с заказами."""
    
    # ==========================================
    # ПОЛУЧИТЬ ЗАКАЗ ПО ID
    # ==========================================
    
    @staticmethod
    async def get_order(order_id: int, session: AsyncSession) -> Order:
        """Получить заказ по ID."""
        
        stmt = select(Order).where(Order.id == order_id)
        result = await session.execute(stmt)
        order = result.scalars().first()
        
        if not order:
            logger.warning("order_not_found", order_id=order_id)
        
        return order
    
    # ==========================================
    # ПОЛУЧИТЬ ЗАКАЗ ПО EXTERNAL ID
    # ==========================================
    
    @staticmethod
    async def get_order_by_external_id(
        external_id: str, 
        session: AsyncSession
    ) -> Order:
        """Получить заказ по external ID (из Tilda)."""
        
        stmt = select(Order).where(Order.external_order_id == external_id)
        result = await session.execute(stmt)
        order = result.scalars().first()
        
        if not order:
            logger.warning("order_not_found_external", external_id=external_id)
        
        return order
    
    # ==========================================
    # ПОЛУЧИТЬ ВСЕ ЗАКАЗЫ ПОЛЬЗОВАТЕЛЯ
    # ==========================================
    
    @staticmethod
    async def get_user_orders(user_id: int, session: AsyncSession) -> list[Order]:
        """Получить все заказы пользователя."""
        
        stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        result = await session.execute(stmt)
        orders = result.scalars().all()
        
        logger.info("user_orders_fetched", user_id=user_id, count=len(orders))
        
        return orders
    
    # ==========================================
    # ПОЛУЧИТЬ НОВЫЕ ЗАКАЗЫ (для оператора)
    # ==========================================
    
    @staticmethod
    async def get_new_orders(session: AsyncSession) -> list[Order]:
        """Получить все новые заказы."""
        
        stmt = select(Order).where(Order.status == OrderStatus.NEW).order_by(Order.created_at.desc())
        result = await session.execute(stmt)
        orders = result.scalars().all()
        
        return orders
    
    # ==========================================
    # ОБНОВИТЬ СТАТУС ЗАКАЗА
    # ==========================================
    
    @staticmethod
    async def update_order_status(
        order_id: int,
        new_status: OrderStatus,
        session: AsyncSession
    ) -> Order:
        """Обновить статус заказа."""
        
        stmt = update(Order).where(Order.id == order_id).values(status=new_status)
        await session.execute(stmt)
        await session.commit()
        
        logger.info("order_status_updated", order_id=order_id, new_status=new_status.value)
        
        # Возвращаем обновленный заказ
        return await OrderService.get_order(order_id, session)
    
    # ==========================================
    # ОБНОВИТЬ ССЫЛКУ НА ОПЛАТУ
    # ==========================================
    
    @staticmethod
    async def set_payment_link(
        order_id: int,
        payment_link: str,
        session: AsyncSession
    ) -> Order:
        """Установить ссылку на оплату."""
        
        stmt = update(Order).where(Order.id == order_id).values(
            payment_link=payment_link,
            status=OrderStatus.AWAITING_PAYMENT
        )
        await session.execute(stmt)
        await session.commit()
        
        logger.info("payment_link_set", order_id=order_id)
        
        return await OrderService.get_order(order_id, session)
    
    # ==========================================
    # ПОДТВЕРДИТЬ ЗАКАЗ (оператор)
    # ==========================================
    
    @staticmethod
    async def confirm_order(
        order_id: int,
        session: AsyncSession
    ) -> Order:
        """Подтвердить заказ (оператор нажимает кнопку 'Подтвердить')."""
        
        stmt = update(Order).where(Order.id == order_id).values(
            status=OrderStatus.WAITING_OPERATOR
        )
        await session.execute(stmt)
        await session.commit()
        
        logger.info("order_confirmed", order_id=order_id)
        
        return await OrderService.get_order(order_id, session)
    
    # ==========================================
    # ОТМЕНИТЬ ЗАКАЗ
    # ==========================================
    
    @staticmethod
    async def cancel_order(
        order_id: int,
        session: AsyncSession
    ) -> Order:
        """Отменить заказ."""
        
        stmt = update(Order).where(Order.id == order_id).values(
            status=OrderStatus.CANCELLED
        )
        await session.execute(stmt)
        await session.commit()
        
        logger.info("order_cancelled", order_id=order_id)
        
        return await OrderService.get_order(order_id, session)
    
    # ==========================================
    # ОТМЕТИТЬ КАК ДОСТАВЛЕНО
    # ==========================================
    
    @staticmethod
    async def mark_as_delivered(
        order_id: int,
        session: AsyncSession
    ) -> Order:
        """Отметить заказ как доставленный."""
        
        stmt = update(Order).where(Order.id == order_id).values(
            status=OrderStatus.COMPLETED
        )
        await session.execute(stmt)
        await session.commit()
        
        logger.info("order_delivered", order_id=order_id)
        
        return await OrderService.get_order(order_id, session)
    
    # ==========================================
    # СТАТИСТИКА
    # ==========================================
    
    @staticmethod
    async def get_statistics(session: AsyncSession) -> dict:
        """Получить статистику по заказам."""
        
        stats = {}
        
        for status in OrderStatus:
            stmt = select(Order).where(Order.status == status)
            result = await session.execute(stmt)
            count = len(result.scalars().all())
            stats[status.value] = count
        
        return stats
```

## ./app/bot/utils/__init__.py
```python
# app/bot/utils/__init__.py
"""Инициализация утилит."""

from .phone import format_phone, validate_phone
from .text import escape_html, truncate

__all__ = [
    "format_phone",
    "validate_phone",
    "escape_html",
    "truncate",
]
```

## ./app/bot/utils/phone.py
```python
# app/bot/utils/phone.py
"""
Утилиты для работы с номерами телефонов.

Проблема: пользователи вводят номера в разных форматах:
- 79991234567 (без плюса)
- +79991234567 (с плюсом)
- 89991234567 (со старым кодом России)
- +7 999 123 45 67 (с пробелами)

Наша функция normalize_phone приводит все к единому формату: +79991234567
"""

import re


def normalize_phone(phone: str) -> str:
    """
    Приводит номер телефона к единому формату: +7XXXXXXXXXX
    
    Примеры:
        normalize_phone("79991234567") → "+79991234567"
        normalize_phone("+79991234567") → "+79991234567"
        normalize_phone("89991234567") → "+79991234567" (заменяет 8 на 7)
        normalize_phone("+7 999 123 45 67") → "+79991234567" (убирает пробелы)
    
    Алгоритм:
    1. Оставляем только цифры и плюс
    2. Если начинается с 8, заменяем на 7
    3. Добавляем плюс в начало если его нет
    """
    
    # Шаг 1: убираем всё кроме цифр и плюса
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # re.sub = регулярное выражение "заменить"
    
    # r'[^\d+]' = "всё что НЕ цифра и НЕ плюс"
    
    # '' = заменяем на пусто
    
    
    # Шаг 2: если начинается с 8, заменяем на 7 (старый формат России)
    
    if cleaned.startswith('8'):
        cleaned = '7' + cleaned[1:]  
        # cleaned[1:] = всё кроме первого символа
    
    
    # Шаг 3: добавляем плюс в начало
    
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    return cleaned


def phones_match(phone1: str, phone2: str) -> bool:
    """
    Проверяет, совпадают ли два номера телефона (после нормализации).
    
    Пример:
        phones_match("79991234567", "+79991234567") → True
        phones_match("89991234567", "+79991234567") → True
        phones_match("+79991234567", "+79991234567") → True
        phones_match("+79991234567", "+79991111111") → False
    
    Используем для проверки: номер в форме Tilda совпадает с номером в Telegram?
    """
    
    try:
        
        # Нормализуем оба номера
        norm_phone1 = normalize_phone(phone1)
        norm_phone2 = normalize_phone(phone2)
        
        # Сравниваем нормализованные версии
        
        return norm_phone1 == norm_phone2
    
    except:
        
        # Если ошибка (например, невалидный номер), возвращаем False
        
        return False

```

## ./app/bot/utils/text.py
```python
# app/bot/utils/text.py
"""
Утилиты для форматирования текстов.

Вместо того чтобы писать одни и те же тексты везде в коде,
создаем функции которые возвращают готовые тексты.

Это удобно потом потому что:
1. Если нужно изменить текст, меняем в одном месте
2. Форматирование не разбросано по всему коду
3. Легче переводить на другие языки
"""

from infrastructure.database.models import Order


def format_items(items: list) -> str:
    """
    Форматирует список товаров для вывода в сообщение.
    
    На вход получает JSON:
    [
        {"title": "Пицца ", "price": 690, "quantity": 1},
        {"title": "Кола ", "price": 500, "quantity": 1}
    ]
    
    На выходе дает красивый текст:
    • Пицца x1 — 690₽
    • Кола x1 — 500₽
    """
    
    if not items:
        return "Товары не указаны"
    
    lines = []
    
    for i, item in enumerate(items, 1):  
        # enumerate(items, 1) = нумерация с 1
        title = item.get("title", "Товар")  
        # item.get = безопасное получение значения
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        line = f"• {title} x{qty} — {price}₽"
        lines.append(line)
    
    # Объединяем все строки перечислением
    
    return "\n".join(lines)


def order_card_text(order: Order, for_operator: bool = False) -> str:
    """
    Генерирует текст карточки заказа.
    
    На вход: объект Order
    На выход: красиво отформатированный текст
    
    Пример для клиента:
        🛒 Заказ 2067628905
        
        👤 Иван
        📞 +79991234567
        📍 ул. Ленина, 10
        
        🛍️ Состав заказа:
        • Пицца x1 — 690₽
        • Кола x1 — 500₽
        
        💰 Сумма: 1190₽
    
    Пример для оператора (больше информации):
        (всё то же самое +)
        
        📊 Статус: waiting_operator
        📱 Подтвержденный номер: +79991234567
    """
    items_text = format_items(order.items)
    
    # Базовый текст (для всех)
    base_text = (
        f"🛒 Заказ {order.external_order_id}\n\n"
        f"👤 {order.tilda_name}\n"
        f"📞 {order.tilda_phone}\n"
        f"📍 {order.address}\n\n"
        f"🛍️ Состав заказа:\n{items_text}\n\n"
        f"💰 Сумма: {order.base_amount}₽"
    )
    
    # Если это для оператора, добавляем дополнительную информацию
    
    if for_operator:
        base_text += f"\n\n📊 Статус: {order.status.value}"
        
        if order.confirmed_phone:
            base_text += f"\n📱 Подтвержденный номер: {order.confirmed_phone}"
    
    return base_text


def operator_message_template(order: Order) -> str:
    """
    Шаблон сообщения от оператора к клиенту.
    
    Оператор может скопировать этот текст и отправить клиенту.
    
    Пример:
        Добрый день! Доставка Чанг 🍕
        
        От вас поступил заказ на сумму 1190₽
        Доставка по тарифам Яндекс Go до указанного адреса: 300₽
        
        Итого: 1490₽
        
        Если вам всё подходит, нажмите кнопку ниже ✅
    """
    delivery_cost = order.delivery_cost or 0   
    # Если доставка ещё не рассчитана, 0
    total = order.base_amount + delivery_cost
    
    return (
        f"Добрый день! Доставка Чанг 🍕\n\n"
        f"От вас поступил заказ на сумму {order.base_amount}₽\n"
        f"Доставка по тарифам Яндекс Go до указанного адреса: {delivery_cost}₽\n\n"
        f"Итого: {total}₽\n\n"
        f"Если вам всё подходит, нажмите кнопку ниже ✅"
    )

```

## ./app/models.py
```python
# app/models.py
"""
📊 МОДЕЛИ ДАННЫХ (SQLAlchemy)

Определяем структуру таблиц в БД:
- User (пользователи)
- Order (заказы)
- OrderItem (товары в заказе)
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
)
from sqlalchemy.orm import relationship

from infrastructure.database.base import Base

# ==========================================
# USER (Пользователи/Клиенты)
# ==========================================

class User(Base):
    """
    Модель пользователя.
    
    Хранит информацию о клиентах которые оформили заказ.
    """
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=True)  # ID в Telegram если есть
    name = Column(String(255), nullable=False)                 # Имя клиента
    phone = Column(String(20), nullable=False)                 # Телефон
    email = Column(String(255), nullable=True)                 # Email
    created_at = Column(DateTime, default=datetime.utcnow)     # Когда создан
    
    # Отношение к заказам
    orders = relationship("Order", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', phone='{self.phone}')>"

# ==========================================
# ORDER (Заказы)
# ==========================================

class Order(Base):
    """
    Модель заказа.
    
    Информация о каждом заказе оформленном на сайте.
    """
    
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True)
    tilda_order_id = Column(String(255), unique=True, nullable=False)  # ID заказа из Tilda
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # Кто заказал
    total_price = Column(Float, nullable=False)                         # Сумма заказа
    status = Column(String(50), default="new")                          # Статус (new, paid, shipped, etc)
    payment_status = Column(String(50), default="unpaid")               # Оплачено ли
    notes = Column(Text, nullable=True)                                 # Комментарии/заметки
    created_at = Column(DateTime, default=datetime.utcnow)              # Когда создан
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Order(id={self.id}, tilda_id='{self.tilda_order_id}', total={self.total_price})>"

# ==========================================
# ORDERITEM (Товары в заказе)
# ==========================================

class OrderItem(Base):
    """
    Модель товара в заказе.
    
    Каждый заказ может содержать несколько товаров.
    """
    
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)  # К какому заказу относится
    product_name = Column(String(255), nullable=False)                    # Название товара
    quantity = Column(Integer, default=1)                                 # Количество
    price = Column(Float, nullable=False)                                 # Цена за единицу
    total = Column(Float, nullable=False)                                 # Сумма (quantity * price)
    
    # Отношение к заказу
    order = relationship("Order", back_populates="items")
    
    def __repr__(self):
        return f"<OrderItem(id={self.id}, product='{self.product_name}', qty={self.quantity})>"
```

## ./config/__init__.py
```python
# config/__init__.py
"""Инициализация конфига."""

from .settings import config

__all__ = ["config"]
```

## ./config/settings.py
```python
# config/settings.py
"""
Settings файл - здесь живут все настройки приложения.

Логика: когда приложение запускается, оно читает .env файл
и создает объект 'config' со всеми необходимыми значениями.

Если какое-то значение из .env потеряется или будет неправильного типа,
Pydantic сразу выдаст ошибку и подскажет что не так.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    """
    Основной класс настроек.
    
    BaseSettings = специальный класс Pydantic который:
    1. Автоматически читает .env файл
    2. Валидирует типы (BOT_TOKEN должен быть str, API_PORT должен быть int)
    3. Выдает ошибку если обязательное поле пусто
    """
    
    # ==========================================
    # TELEGRAM BOT
    # ==========================================
    bot_token: str
    bot_username: str
    operator_telegram_id: int
    
    # ==========================================
    # DATABASE
    # ==========================================
    database_url: str
    
    # ==========================================
    # REDIS
    # ==========================================
    redis_url: str
    
    # ==========================================
    # API
    # ==========================================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_webhook_secret: str
    
    # ==========================================
    # WEBHOOK
    # ==========================================
    tilda_webhook_url: str
    webhook_signing_secret: str
    
    # ==========================================
    # ENVIRONMENT
    # ==========================================
    environment: Literal["development", "production"] = "production"
    debug: bool = False
    
    # Конфигурация Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",  # Читаем из .env файла
        extra="ignore",  # Игнорируем неизвестные переменные
        case_sensitive=False  # BOT_TOKEN == bot_token
    )

# Создаем глобальный объект config
# Используется везде в приложении: from config.settings import config
config = Settings()
```

## ./infrastructure/__init__.py
```python
# infrastructure/__init__.py
"""Инфраструктура приложения."""

from .logger import logger, setup_logging
from .redis_storage import redis_storage
from .database import engine, async_session_maker, get_db_session, init_db, close_db

__all__ = [
    "logger",
    "setup_logging",
    "redis_storage",
    "engine",
    "async_session_maker",
    "get_db_session",
    "init_db",
    "close_db",
]
```

## ./infrastructure/database/__init__.py
```python
# infrastructure/database/__init__.py
"""
🗄️ DATABASE ИНИЦИАЛИЗАЦИЯ

Экспортируем все нужные функции и объекты.
"""

from infrastructure.database.base import (
    Base,
    engine,
    async_session_maker,
    get_db_session,
    init_db,
    close_db,
)

__all__ = [
    "Base",
    "engine",
    "async_session_maker",
    "get_db_session",
    "init_db",
    "close_db",
]
```

## ./infrastructure/database/base.py
```python
# infrastructure/database/base.py
"""
🗄️ DATABASE - Base и Engine

Этот файл устанавливает соединение с PostgreSQL
и создает "сессии" (объекты для работы с БД).

async = асинхронное (неблокирующее) выполнение
Это позволяет серверу обрабатывать много запросов одновременно.
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,     
    async_sessionmaker,      
    AsyncSession             
)
from sqlalchemy.orm import declarative_base

from config.settings import config

# ==========================================
# BASE для моделей (БЕЗ циклического импорта!)
# ==========================================

Base = declarative_base()

# ==========================================
# СОЗДАЕМ АСИНХРОННЫЙ ENGINE (соединение с БД)
# ==========================================

engine = create_async_engine(
    config.database_url,  
    echo=config.debug,    
    pool_size=20,         
    max_overflow=10,      
    pool_pre_ping=True    
)

# ==========================================
# СОЗДАЕМ SESSION MAKER (фабрика для создания сессий)
# ==========================================

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,      
    expire_on_commit=False,   
    autoflush=False,          
    autocommit=False          
)

# ==========================================
# ФУНКЦИЯ: Dependency Injection для FastAPI/aiogram
# ==========================================

async def get_db_session() -> AsyncSession:
    """
    Эта функция создает новую сессию БД для каждого запроса.
    
    После завершения функции сессия автоматически закрывается.
    """
    
    async with async_session_maker() as session:
        yield session

# ==========================================
# ФУНКЦИЯ: Инициализация БД (создание таблиц)
# ==========================================

async def init_db():
    """
    Создает все таблицы в БД.
    Запускается один раз при старте приложения.
    """
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ==========================================
# ФУНКЦИЯ: Закрытие соединения с БД
# ==========================================

async def close_db():
    """
    Закрывает все соединения с БД.
    Запускается при выключении приложения.
    """
    
    await engine.dispose()
```

## ./infrastructure/database/models.py
```python
# infrastructure/database/models.py
"""
Здесь мы описываем структуру таблиц в базе данных.
SQLAlchemy автоматически создаст эти таблицы при первом запуске.

Каждый класс = одна таблица в БД
Каждое поле класса = один столбец в таблице
"""

from sqlalchemy import (
    BigInteger,    # Большие целые числа (для Telegram ID)
    Integer,       # Целые числа
    String,        # Текст фиксированной длины
    Text,          # Текст любой длины
    DateTime,      # Дата и время
    ForeignKey,    # Связь с другой таблицей
    Enum,          # Перечисление (выбор из нескольких вариантов)
    Boolean,       # Логическое значение (true/false)
    DECIMAL,       # Числа с плавающей запятой (для денег!)
    JSON,          # JSON данные (для массивов, объектов)
    Column         # Определение столбца
)

from sqlalchemy.orm import declarative_base, relationship

from datetime import datetime

from enum import Enum as PyEnum

# Base — базовый класс для всех моделей
# Всем моделям нужно наследоваться от Base
Base = declarative_base()


# ==========================================
# ENUMS (Перечисления)
# ==========================================

class UserRole(str, PyEnum):
    """
    Роль пользователя.
    Может быть либо клиент, либо оператор.
    """
    CLIENT = "client"       # Обычный клиент, который заказывает еду
    OPERATOR = "operator"   # Менеджер доставки, который обрабатывает заказы


class OrderStatus(str, PyEnum):
    """
    Статусы заказа (по какой стадии заказ находится).
    """
    NEW = "new"                           
    # Только что создан из вебхука
    AWAITING_CONFIRMATION = "awaiting_confirmation"   
    # Ждет подтверждения в боте
    WAITING_OPERATOR = "waiting_operator"   
    # Клиент подтвердил номер, ждет оператора
    AWAITING_PAYMENT = "awaiting_payment"   
    # Оператор отправил условия доставки
    PAID = "paid"                         
    # Клиент оплатил
    IN_DELIVERY = "in_delivery"           
    # Курьер доставляет
    COMPLETED = "completed"               
    # Успешно доставлено
    CANCELLED = "cancelled"               
    # Отменено


# ==========================================
# МОДЕЛЬ: User (Таблица users)
# ==========================================

class User(Base):
    """
    Таблица пользователей.
    Хранит информацию о клиентах и операторе.
    
    В БД будет создана таблица "users" с такими столбцами:
    - user_id (PRIMARY KEY, BIGINT)
    - username (VARCHAR, UNIQUE)
    - first_name (VARCHAR)
    - last_name (VARCHAR)
    - phone (VARCHAR)
    - role (ENUM)
    - created_at (TIMESTAMP)
    - updated_at (TIMESTAMP)
    """
    __tablename__ = "users"   # Имя таблицы в БД
    
    # Столбцы таблицы
    user_id = Column(
        BigInteger,
        primary_key=True  
        # Первичный ключ (уникальный ID)
    )  
    # Telegram ID пользователя
    
    username = Column(
        String,
        nullable=True,  
        # Может быть пусто (не обязательное поле)
        unique=True  
        # Не может быть дубликатов
    )  
    # Username в Telegram (вроде @ivan_petrov)
    
    first_name = Column(String)  
    # Имя (ОБЯЗАТЕЛЬНОЕ)
    
    last_name = Column(
        String,
        nullable=True  
        # Может быть пусто
    )  
    # Фамилия
    
    phone = Column(
        String,
        nullable=True  
        # Может быть пусто до подтверждения
    )  
    # Номер телефона (подтвержденный)
    
    role = Column(
        Enum(UserRole),
        default=UserRole.CLIENT  
        # По умолчанию все клиенты
    )  
    # Роль : client или operator
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow  
        # Автоматически ставится текущее время при создании
    )  
    # Когда создан аккаунт
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow  
        # Обновляется каждый раз при изменении
    )  
    # Когда последний раз обновлен
    
    # Связи с другими таблицами (один юзер может иметь много заказов)
    orders = relationship(
        "Order",  
        # Связь с моделью Order
        back_populates="user"   
        # Обратная ссылка (order.user будет работать)
    )
    messages = relationship("Message", back_populates="sender")


# ==========================================
# МОДЕЛЬ: Order (Таблица orders)
# ==========================================

class Order(Base):
    """
    Таблица заказов.
    Хранит информацию о каждом заказе.
    
    Примерно так это выглядит в БД:
    id | external_order_id | user_id | tilda_name | tilda_phone | ... | status
    1  | 2067628905        | 123456  | Иван        | +79991234567| ... | paid
    """
    __tablename__ = "orders"
    
    # Столбцы
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True  
        # Автоматически увеличивается
    )  
    # Внутренний ID (от 1, 2, 3...)
    
    external_order_id = Column(
        String,
        unique=True,  
        # Не может быть двух одинаковых ID
        index=True    
        # Индекс для быстрого поиска
    )  
    # ID заказа из Tilda (вроде 2067628905)
    
    user_id = Column(
        BigInteger,
        ForeignKey("users.user_id"),  
        # Связь с таблицей users
        nullable=True  
        # Может быть пусто, пока клиент не подтвердит телефон
    )  
    # Кто создал заказ (ID в Telegram)
    
    
    # ==========================================
    # данные из Tilda (при создании заказа)
    # ==========================================
    tilda_name = Column(String)  
    # Имя из формы Tilda
    tilda_phone = Column(String)  
    # Номер телефона из формы Tilda
    address = Column(Text)  
    # Адрес доставки
    items = Column(JSON)  
    # Товары в виде JSON:
    # [
    #   {"title": "Пицца ", "price": 690, "quantity": 1},
    #   {"title": "Кола ", "price": 500, "quantity": 1}
    # ]
    base_amount = Column(DECIMAL(10, 2))  
    # Сумма заказа (без доставки)
    
    
    # ==========================================
    # Подтвержденные данные (после подтверждения клиентом)
    # ==========================================
    confirmed_phone = Column(
        String,
        nullable=True  
        # Пусто, пока клиент не подтвердит
    )  
    # Номер, подтвержденный клиентом в боте
    
    
    # ==========================================
    # Информация о доставке
    # ==========================================
    delivery_cost = Column(
        DECIMAL(10, 2),
        nullable=True  
        # Пусто, пока оператор не рассчитает
    )  
    # Стоимость доставки
    
    total_amount = Column(
        DECIMAL(10, 2),
        nullable=True  
        # Пусто, пока не посчитается
    )  
    # Итоговая сумма (заказ + доставка)
    
    
    # ==========================================
    # Ссылки на платежи и трекинг
    # ==========================================
    payment_link = Column(
        String,
        nullable=True  
        # Пусто, пока оператор не создаст ссылку
    )  
    # Ссылка на оплату
    
    tracking_link = Column(
        String,
        nullable=True  
        # Пусто, пока курьер не выехал
    )  
    # Ссылка на трекинг Яндекс.Go
    
    
    # ==========================================
    # Статус и время
    # ==========================================
    status = Column(
        Enum(OrderStatus),
        default=OrderStatus.NEW,
        index=True  
        # Индекс для быстрого фильтра по статусу
    )  
    # Текущий статус заказа
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )  
    # Когда создан
    
    confirmed_at = Column(
        DateTime,
        nullable=True
    )  
    # Когда подтвержден
    
    paid_at = Column(
        DateTime,
        nullable=True
    )  
    # Когда оплачен
    
    completed_at = Column(
        DateTime,
        nullable=True
    )  
    # Когда завершен
    
    # Связи
    user = relationship("User", back_populates="orders")
    messages = relationship("Message", back_populates="order")


# ==========================================
# МОДЕЛЬ: Message (Таблица messages)
# ==========================================

class Message(Base):
    """
    Таблица сообщений.
    Хранит историю переписки между оператором и клиентом.
    """
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    order_id = Column(
        Integer,
        ForeignKey("orders.id")  
        # К какому заказу относится сообщение
    )
    
    sender_id = Column(
        BigInteger,
        ForeignKey("users.user_id")  
        # Кто отправил сообщение
    )
    
    text = Column(Text)  
    # Содержание сообщения
    
    direction = Column(String)  
    # Направление:
    # "to_client" = от оператора к клиенту
    # "to_operator" = от клиента к оператору
    
    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )  
    # Когда отправлено
    
    # Связи
    order = relationship("Order", back_populates="messages")
    sender = relationship("User", back_populates="messages")

```

## ./infrastructure/database/repositories.py
```python
# infrastructure/database/repositories.py
"""
Repository паттерн.

Вместо того чтобы писать:
    session.execute(select(...))
    session.commit()
везде в коде, мы создаем методы:
    repo.get_user(123)
    repo.create_order(...)

Это делает код чище и безопаснее.
"""

from sqlalchemy.ext.asyncio import AsyncSession  
# Асинхронная сессия БД

from sqlalchemy import select, update  
# Функции для написания SQL

from .models import User, Order, Message, UserRole, OrderStatus  
# Модели

from typing import Optional

import structlog  

logger = structlog.get_logger()


# ==========================================
# REPOSITORY: User (работа с пользователями)
# ==========================================

class UserRepository:
    """
    Репозиторий для работы с пользователями.
    Все операции с юзерами идут через этот класс.
    """
    
    def __init__(self, session: AsyncSession):
        """При создании репозитория передаем сессию БД"""
        self.session = session
    
    async def get_or_create(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = ""
    ) -> User:
        """
        Получить пользователя из БД, или создать если его нет.
        
        Логика:
        1. Ищем юзера по user_id в БД
        2. Если найден:
           - Обновляем его данные если они изменились
           - Возвращаем юзера
        3. Если не найден:
           - Создаем нового юзера
           - Сохраняем в БД
           - Возвращаем нового юзера
        
        Пример:
            repo = UserRepository(session)
            user = await repo.get_or_create(
                user_id=123456789,
                username="ivan_petrov",
                first_name="Иван"
            )
        """
        
        # Запрос: SELECT * FROM users WHERE user_id = ?
        stmt = select(User).where(User.user_id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalars().first()  
        # Получить первый результат или None
        
        
        if user:
            
            # Пользователь уже есть в БД
            
            # Обновляем данные если они изменились
            if username and not user.username:  
                # Если new username есть а у юзера нет
                user.username = username
            if first_name and not user.first_name:
                user.first_name = first_name
            self.session.add(user)  
            # Добавляем в сессию (для отслеживания изменений)
        
        else:
            
            # Пользователя нет, создаем нового
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                role=UserRole.CLIENT  
                # Все новые = клиенты
            )
            self.session.add(user)  
            # Добавляем в сессию
            logger.info("user_created", user_id=user_id, username=username)
        
        await self.session.commit()  
        # Сохраняем все изменения в БД
        
        return user
    
    async def update_phone(self, user_id: int, phone: str) -> User:
        """
        Обновить номер телефона пользователя.
        
        Пример:
            user = await repo.update_phone(123456789, "+79991234567")
        """
        
        # UPDATE users SET phone = ? WHERE user_id = ?
        stmt = update(User).where(User.user_id == user_id).values(phone=phone)
        
        await self.session.execute(stmt)
        
        await self.session.commit()
        
        # Получаем обновленного юзера и возвращаем
        stmt = select(User).where(User.user_id == user_id)
        result = await self.session.execute(stmt)
        
        return result.scalars().first()
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Получить пользователя по ID.
        
        Пример:
            user = await repo.get_by_id(123456789)
            if user:
                print(user.username)
            else:
                print("Пользователь не найден")
        """
        stmt = select(User).where(User.user_id == user_id)
        result = await self.session.execute(stmt)
        
        return result.scalars().first()


# ==========================================
# REPOSITORY: Order (работа с заказами)
# ==========================================

class OrderRepository:
    """
    Репозиторий для работы с заказами.
    Все CRUD операции с заказами идут через этот класс.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_from_webhook(
        self,
        external_order_id: str,  
        # ID из Tilda
        tilda_name: str,         
        # Имя из формы
        tilda_phone: str,        
        # Телефон из формы
        address: str,            
        # Адрес
        items: list,             
        # Товары
        base_amount: float        
        # Сумма
    ) -> Order:
        """
        Создать заказ из вебхука Tilda.
        
        Вебхук приходит когда пользователь оформляет заказ на сайте.
        Мы сохраняем эти данные в БД.
        
        Пример:
            order = await repo.create_from_webhook(
                external_order_id="2067628905",
                tilda_name="Иван",
                tilda_phone="+79991234567",
                address="ул. Ленина, 10",
                items=[...],
                base_amount=3010
            )
        """
        
        # Создаем новый заказ
        order = Order(
            external_order_id=external_order_id,
            tilda_name=tilda_name,
            tilda_phone=tilda_phone,
            address=address,
            items=items,
            base_amount=base_amount,
            status=OrderStatus.NEW  
            # Статус: только что создан
        )
        self.session.add(order)
        
        await self.session.commit()
        
        logger.info("order_created_from_webhook", external_order_id=external_order_id)
        
        return order
    
    async def get_by_external_id(self, external_order_id: str) -> Optional[Order]:
        """
        Получить заказ по ID из Tilda.
        
        Пример:
            order = await repo.get_by_external_id("2067628905")
        """
        stmt = select(Order).where(Order.external_order_id == external_order_id)
        result = await self.session.execute(stmt)
        
        return result.scalars().first()
    
    async def get_by_id(self, order_id: int) -> Optional[Order]:
        """
        Получить заказ по внутреннему ID.
        
        Пример:
            order = await repo.get_by_id(1)
        """
        stmt = select(Order).where(Order.id == order_id)
        result = await self.session.execute(stmt)
        
        return result.scalars().first()
    
    async def link_user(
        self,
        order_id: int,
        user_id: int,
        confirmed_phone: str
    ) -> Order:
        """
        Привязать заказ к пользователю Telegram.
        
        Когда клиент подтверждает номер телефона в боте,
        мы связываем его Telegram-аккаунт с заказом.
        
        Также меняем статус на WAITING_OPERATOR
        (ждем, пока оператор посчитает доставку).
        
        Пример:
            order = await repo.link_user(1, 123456789, "+79991234567")
        """
        stmt = update(Order).where(Order.id == order_id).values(
            user_id=user_id,
            confirmed_phone=confirmed_phone,
            status=OrderStatus.WAITING_OPERATOR
        )
        
        await self.session.execute(stmt)
        
        await self.session.commit()
        
        return await self.get_by_id(order_id)
    
    async def update_status(self, order_id: int, status: OrderStatus) -> Order:
        """
        Обновить статус заказа.
        
        Вызываем это когда меняется статус:
        - AWAITING_PAYMENT = когда оператор отправил условия доставки
        - PAID = когда клиент оплатил
        - IN_DELIVERY = когда курьер выехал
        - COMPLETED = когда доставлено
        
        Пример:
            order = await repo.update_status(1, OrderStatus.PAID)
        """
        stmt = update(Order).where(Order.id == order_id).values(status=status)
        
        await self.session.execute(stmt)
        
        await self.session.commit()
        
        logger.info("order_status_updated", order_id=order_id, status=status)
        
        return await self.get_by_id(order_id)
    
    async def set_payment_link(self, order_id: int, payment_link: str) -> Order:
        """
        Сохранить ссылку на оплату.
        
        Когда оператор вводит ссылку на оплату в боте,
        мы сохраняем ее и меняем статус на AWAITING_PAYMENT.
        
        Пример:
            order = await repo.set_payment_link(1, "https://pay.yandex.ru/...")
        """
        stmt = update(Order).where(Order.id == order_id).values(
            payment_link=payment_link,
            status=OrderStatus.AWAITING_PAYMENT
        )
        
        await self.session.execute(stmt)
        
        await self.session.commit()
        
        return await self.get_by_id(order_id)
    
    async def set_tracking_link(self, order_id: int, tracking_link: str) -> Order:
        """
        Сохранить ссылку на трекинг.
        
        Когда оператор отправляет ссылку на Яндекс.Go,
        мы сохраняем ее и меняем статус на IN_DELIVERY.
        
        Пример:
            order = await repo.set_tracking_link(1, "https://yandex.go/...")
        """
        stmt = update(Order).where(Order.id == order_id).values(
            tracking_link=tracking_link,
            status=OrderStatus.IN_DELIVERY
        )
        
        await self.session.execute(stmt)
        
        await self.session.commit()
        
        return await self.get_by_id(order_id)


# ==========================================
# REPOSITORY: Message (работа с сообщениями)
# ==========================================

class MessageRepository:
    """
    Репозиторий для работы с сообщениями.
    Сохраняет историю переписки.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save(
        self,
        order_id: int,
        sender_id: int,
        text: str,
        direction: str   
        # "to_client" или "to_operator"
    ):
        """
        Сохранить сообщение в БД.
        
        Пример:
            await repo.save(
                order_id=1,
                sender_id=123456789,
                text="Ваш заказ готов!",
                direction="to_client"
            )
        """
        message = Message(
            order_id=order_id,
            sender_id=sender_id,
            text=text,
            direction=direction
        )
        self.session.add(message)
        
        await self.session.commit()
        logger.info("message_saved", order_id=order_id, direction=direction)

```

## ./infrastructure/logger.py
```python
# infrastructure/logger.py
"""
📝 ЛОГИРОВАНИЕ

Система для красивого вывода логов в консоль.
Использует structlog для структурированного логирования.
"""

import logging
import sys
from typing import Any

import structlog

# ==========================================
# ИНИЦИАЛИЗАЦИЯ STRUCTLOG
# ==========================================

def setup_logging():
    """
    Инициализирует логирование.
    
    Вызывается один раз при старте приложения.
    """
    
    # Конфигурируем structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()  # Выводит как JSON
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Конфигурируем стандартный logging
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s: %(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

# ==========================================
# ПОЛУЧЕНИЕ ЛОГГЕРА
# ==========================================

logger = structlog.get_logger()

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def log_info(message: str, **kwargs):
    """Логируем информацию."""
    logger.info(message, **kwargs)

def log_error(message: str, **kwargs):
    """Логируем ошибку."""
    logger.error(message, **kwargs)

def log_warning(message: str, **kwargs):
    """Логируем предупреждение."""
    logger.warning(message, **kwargs)

def log_debug(message: str, **kwargs):
    """Логируем отладку."""
    logger.debug(message, **kwargs)
```

## ./infrastructure/redis_storage.py
```python
# infrastructure/redis_storage.py
"""
🔴 REDIS STORAGE

Redis хранит состояния пользователей (FSM).
Когда пользователь говорит /start, /order и т.д.
Redis запоминает в каком состоянии он находится.

Пример:
- Пользователь нажал /start → состояние = "main_menu"
- Затем /order → состояние = "choosing_product"
- И т.д.

Без Redis состояния теряются при перезагрузке бота.
"""

from redis.asyncio.client import Redis
from aiogram.fsm.storage.redis import RedisStorage

from config.settings import config

# ==========================================
# ПОДКЛЮЧАЕМСЯ К REDIS
# ==========================================

# Создаём асинхронное соединение с Redis
redis = Redis.from_url(
    config.redis_url,  # Берём URL из .env (обычно redis://localhost:6379)
    encoding="utf-8",
    decode_responses=True
)

# ==========================================
# СОЗДАЁМ STORAGE ДЛЯ AIOGRAM
# ==========================================

# RedisStorage = хранилище состояний в Redis для aiogram FSM
# FSM = Finite State Machine (конечный автомат)
redis_storage = RedisStorage(redis=redis)

# ==========================================
# ФУНКЦИЯ: проверить соединение
# ==========================================

async def check_redis_connection():
    """
    Проверяет что Redis живой и отвечает.
    Вызывается при старте приложения для диагностики.
    
    Пример использования:
    try:
        await check_redis_connection()
        print("✅ Redis работает!")
    except Exception as e:
        print(f"❌ Redis не работает: {e}")
    """
    
    try:
        await redis.ping()
        return True
    except Exception as e:
        print(f"❌ Redis connection error: {e}")
        return False

# ==========================================
# ЭКСПОРТ
# ==========================================

__all__ = [
    "redis",
    "redis_storage",
    "check_redis_connection",
]
```

## ./init.py
```python
# changcafe_bot/__init__.py или в корне проекта
"""
ChangCafe Bot - Telegram бот для заказов.

Структура:
- app/ - основное приложение (бот + API)
  - bot/ - Telegram бот (handlers, middlewares, states)
  - api/ - FastAPI endpoints (webhooks от Tilda)
- config/ - конфигурация (settings.py)
- infrastructure/ - инфраструктура (БД, Redis, логирование)
"""

__version__ = "1.0.0"
__author__ = "Chang Cafe"
__description__ = "Telegram bot для заказов Chang Cafe из Tilda"
```

## ./main.py
```python
# main.py
"""
🚀 ГЛАВНЫЙ ФАЙЛ ЗАПУСКА БОТА

Это точка входа - отсюда всё начинается!

Функция: запускает бота, подключает БД, слушает команды от Tilda
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI
import uvicorn

# Импортируем свои модули
from config.settings import config
from infrastructure.logger import setup_logging, logger
from infrastructure.database import init_db, close_db
from infrastructure.redis_storage import redis_storage
from app.bot.handlers import main_router
from app.bot.middlewares import DatabaseMiddleware, LoggingMiddleware
from app.api.webhooks.tilda import router as tilda_router

# ==========================================
# 🔄 LIFESPAN (управление жизненным циклом приложения)
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Когда приложение запускается и выключается.
    
    Как жизненный цикл человека:
    - РОЖДЕНИЕ (запуск)
    - ЖИЗНЬ (основной цикл)
    - СМЕРТЬ (выключение)
    """
    
    # ========== ЗАПУСК ==========
    logger.info("app_startup", message="🟢 Инициализация приложения")
    
    # Создаём таблицы в БД если их нет
    await init_db()
    logger.info("database_initialized", message="✅ База данных готова")
    
    yield  # ← Здесь приложение работает (слушает команды)
    
    # ========== ВЫКЛЮЧЕНИЕ ==========
    logger.info("app_shutdown", message="🔴 Выключение приложения")
    
    # Закрываем соединение с БД (чистим за собой)
    await close_db()
    logger.info("database_closed", message="✅ База данных закрыта")

# ==========================================
# 🌐 СОЗДАЁМ FASTAPI ПРИЛОЖЕНИЕ
# ==========================================

app = FastAPI(
    title="ChangCafe Bot API",
    description="API для вебхуков от Tilda",
    version="1.0.0",
    lifespan=lifespan
)

# Добавляем маршруты для вебхуков (сюда будут приходить данные от Tilda)
app.include_router(tilda_router)

# ==========================================
# 🤖 BOT STARTUP & SHUTDOWN
# ==========================================

async def on_startup(bot: Bot):
    """
    Запускается когда бот стартует.
    
    Может использоваться для:
    - Уведомления оператора что бот онлайн
    - Установки кнопок меню
    - И т.д.
    """
    
    logger.info("bot_starting", message="🤖 Бот стартует...")
    
    # Уведомляем оператора что бот живой
    try:
        await bot.send_message(
            chat_id=config.operator_telegram_id,
            text="✅ <b>Бот запустился!</b>\n\nТеперь готов принимать заказы от Tilda 🎉"
        )
        logger.info("operator_notified", message="✅ Оператор уведомлен")
    except Exception as e:
        logger.error("operator_notification_failed", error=str(e))
    
    logger.info("bot_startup_complete", message="✅ Бот полностью готов")

async def on_shutdown(bot: Bot):
    """Запускается когда бот выключается."""
    logger.info("bot_shutdown", message="🔴 Бот выключается...")
    await bot.session.close()

# ==========================================
# 🚀 ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ==========================================

async def main():
    """
    Главная асинхронная функция.
    
    Здесь мы:
    1. Инициализируем логирование
    2. Создаём объект бота
    3. Запускаем бота И FastAPI одновременно
    """
    
    # Инициализируем логирование (все логи будут видны в консоли)
    setup_logging()
    logger.info("application_start", message="🟢 Приложение стартует")
    
    # Инициализируем БД
    await init_db()
    logger.info("database_initialized", message="✅ База данных готова")
    
    # Создаём объект бота (который будет отправлять/получать сообщения)
    bot = Bot(
        token=config.bot_token,  # Берём токен из .env
        default=DefaultBotProperties(parse_mode="HTML")  # Новый способ в aiogram 3.7+
    )
    
    # Создаём диспетчер (объект который управляет обработчиками)
    # RedisStorage = сохраняем состояния пользователей в Redis
    dp = Dispatcher(
        storage=redis_storage,
        bot=bot
    )
    
    # Добавляем middleware (перехватчики - они обрабатывают ВСЕ сообщения)
    dp.message.middleware(LoggingMiddleware())       # Логируем все события
    dp.message.middleware(DatabaseMiddleware())      # Подключаем БД к каждому запросу
    
    # Добавляем обработчики (команды /start, /help и т.д.)
    dp.include_router(main_router)
    
    # Запускаем startup функцию
    await on_startup(bot)
    
    # ==========================================
    # 🚀 ЗАПУСКАЕМ БОТ И FASTAPI ОДНОВРЕМЕННО
    # ==========================================
    
    async def run_bot():
        """Запуск бота"""
        try:
            logger.info("polling_started", message="👂 Бот начинает слушать сообщения...")
            await dp.start_polling(bot)
        except Exception as e:
            logger.error("bot_error", error=str(e))
            raise
        finally:
            await on_shutdown(bot)
    
    async def run_api():
        """Запуск FastAPI"""
        config_uvicorn = uvicorn.Config(
            app,
            host=config.api_host,
            port=config.api_port,
            log_level="info"
        )
        server = uvicorn.Server(config_uvicorn)
        logger.info("fastapi_started", message=f"🌐 FastAPI запущен на {config.api_host}:{config.api_port}")
        await server.serve()
    
    # Запускаем оба одновременно
    await asyncio.gather(
        run_bot(),
        run_api()
    )

# ==========================================
# 📌 ENTRY POINT (точка входа)
# ==========================================

if __name__ == "__main__":
    """
    Это срабатывает когда ты запускаешь файл напрямую.
    
    Команда для запуска:
    python main.py        (на Windows/Mac)
    python3 main.py       (на Linux)
    
    ✅ Запускаешь ВСЕ в одной команде!
    """
    
    try:
        # Запускаем основную асинхронную функцию
        asyncio.run(main())
        
    except KeyboardInterrupt:
        # Если нажал Ctrl+C
        logger.info("keyboard_interrupt", message="⛔ Бот остановлен пользователем")
    except Exception as e:
        logger.error("fatal_error", error=str(e))
        raise
```
