# main.py
"""
🚀 ГЛАВНЫЙ ФАЙЛ ЗАПУСКА БОТА

Это точка входа - отсюда всё начинается!

Функция: запускает бота, подключает БД, слушает команды от Tilda

ШАГ 3.5: АУДИТ И ИСПРАВЛЕНИЯ main.py
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
from infrastructure.logger import setup_logging
from infrastructure.database.base import init_db, close_db
from infrastructure.redis_storage import redis_storage
from app.bot.handlers.operator import router as operator_router
from app.bot.handlers.client import router as client_router
from app.bot.middlewares import DatabaseMiddleware, LoggingMiddleware
from app.api.webhooks.tilda import router as tilda_router

import structlog

logger = structlog.get_logger()


# ==========================================
# 🔄 LIFESPAN (управление жизненным циклом приложения)
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Когда приложение запускается и выключается.
    
    ✅ ИСПРАВЛЕНО:
    - Правильный порядок инициализации (БД ДО использования)
    - Правильная обработка ошибок
    - Логирование на разных уровнях
    """
    
    # ========== ЗАПУСК ==========
    logger.info("app_startup", message="🟢 Инициализация приложения")
    
    try:
        # Создаём таблицы в БД если их нет
        await init_db()
        logger.info("database_initialized", message="✅ База данных готова")
        
        yield  # ← Здесь приложение работает (слушает команды)
    
    finally:
        # ========== ВЫКЛЮЧЕНИЕ ==========
        logger.info("app_shutdown", message="🔴 Выключение приложения")
        
        try:
            # Закрываем соединение с БД (чистим за собой)
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

# ← ✅ ИСПРАВЛЕНО: Добавляем маршруты ПОСЛЕ создания app
app.include_router(tilda_router, prefix="/api")


# ==========================================
# 🤖 BOT STARTUP & SHUTDOWN
# ==========================================

async def on_startup(bot: Bot):
    """
    Запускается когда бот стартует.
    
    ✅ ИСПРАВЛЕНО:
    - Проверка что config.operator_telegram_id установлен
    - Правильная обработка ошибок
    - Не блокируем запуск если уведомление упало
    """
    
    logger.info("bot_starting", message="🤖 Бот стартует...")
    
    # Проверяем что ID оператора установлен
    if not config.operator_telegram_id:
        logger.warning(
            "operator_id_not_set",
            message="⚠️ OPERATOR_TELEGRAM_ID не установлен в .env"
        )
        return
    
    # Уведомляем оператора что бот живой
    try:
        await bot.send_message(
            chat_id=config.operator_telegram_id,
            text=(
                "✅ <b>Бот запустился!</b>\n\n"
                "Теперь готов принимать заказы от Tilda 🎉\n\n"
                "Используй /operator для управления"
            ),
            parse_mode="HTML"
        )
        logger.info("operator_notified", message="✅ Оператор уведомлен")
    except Exception as e:
        logger.error(
            "operator_notification_failed",
            error=str(e),
            message="⚠️ Не удалось уведомить оператора (но бот работает)"
        )


async def on_shutdown(bot: Bot):
    """
    Запускается когда бот выключается.
    
    ✅ ИСПРАВЛЕНО:
    - Правильная очистка ресурсов
    - Обработка ошибок
    """
    
    logger.info("bot_shutdown", message="🔴 Бот выключается...")
    
    try:
        # ← ✅ ИСПРАВЛЕНО: Закрываем сессию бота
        await bot.session.close()
        logger.info("bot_session_closed", message="✅ Сессия бота закрыта")
    except Exception as e:
        logger.error("bot_shutdown_error", error=str(e))


# ==========================================
# 🚀 ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ==========================================

