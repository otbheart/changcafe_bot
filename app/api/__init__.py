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
