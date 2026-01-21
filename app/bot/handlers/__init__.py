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
