# ChangCafe Bot API

## Overview
This is a Telegram bot application for ChangCafe that handles orders from Tilda webhooks. It includes:
- FastAPI REST API for receiving webhooks from Tilda
- Optional Telegram bot for operator notifications
- PostgreSQL database for storing orders and users
- Redis for FSM state storage (optional, falls back to memory storage)

## Project Structure
```
.
├── app/
│   ├── api/           # FastAPI application
│   │   └── webhooks/  # Webhook handlers (Tilda)
│   └── bot/           # Telegram bot
│       ├── handlers/  # Message handlers
│       ├── keyboards/ # Bot keyboards
│       ├── middlewares/ # Bot middlewares
│       └── services/  # Business logic
├── config/
│   └── settings.py    # Application settings (Pydantic)
├── infrastructure/
│   ├── database/      # SQLAlchemy models and session
│   ├── logger.py      # Logging configuration
│   └── redis_storage.py # Redis/Memory storage for FSM
└── main.py            # Application entry point
```

## Environment Variables
Required:
- `DATABASE_URL` - PostgreSQL connection string (auto-configured by Replit)

Optional (for Telegram bot):
- `BOT_TOKEN` - Telegram bot token from @BotFather
- `BOT_USERNAME` - Bot username (without @)
- `OPERATOR_TELEGRAM_ID` - Telegram ID to receive notifications
- `REDIS_URL` - Redis connection URL (uses memory storage if not set)
- `WEBHOOK_SIGNING_SECRET` - Secret for webhook verification
- `API_WEBHOOK_SECRET` - API authentication secret

## Running the Application
The application runs on port 5000 (FastAPI).

API Endpoints:
- `GET /` - Root endpoint (status check)
- `GET /health` - Health check
- `POST /api/webhook/tilda` - Tilda webhook endpoint

## Database
PostgreSQL database is used with SQLAlchemy ORM.

Tables:
- `users` - Customer information
- `orders` - Order records
- `order_items` - Order line items

## Recent Changes
- 2026-01-22: Initial Replit setup
  - Configured for Replit PostgreSQL
  - Made Redis optional (falls back to MemoryStorage)
  - Set API port to 5000
  - Made bot token optional for API-only mode
