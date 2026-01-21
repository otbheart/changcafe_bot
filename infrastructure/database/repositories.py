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

ШАГ 2.4: ДОБАВЛЕНЫ МЕТОДЫ ДЛЯ БЫСТРОЙ ЗАГРУЗКИ ДАННЫХ (N+1 FIX)
- selectinload() для загрузки relations одним запросом
- Методы с суффиксом _with_relations() для полной информации
"""

from sqlalchemy.ext.asyncio import AsyncSession
# Асинхронная сессия БД

from sqlalchemy import select, update
# Функции для написания SQL

from sqlalchemy.orm import selectinload
# ← ✅ НОВОЕ! Для быстрой загрузки related данных

from .models import User, Order, Message, UserRole, OrderStatus
# Модели

from typing import Optional, List

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
    
    # ← ✅ НОВОЕ! Быстрая загрузка с заказами
    async def get_by_phone(self, phone: str) -> Optional[User]:
        """
        Получить пользователя по номеру телефона.
        
        Это часто вызывается из Tilda webhook.
        
        Пример:
            user = await repo.get_by_phone("+79991234567")
        """
        stmt = select(User).where(User.phone == phone)
        result = await self.session.execute(stmt)
        
        return result.scalars().first()
    
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


# ==========================================
# REPOSITORY: Order (работа с заказами)
# ==========================================

class OrderRepository:
    """
    Репозиторий для работы с заказами.
    Все CRUD операции с заказами идут через этот класс.
    
    ВАЖНО: Используй методы с суффиксом _with_relations()
    для загрузки заказа с пользователем и сообщениями одним запросом.
    Это избегает N+1 Query Problem.
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
    
    # ← ✅ НОВОЕ! Быстрая загрузка с related данными (N+1 FIX)
    async def get_by_id_with_relations(self, order_id: int) -> Optional[Order]:
        """
        Получить заказ со ВСЕМИ связанными данными одним запросом.
        
        ❌ БЕЗ selectinload (N+1 проблема):
        order = await repo.get_by_id(1)
        print(order.user.username)  # ← Второй запрос к БД!
        print(order.messages.text)  # ← Третий запрос к БД!
        
        ✅ С selectinload (быстро):
        order = await repo.get_by_id_with_relations(1)
        print(order.user.username)  # ← Уже загружено в памяти
        print(order.messages.text)  # ← Уже загружено в памяти
        
        Пример:
            order = await repo.get_by_id_with_relations(1)
            # Одним запросом загрузили:
            # - сам заказ
            # - пользователя (order.user)
            # - все сообщения (order.messages)
        """
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.user),  # ← Загруз пользователя
                selectinload(Order.messages)  # ← Загруз все сообщения
            )
        )
        result = await self.session.execute(stmt)
        
        return result.scalars().first()
    
    # ← ✅ НОВОЕ! Получить новые заказы (для оператора)
    async def get_new_orders(self, limit: int = 10) -> List[Order]:
        """
        Получить список НОВЫХ заказов для оператора.
        
        Вызывается когда оператор кликает "Посмотреть новые заказы".
        
        Пример:
            orders = await repo.get_new_orders(limit=20)
            for order in orders:
                print(f"ID: {order.id}, Клиент: {order.tilda_name}")
        """
        stmt = (
            select(Order)
            .where(Order.status == OrderStatus.NEW)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .options(
                selectinload(Order.user),  # Загруз пользователя
                selectinload(Order.messages)  # Загруз сообщения
            )
        )
        result = await self.session.execute(stmt)
        
        return result.scalars().all()
    
    # ← ✅ НОВОЕ! Получить заказы оператора
    async def get_operator_orders(
        self,
        operator_id: int,
        status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """
        Получить ВСЕ заказы, назначенные оператору.
        
        Оператор видит только "свои" заказы, которые ему назначены.
        
        Пример:
            # Все заказы оператора
            orders = await repo.get_operator_orders(operator_id=987654321)
            
            # Только активные заказы оператора
            orders = await repo.get_operator_orders(
                operator_id=987654321,
                status=OrderStatus.IN_DELIVERY
            )
        """
        stmt = select(Order).where(Order.assigned_to == operator_id)
        
        # Если передали статус - фильтруем еще и по статусу
        if status:
            stmt = stmt.where(Order.status == status)
        
        stmt = (
            stmt
            .order_by(Order.created_at.desc())
            .options(
                selectinload(Order.user),
                selectinload(Order.messages)
            )
        )
        result = await self.session.execute(stmt)
        
        return result.scalars().all()
    
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
        
        return await self.get_by_id_with_relations(order_id)
    
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
        
        return await self.get_by_id_with_relations(order_id)
    
    # ← ✅ НОВОЕ! Назначить заказ оператору
    async def assign_to_operator(
        self,
        order_id: int,
        operator_id: int
    ) -> Order:
        """
        Назначить заказ оператору.
        
        Оператор кликает "Взять заказ" и заказ становится его.
        
        Пример:
            order = await repo.assign_to_operator(
                order_id=1,
                operator_id=987654321
            )
        """
        from datetime import datetime
        
        stmt = update(Order).where(Order.id == order_id).values(
            assigned_to=operator_id,
            assigned_at=datetime.utcnow()
        )
        
        await self.session.execute(stmt)
        
        await self.session.commit()
        
        logger.info(
            "order_assigned",
            order_id=order_id,
            operator_id=operator_id
        )
        
        return await self.get_by_id_with_relations(order_id)
    
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
        
        return await self.get_by_id_with_relations(order_id)
    
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
        
        return await self.get_by_id_with_relations(order_id)


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
    
    # ← ✅ НОВОЕ! Получить историю переписки
    async def get_order_messages(self, order_id: int) -> List[Message]:
        """
        Получить ВСЮ историю переписки по заказу.
        
        Вызывается когда открываем детали заказа.
        
        Пример:
            messages = await repo.get_order_messages(order_id=1)
            for msg in messages:
                print(f"{msg.sender_id}: {msg.text}")
        """
        stmt = (
            select(Message)
            .where(Message.order_id == order_id)
            .order_by(Message.timestamp.asc())
            .options(
                selectinload(Message.sender)  # Загруз отправителя
            )
        )
        result = await self.session.execute(stmt)
        
        return result.scalars().all()