async def main():
    """
    Главная асинхронная функция.
    
    ✅ ИСПРАВЛЕНО:
    - Правильный порядок инициализации
    - Все обработчики зарегистрированы
    - Проверка критических параметров
    - Правильное управление ошибками
    """
    
    # ========== ИНИЦИАЛИЗАЦИЯ ==========
    
    # 1. Инициализируем логирование (все логи будут видны)
    setup_logging()
    logger.info("application_start", message="🟢 Приложение стартует")
    
    # 2. ← ✅ ИСПРАВЛЕНО: Проверяем критические переменные окружения
    if not config.bot_token:
        logger.error("bot_token_missing", message="❌ BOT_TOKEN не установлен в .env")
        raise ValueError("BOT_TOKEN не найден в переменных окружения")
    
    if not config.webhook_signing_secret:
        logger.error(
            "webhook_secret_missing",
            message="❌ WEBHOOK_SIGNING_SECRET не установлен в .env"
        )
        raise ValueError("WEBHOOK_SIGNING_SECRET не найден")
    
    logger.info("config_validated", message="✅ Конфигурация валидна")
    
    # 3. Инициализируем БД (ПЕРЕД использованием)
    logger.info("initializing_database", message="⏳ Инициализация БД...")
    try:
        await init_db()
        logger.info("database_ready", message="✅ База данных готова")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise
    
    # ========== СОЗДАНИЕ БОТА И ДИСПЕТЧЕРА ==========
    
    # 4. Создаём объект бота (который будет отправлять/получать сообщения)
    logger.info("creating_bot", message="⏳ Создание бота...")
    bot = Bot(
        token=config.bot_token,  # Берём токен из .env
        default=DefaultBotProperties(parse_mode="HTML")
    )
    logger.info("bot_created", message="✅ Бот создан")
    
    # 5. Создаём диспетчер (объект который управляет обработчиками)
    # RedisStorage = сохраняем состояния пользователей в Redis
    logger.info("creating_dispatcher", message="⏳ Создание диспетчера...")
    dp = Dispatcher(
        storage=redis_storage,
        bot=bot
    )
    logger.info("dispatcher_created", message="✅ Диспетчер создан")
    
    # 6. ← ✅ ИСПРАВЛЕНО: Правильный порядок добавления middleware
    # Middleware добавляются в порядке FIFO (first in, first out)
    # Первый добавленный = первый в цепочке обработки
    logger.info("adding_middlewares", message="⏳ Добавление middleware...")
    dp.message.middleware(LoggingMiddleware())      # Логируем первым
    dp.message.middleware(DatabaseMiddleware())     # Затем подключаем БД
    logger.info("middlewares_added", message="✅ Middleware добавлены")
    
    # 7. ← ✅ ИСПРАВЛЕНО: Добавляем ВСЕ обработчики
    logger.info("registering_handlers", message="⏳ Регистрация обработчиков...")
    dp.include_router(operator_router)
    dp.include_router(client_router)
    logger.info("handlers_registered", message="✅ Обработчики зарегистрированы")
    
    # 8. Запускаем startup функцию
    await on_startup(bot)
    
    # ========== ЗАПУСК БОТА И API ОДНОВРЕМЕННО ==========
    
    async def run_bot():
        """
        Запуск бота (слушаем сообщения от пользователей).
        
        ← ✅ ИСПРАВЛЕНО:
        - Правильная обработка ошибок
        - Гарантированное выполнение cleanup
        """
        try:
            logger.info(
                "polling_started",
                message="👂 Бот начинает слушать сообщения...",
                bot_username=f"@{(await bot.get_me()).username}"
            )
            
            # Запускаем polling (слушаем обновления от Telegram)
            await dp.start_polling(
                bot,
                # ← ✅ ИСПРАВЛЕНО: Не трогаем allowed_updates (используем default)
                # allowed_updates=None приводит к получению ВСЕХ обновлений
            )
        
        except asyncio.CancelledError:
            logger.info("polling_cancelled", message="⛔ Polling отменён")
            raise
        
        except Exception as e:
            logger.error(
                "bot_polling_error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        
        finally:
            await on_shutdown(bot)
    
    async def run_api():
        """
        Запуск FastAPI (слушаем вебхуки от Tilda).
        
        ← ✅ ИСПРАВЛЕНО:
        - Правильная конфигурация uvicorn
        - Корректное логирование
        """
        try:
            config_uvicorn = uvicorn.Config(
                app,
                host=config.api_host,
                port=config.api_port,
                log_level="info",
                access_log=True,  # ← Логируем HTTP запросы
                # workers=1 (уже по умолчанию для async)
            )
            server = uvicorn.Server(config_uvicorn)
            logger.info(
                "fastapi_starting",
                message=f"🌐 FastAPI запускается на {config.api_host}:{config.api_port}",
                webhook_url=config.webhook_url
            )
            await server.serve()
        
        except Exception as e:
            logger.error("fastapi_error", error=str(e), error_type=type(e).__name__)
            raise
    
    # ← ✅ ИСПРАВЛЕНО: Запускаем оба одновременно
    logger.info("starting_services", message="🚀 Запуск бота и API...")
    
    try:
        await asyncio.gather(
            run_bot(),
            run_api(),
            return_exceptions=False  # ← Если один упадёт, упадут оба
        )
    
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt", message="⛔ Приложение остановлено пользователем")
    
    except Exception as e:
        logger.error(
            "fatal_error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise


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
        logger.info("app_interrupted", message="⛔ Приложение остановлено пользователем (Ctrl+C)")
    
    except SystemExit:
        # Если вызван sys.exit()
        logger.info("app_exit", message="⛔ Приложение выключилось (sys.exit)")
    
    except Exception as e:
        # Неожиданная критическая ошибка
        logger.error(
            "fatal_error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
    
    finally:
        logger.info("app_final_shutdown", message="👋 Приложение полностью выключено")
