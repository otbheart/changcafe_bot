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
    - phone (VARCHAR, UNIQUE, INDEX)  ← ДОБАВЛЕН INDEX
    - role (ENUM, INDEX)  ← ДОБАВЛЕН INDEX
    - created_at (TIMESTAMP)
    - updated_at (TIMESTAMP)
    """
    __tablename__ = "users"   # Имя таблицы в БД
    
    # Столбцы таблицы
    user_id = Column(
        BigInteger,
        primary_key=True
    )
    # Telegram ID пользователя
    
    username = Column(
        String,
        nullable=True,
        unique=True,
        index=True  # ← ✅ ДОБАВЛЕН INDEX (для быстрого поиска по username)
    )
    # Username в Telegram (вроде @ivan_petrov)
    
    first_name = Column(String)
    # Имя (ОБЯЗАТЕЛЬНОЕ)
    
    last_name = Column(
        String,
        nullable=True
    )
    # Фамилия
    
    phone = Column(
        String,
        nullable=True,
        unique=True,
        index=True  # ← ✅ ДОБАВЛЕН INDEX (часто ищем по phone)
    )
    # Номер телефона (подтвержденный)
    
    email = Column(
        String,
        nullable=True,
        unique=True,
        index=True  # ← ✅ ДОБАВЛЕН INDEX (для быстрого поиска по email)
    )
    # Email (из Tilda)
    
    role = Column(
        Enum(UserRole),
        default=UserRole.CLIENT,
        index=True  # ← ✅ ДОБАВЛЕН INDEX (для фильтрации по роли)
    )
    # Роль: client или operator
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
    # Когда создан аккаунт
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    # Когда последний раз обновлен
    
    # Связи с другими таблицами (один юзер может иметь много заказов)
    orders = relationship(
        "Order",
        back_populates="user"
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
    id | external_order_id | user_id | tilda_name | tilda_phone | status | assigned_to | created_at
    1  | 2067628905        | 123456  | Иван       | +79991234567| paid   | 987654321   | 2024-01-21
    """
    __tablename__ = "orders"
    
    # Столбцы
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    # Внутренний ID (от 1, 2, 3...)
    
    external_order_id = Column(
        String,
        unique=True,
        index=True
    )
    # ID заказа из Tilda (вроде 2067628905)
    
    user_id = Column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=True,
        index=True  # ← ✅ ДОБАВЛЕН INDEX (часто ищем заказы юзера)
    )
    # Кто создал заказ (ID в Telegram)
    
    
    # ==========================================
    # Данные из Tilda (при создании заказа)
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
    #   {"title": "Пицца", "price": 690, "quantity": 1},
    #   {"title": "Кола", "price": 500, "quantity": 1}
    # ]
    
    base_amount = Column(DECIMAL(10, 2))
    # Сумма заказа (без доставки)
    
    
    # ==========================================
    # Подтвержденные данные (после подтверждения клиентом)
    # ==========================================
    confirmed_phone = Column(
        String,
        nullable=True
    )
    # Номер, подтвержденный клиентом в боте
    
    
    # ==========================================
    # Информация о доставке
    # ==========================================
    delivery_address = Column(
        Text,
        nullable=True
    )
    # Адрес доставки (подтвержденный)
    
    delivery_cost = Column(
        DECIMAL(10, 2),
        nullable=True
    )
    # Стоимость доставки
    
    total_amount = Column(
        DECIMAL(10, 2),
        nullable=True
    )
    # Итоговая сумма (заказ + доставка)
    
    
    # ==========================================
    # Ссылки на платежи и трекинг
    # ==========================================
    payment_link = Column(
        String,
        nullable=True
    )
    # Ссылка на оплату
    
    tracking_link = Column(
        String,
        nullable=True
    )
    # Ссылка на трекинг Яндекс.Go
    
    
    # ==========================================
    # Статус и время
    # ==========================================
    status = Column(
        Enum(OrderStatus),
        default=OrderStatus.NEW,
        index=True  # ← ✅ INDEX (часто фильтруем по статусу)
    )
    # Текущий статус заказа
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True  # ← ✅ INDEX (часто сортируем по дате)
    )
    # Когда создан
    
    confirmed_at = Column(
        DateTime,
        nullable=True,
        index=True  # ← ✅ INDEX (для аналитики)
    )
    # Когда подтвержден
    
    paid_at = Column(
        DateTime,
        nullable=True,
        index=True  # ← ✅ INDEX (для аналитики)
    )
    # Когда оплачен
    
    completed_at = Column(
        DateTime,
        nullable=True,
        index=True  # ← ✅ INDEX (для аналитики)
    )
    # Когда завершен
    
    
    # ==========================================
    # Управление заказом (НОВОЕ!)
    # ==========================================
    assigned_to = Column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=True,
        index=True  # ← ✅ INDEX (часто ищем "мои заказы")
    )
    # Кому назначен заказ (ID оператора)
    
    assigned_at = Column(
        DateTime,
        nullable=True
    )
    # Когда назначен оператору
    
    
    # Связи
    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="orders"
    )
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
        ForeignKey("orders.id"),
        index=True  # ← ✅ ДОБАВЛЕН INDEX (ищем сообщения по заказу)
    )
    # К какому заказу относится сообщение
    
    sender_id = Column(
        BigInteger,
        ForeignKey("users.user_id"),
        index=True  # ← ✅ ДОБАВЛЕН INDEX (ищем сообщения по отправителю)
    )
    # Кто отправил сообщение
    
    text = Column(Text)
    # Содержание сообщения
    
    direction = Column(String)
    # Направление:
    # "to_client" = от оператора к клиенту
    # "to_operator" = от клиента к оператору
    
    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        index=True  # ← ✅ INDEX (сортируем по времени)
    )
    # Когда отправлено
    
    # Связи
    order = relationship("Order", back_populates="messages")
    sender = relationship("User", back_populates="messages")
