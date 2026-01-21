"""Головний файл FastAPI додатку."""

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func

from backend.api.routes import documents, schedule, staff, upload, auth, attendance, settings as settings_routes, tabel, dashboard, bulk
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

    yield
    
    # Cleanup
    stop_event.set()
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    logging.info("Stale document monitor stopped")


app = FastAPI(
    title="VacationManager API",
    description="""
    API для системи управління відпустками та кадрами.
    
    ## Основні можливості:
    
    * **Документи**: Створення, погодження та архівування кадрових документів.
    * **Співробітники**: Управління базою співробітників, їх контрактами та ставками.
    * **Графік відпусток**: Планування та моніторинг щорічних відпусток.
    * **Табель**: Облік робочого часу та формування табелів.
    * **Статистика**: Дашборди та звіти.
    
    ## Авторизація:
    
    Для доступу до більшості ендпоінтів потрібна авторизація через Bearer token.
    Використовуйте ендпоінт `/api/auth/login` для отримання токена.
    """,
    version="7.0.1",
    contact={
        "name": "Support Team",
        "email": "support@vacationmanager.local",
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

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(staff.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(tabel.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(bulk.router, prefix="/api")



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
