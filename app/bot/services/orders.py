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
