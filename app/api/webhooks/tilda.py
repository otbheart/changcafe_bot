# app/api/webhooks/tilda.py
"""
Обработчик вебхука от Tilda.

Когда пользователь оформляет заказ на сайте changcafe.ru,
Tilda отправляет POST запрос на наш сервер.

Мы обрабатываем этот запрос, сохраняем заказ в БД,
и отправляем уведомление оператору.
"""

import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
import structlog

from infrastructure.database.base import async_session_maker
from infrastructure.database.repositories import OrderRepository
from app.bot.services.user_service import UserService
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
    name: str
    phone: str
    street: str
    home: str
    apartment: Optional[str] = None
    amount: Decimal
    
    class Config:
        extra = "allow"


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
    1. ✅ Проверяем подпись вебхука (SECURITY!)
    2. Получаем данные из запроса
    3. Валидируем их (проверяем что всё заполнено правильно)
    4. Проверяем что заказа ещё нет в БД (защита от дубликатов)
    5. Создаем пользователя (если нет)
    6. Создаем заказ в БД
    7. Генерируем deep link для клиента
    8. Отправляем оператору уведомление (в фоне)
    9. Возвращаем OK ответ Tilda
    """
    
    try:
        # ==========================================
        # ШАГ 1: ПРОВЕРКА ПОДПИСИ (КРИТИЧНО!)
        # ==========================================
        
        signature = request.headers.get("X-Tilda-Signature", "")
        body = await request.body()
        
        # Вычисляем ожидаемую подпись
        expected_signature = hmac.new(
            key=config.webhook_signing_secret.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # TIMING-SAFE сравнение (защита от timing attacks)
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning(
                "invalid_webhook_signature",
                provided_signature=signature[:20] + "***",
                remote_ip=request.client.host if request.client else "unknown"
            )
            raise HTTPException(403, "Invalid signature")
        
        logger.info("signature_verified", order_source="tilda")
        
        # ==========================================
        # ШАГ 2: ПОЛУЧАЕМ ДАННЫЕ
        # ==========================================
        
        # Tilda отправляет данные в формате multipart/form-data
        try:
            form_data = await request.form()
        except ValueError:
            try:
                form_data = await request.json()
            except ValueError as e:
                logger.error("invalid_webhook_format", error=str(e))
                raise HTTPException(400, "Invalid request format")
        
        logger.info(
            "tilda_webhook_received",
            form_data_keys=list(form_data.keys())
        )
        
        # ==========================================
        # ШАГ 3: ВАЛИДИРУЕМ ОБЯЗАТЕЛЬНЫЕ ПОЛЯ
        # ==========================================
        
        order_id = form_data.get("formid")
        
        if not order_id:
            logger.error("webhook_validation_failed", reason="missing_formid")
            raise HTTPException(400, "Missing formid")
        
        phone = form_data.get("phone", "")
        name = form_data.get("name", "Guest")
        
        if not phone or not name:
            logger.warning(
                "incomplete_order_data",
                order_id=order_id,
                has_phone=bool(phone),
                has_name=bool(name)
            )
        
        # ==========================================
        # ШАГ 4: РАБОТАЕМ С БД
        # ==========================================
        
        async with async_session_maker() as session:
            
            # ==========================================
            # ПРОВЕРЯЕМ ДУБЛИКАТ
            # ==========================================
            
            order_repo = OrderRepository(session)
            existing = await order_repo.get_by_external_id(order_id)
            
            if existing:
                logger.warning("duplicate_order", order_id=order_id)
                # Возвращаем OK (чтобы Tilda не пробовала ещё раз)
                return {
                    "status": "ok",
                    "message": "Already processed",
                    "order_id": order_id
                }
            
            # ==========================================
            # СОЗДАЁМ ПОЛЬЗОВАТЕЛЯ (БЕЗОПАСНО)
            # ==========================================
            
            user_service = UserService()
            user = await user_service.get_or_create_by_phone(
                session=session,
                phone=phone,
                name=name,
                email=form_data.get("email", "")
            )
            
            logger.info(
                "user_processed",
                user_id=user.user_id,
                phone=phone
            )
            
            # ==========================================
            # СОБИРАЕМ ТОВАРЫ
            # ==========================================
            
            # Tilda отправляет товары в таком формате:
            # payment[title] = "Пицца"
            # payment[price] = "690"
            # payment[quantity] = "1"
            # payment[title] = "Кола"
            # и т.д.
            
            items = []
            i = 0
            
            while f"payment[{i}][title]" in form_data:
                try:
                    items.append({
                        "title": form_data.get(f"payment[{i}][title]"),
                        "price": float(form_data.get(f"payment[{i}][price]", 0)),
                        "quantity": int(form_data.get(f"payment[{i}][quantity]", 1)),
                        "sku": form_data.get(f"payment[{i}][sku]")
                    })
                except (ValueError, TypeError) as e:
                    logger.error(
                        "item_parse_error",
                        item_index=i,
                        error=str(e)
                    )
                i += 1
            
            if not items:
                logger.warning("empty_order_items", order_id=order_id)
            
            # ==========================================
            # СОБИРАЕМ АДРЕС
            # ==========================================
            
            address_parts = [
                form_data.get("street", ""),
                f"д. {form_data.get('home', '')}"
            ]
            
            if form_data.get("apartment"):
                address_parts.append(f"кв. {form_data.get('apartment')}")
            
            full_address = ", ".join(filter(None, address_parts))
            
            # ==========================================
            # СОЗДАЁМ ЗАКАЗ В БД
            # ==========================================
            
            try:
                order = await order_repo.create_from_webhook(
                    external_order_id=order_id,
                    tilda_name=name,
                    tilda_phone=phone,
                    address=full_address,
                    items=items,
                    base_amount=float(form_data.get("amount", 0))
                )
                
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                logger.error(
                    "order_creation_failed",
                    order_id=order_id,
                    error=str(e)
                )
                raise HTTPException(500, "Failed to create order")
            
            # ==========================================
            # ГЕНЕРИРУЕМ DEEP LINK
            # ==========================================
            
            deep_link = f"https://t.me/{config.bot_username}?start=order_{order_id}"
            
            logger.info(
                "order_created",
                order_id=order_id,
                user_id=user.user_id,
                deep_link=deep_link
            )
            
            # ==========================================
            # ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ ОПЕРАТОРУ (В ФОНЕ)
            # ==========================================
            
            # background_tasks = очередь задач которые выполняются в фоне
            # Это нужно чтобы не ждать отправки уведомления перед ответом Tilda
            
            background_tasks.add_task(
                notify_operator_async,
                order_id=order_id,
                customer_name=name,
                customer_phone=phone,
                total_amount=float(form_data.get("amount", 0)),
                address=full_address
            )
        
        # ==========================================
        # ШАГ 5: ВОЗВРАЩАЕМ УСПЕШНЫЙ ОТВЕТ
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
        # FastAPI HTTPException - это intentional ошибка которую мы кидаем
        raise
    
    except Exception as e:
        # Неожиданная ошибка = логируем и возвращаем 500
        logger.error(
            "webhook_error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(500, "Internal server error")


# ==========================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: Уведомление оператору
# ==========================================

async def notify_operator_async(
    order_id: str,
    customer_name: str,
    customer_phone: str,
    total_amount: float,
    address: str
):
    """
    Отправляет уведомление оператору в фоне.
    
    Эта функция вызывается в background_tasks,
    поэтому не блокирует ответ на вебхук.
    """
    
    try:
        message_text = (
            f"🔔 <b>Новый заказ!</b>\n\n"
            f"ID: <code>{order_id}</code>\n"
            f"👤 Клиент: {customer_name}\n"
            f"📞 Телефон: {customer_phone}\n"
            f"📍 Адрес: {address}\n"
            f"💰 Сумма: {total_amount}₽\n\n"
            f"<i>Нажмите кнопку ниже чтобы принять</i>"
        )
        
        await bot.send_message(
            chat_id=config.operator_telegram_id,
            text=message_text,
            parse_mode="HTML"
        )
        
        logger.info(
            "operator_notified",
            order_id=order_id,
            operator_id=config.operator_telegram_id
        )
        
    except Exception as e:
        logger.error(
            "operator_notification_failed",
            order_id=order_id,
            error=str(e)
        )
        # Не кидаем исключение - заказ уже создан, это не критично


# ==========================================
# HEALTH CHECK ENDPOINT
# ==========================================

@router.get("/health")
async def health_check():
    """
    Проверка что вебхук живой.
    
    Используется для диагностики.
    """
    return {
        "status": "healthy",
        "endpoint": "tilda_webhook"
    }
