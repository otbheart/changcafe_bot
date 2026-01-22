# main.py
"""
🚀 ГЛАВНЫЙ ФАЙЛ ЗАПУСКА

Это точка входа - отсюда всё начинается!

Функция: запускает API сервер и опционально бота, подключает БД
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from config.settings import config
from infrastructure.logger import setup_logging
from infrastructure.database.base import init_db, close_db

import structlog

logger = structlog.get_logger()


# ==========================================
# 🔄 LIFESPAN (управление жизненным циклом приложения)
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Когда приложение запускается и выключается.
    """
    
    logger.info("app_startup", message="🟢 Инициализация приложения")
    
    try:
        await init_db()
        logger.info("database_initialized", message="✅ База данных готова")
        
        yield
    
    finally:
        logger.info("app_shutdown", message="🔴 Выключение приложения")
        
        try:
            await close_db()
            logger.info("database_closed", message="✅ База данных закрыта")
        except Exception as e:
            logger.error("database_close_error", error=str(e))


# ==========================================
# 🌐 СОЗДАЁМ FASTAPI ПРИЛОЖЕНИЕ
# ==========================================

app = FastAPI(
    title="ChangCafe Bot API",
    description="API для вебхуков от Tilda",
    version="1.0.0",
    lifespan=lifespan
)


# ==========================================
# HEALTH CHECK ENDPOINT
# ==========================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "ok",
        "service": "ChangCafe Bot API",
        "message": "Welcome to ChangCafe Bot API"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "changcafe_bot"
    }


# ==========================================
# INCLUDE ROUTERS
# ==========================================

try:
    from app.api.webhooks.tilda import router as tilda_router
    app.include_router(tilda_router, prefix="/api")
except ImportError as e:
    logger.warning("tilda_router_import_failed", error=str(e))


# ==========================================
# 🚀 ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ==========================================

async def run_api():
    """
    Запуск FastAPI сервера.
    """
    setup_logging()
    logger.info("application_start", message="🟢 Приложение стартует")
    
    config_uvicorn = uvicorn.Config(
        app,
        host=config.api_host,
        port=config.api_port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config_uvicorn)
    logger.info(
        "fastapi_starting",
        message=f"🌐 FastAPI запускается на {config.api_host}:{config.api_port}"
    )
    await server.serve()


async def run_bot():
    """
    Запуск Telegram бота (опционально).
    Требует BOT_TOKEN в переменных окружения.
    """
    if not config.bot_token:
        logger.warning("bot_token_missing", message="⚠️ BOT_TOKEN не установлен, бот не запущен")
        return
    
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.client.default import DefaultBotProperties
        from infrastructure.redis_storage import redis_storage
        from app.bot.handlers.operator import router as operator_router
        from app.bot.handlers.client import router as client_router
        from app.bot.middlewares import DatabaseMiddleware, LoggingMiddleware
        
        bot = Bot(
            token=config.bot_token,
            default=DefaultBotProperties(parse_mode="HTML")
        )
        
        dp = Dispatcher(
            storage=redis_storage,
            bot=bot
        )
        
        dp.message.middleware(LoggingMiddleware())
        dp.message.middleware(DatabaseMiddleware())
        dp.include_router(operator_router)
        dp.include_router(client_router)
        
        if config.operator_telegram_id:
            try:
                await bot.send_message(
                    chat_id=config.operator_telegram_id,
                    text="✅ <b>Бот запустился!</b>\n\nТеперь готов принимать заказы от Tilda 🎉",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning("operator_notification_failed", error=str(e))
        
        logger.info("bot_starting", message="🤖 Бот стартует...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error("bot_error", error=str(e))
        raise


async def main():
    """
    Главная асинхронная функция.
    """
    setup_logging()
    
    await init_db()
    
    tasks = [run_api()]
    
    if config.bot_token:
        tasks.append(run_bot())
    
    try:
        await asyncio.gather(*tasks, return_exceptions=False)
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt", message="⛔ Приложение остановлено пользователем")
    except Exception as e:
        logger.error("fatal_error", error=str(e))
        raise


# ==========================================
# 📌 ENTRY POINT (точка входа)
# ==========================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("⛔ Приложение остановлено пользователем (Ctrl+C)")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        raise
