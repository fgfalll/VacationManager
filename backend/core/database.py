"""Налаштування бази даних та сесій SQLAlchemy."""

from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings

settings = get_settings()

# Створення двигуна бази даних
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    echo=settings.debug,
)

# Фабрика сесій
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency для FastAPI - надає сесію бази даних.

    Yields:
        Session: Сесія SQLAlchemy
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Контекстний менеджер для використання в Desktop додатку.

    Yields:
        Session: Сесія SQLAlchemy

    Example:
        with get_db_context() as db:
            staff = db.query(Staff).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class AsyncDBContext:
    """Async context manager wrapper for synchronous database session."""

    def __init__(self):
        self.db = None

    async def __aenter__(self):
        self.db = SessionLocal()
        return self.db

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.db.rollback()
        else:
            self.db.commit()
        self.db.close()
        return False


async def get_db_session() -> AsyncGenerator[Session, None]:
    """
    Async generator для отримання сесії бази даних.

    Для використання в Telegram bot handlers.

    Usage:
        async for db in get_db_session():
            result = db.execute(select(Staff).first())
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
