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

