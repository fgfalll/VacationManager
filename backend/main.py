"""Головний файл FastAPI додатку."""

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func

from backend.api.routes import documents, schedule, staff, auth, attendance, settings as settings_routes, tabel, dashboard, bulk, telegram
from backend.api.dependencies import DBSession
from backend.core.config import get_settings
from backend.core.logging import setup_logging
from backend.core.websocket import manager
from backend.models.staff import Staff
from backend.models.document import Document
from backend.models.schedule import AnnualSchedule

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    setup_logging()

    # Start background task for stale document monitoring
    import asyncio
    from backend.api.dependencies import get_db
    from backend.services.stale_document_service import StaleDocumentService
    import logging

    stop_event = asyncio.Event()

    async def stale_monitor_loop():
        """Periodically check for stale documents."""
        logging.info("Starting stale document monitor loop")
        # Initial wait to let server start up
        await asyncio.sleep(60)

        while not stop_event.is_set():
            try:
                logging.info("Running stale document check...")
                # Create a new session for this check
                db_gen = get_db()
                db = next(db_gen)
                try:
                    result = StaleDocumentService.check_and_notify_stale_documents(db)
                    logging.info(f"Stale document check result: {result}")
                finally:
                    db.close()
            except Exception as e:
                logging.error(f"Error in stale document monitor: {e}")

            # Check every 24 hours (86400 seconds)
            # For testing/demo purposes, we can check more frequently or use config
            # But requirement says "notifications when status unchanged for > 1 day"
            # So checking once a day or every few hours is reasonable.
            # Let's check every 12 hours.
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=12 * 3600)
            except asyncio.TimeoutError:
                continue

    monitor_task = asyncio.create_task(stale_monitor_loop())

    # Setup Telegram bot webhook if enabled
    if settings.telegram_enabled:
        try:
            from backend.telegram.bot import bot, dp
            from backend.telegram.handlers import register_command_handlers, register_callback_handlers
            from backend.telegram.handlers.messages import register_message_handlers

            if bot is None:
                logging.warning("Telegram bot enabled but no token configured")
            else:
                # Register handlers
                register_command_handlers(dp)
                register_callback_handlers(dp)
                register_message_handlers(dp)

                # Set webhook if URL is configured AND we're in webhook mode
                # VM_TELEGRAM_WEBHOOK_MODE is set by run.py --telegram-webhook
                import os
                webhook_mode = os.getenv("VM_TELEGRAM_WEBHOOK_MODE", "false").lower() == "true"
                if settings.telegram_webhook_url and webhook_mode:
                    await bot.set_webhook(settings.telegram_webhook_url)
                    logging.info(f"Telegram webhook set to: {settings.telegram_webhook_url}")
                elif settings.telegram_webhook_url and not webhook_mode:
                    logging.info("Telegram webhook URL configured but not in webhook mode (use --telegram-webhook)")
                else:
                    logging.info("Telegram bot enabled but webhook URL not configured")

        except Exception as e:
            logging.error(f"Failed to setup Telegram bot: {e}")

    yield

    # Cleanup
    stop_event.set()
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    logging.info("Stale document monitor stopped")

    # Delete Telegram webhook on shutdown
    if settings.telegram_enabled:
        try:
            from backend.telegram.bot import bot
            if bot is not None:
                await bot.delete_webhook()
                logging.info("Telegram webhook deleted")
        except Exception as e:
            logging.error(f"Failed to delete Telegram webhook: {e}")


app = FastAPI(
    title="VacationManager API",
    description="""
    API для системи управління відпустками та кадрами.
    
    ## Основні можливості
    
    * **Документи**: Повний цикл документообігу - від створення заяви до архівування.
    * **Співробітники**: Ведення кадрового обліку, сумісництво, історія змін.
    * **Графік відпусток**: Планування, автоматичний розподіл та контроль використання відпусток.
    * **Табель**: Автоматизоване формування, корегування та затвердження табелів обліку робочого часу.
    * **Статистика**: Аналітичні дашборди для керівників та співробітників.
    * **Інтеграція**: WebSocket сповіщення, завантаження сканів, друк документів.
    
    ## Авторизація
    
    API використовує JWT (Bearer token) авторизацію.
    1. Отримайте токен через `/api/auth/login`.
    2. Додавайте заголовок `Authorization: Bearer <token>` до кожного запиту.
    """,
    version="7.0.2",
    contact={
        "name": "VacationManager Support",
        "email": "support@vacationmanager.local",
        "url": "http://localhost:8000/support",
    },
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшені обмежити
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
static_dir = Path(__file__).parent.parent / "backend" / "static"
templates_dir = Path(__file__).parent.parent / "backend" / "templates"
telegram_mini_app_dir = Path(__file__).parent.parent / "telegram-mini-app" / "dist"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
# Mount Telegram Mini App if built
if telegram_mini_app_dir.exists():
    app.mount("/mini", StaticFiles(directory=str(telegram_mini_app_dir), html=True), name="mini_app")
templates = Jinja2Templates(directory=str(templates_dir))

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(staff.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")

app.include_router(tabel.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(bulk.router, prefix="/api")
app.include_router(telegram.router, prefix="/api/telegram", tags=["telegram"])



@app.get("/")
async def root():
    """Коренева точка API."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Перевірка здоров'я API."""
    return {"status": "healthy"}





@app.get("/portal")
async def web_portal(request: Request):
    """Web Portal для завантаження сканів документів."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard")
async def employee_dashboard(request: Request):
    """Кабінет співробітника для перегляду балансу та графіку."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для real-time синхронізації.

    Desktop app підключається до цього endpoint для отримання
    повідомлень про завантаження сканів та зміни статусів документів.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Обробка повідомлень від клієнта (наприклад, ping)
            # В основному ми розсилаємо повідомлення, а не отримуємо
            import json
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    # Відповідаємо на ping
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        raise e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
