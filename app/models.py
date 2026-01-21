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
