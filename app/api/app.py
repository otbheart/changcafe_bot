# app/api/app.py
"""
FastAPI приложение для обработки вебхуков от Tilda.

FastAPI = веб-фреймворк для создания REST API.

В нашем случае нам нужен FastAPI для обработки POST запроса
когда Tilda отправляет данные о новом заказе.
"""

from fastapi import FastAPI

from app.api.webhooks.tilda import router as tilda_router  
# Импортируем роутер вебхуков

from infrastructure.database.base import init_db, close_db


# Создаем FastAPI приложение
app = FastAPI(
    title="Chang Cafe Bot API",
    description="API для обработки вебхуков от Tilda"
)


# ==========================================
# EVENT: Startup (при старте приложения)
# ==========================================

@app.on_event("startup")
async def startup():
    """
    Вызывается один раз при старте приложения.
    Инициализируем БД (создаем таблицы если их нет).
    """
    
    await init_db()


# ==========================================
# EVENT: Shutdown (при выключении приложения)
# ==========================================

@app.on_event("shutdown")
async def shutdown():
    """
    Вызывается один раз при выключении приложения.
    Закрываем соединения с БД.
    """
    
    await close_db()


# ==========================================
# ENDPOINT: Health check
# ==========================================

@app.get("/health")
async def health_check():
    """
    Простой endpoint для проверки что приложение живо.
    
    Используется для мониторинга (Docker, Kubernetes и т.д.).
    
    Пример:
        GET /health
        → {"status": "ok", "service": "changcafe_bot"}
    """
    
    return {
        "status": "ok",
        "service": "changcafe_bot"
    }


# ==========================================
# РЕГИСТРИРУЕМ РОУТЕР
# ==========================================


# Все endpoints из tilda.py будут доступны как /api/webhook/...
app.include_router(tilda_router, prefix="/api/webhook")

