"""Налаштування структурованого логування."""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from backend.core.config import get_settings

settings = get_settings()


def add_log_level(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Додає рівень логування до запису."""
    event_dict["level"] = method_name.upper()
    return event_dict


def drop_color_message_key(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Видаляє ключ color_message для JSON формату."""
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging() -> None:
    """
    Налаштовує структуроване логування для додатку.

    Використовує structlog для уніфікованого логування в форматі
    JSON або Console залежно від налаштувань.
    """
    log_level = getattr(logging, settings.log_level)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Shared processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        # JSON формат для продакшн
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Console формат для розробки
        processors = shared_processors + [
            drop_color_message_key,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Налаштування structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Налаштування стандартного логування
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Налаштування логування в файл
    file_handler = logging.FileHandler(log_dir / "vacation_manager.log", encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    # Зменшити шум від зовнішніх бібліотек
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
