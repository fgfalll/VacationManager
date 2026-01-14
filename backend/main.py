"""Головний файл FastAPI додатку."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.api.routes import documents, schedule, staff, upload
from backend.core.config import get_settings
from backend.core.logging import setup_logging
from backend.core.websocket import manager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    setup_logging()
    yield
    # Cleanup


app = FastAPI(
    title="VacationManager API",
    description="API для системи управління відпустками",
    version=settings.app_version,
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
app.include_router(staff.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(upload.router, prefix="/api")


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
