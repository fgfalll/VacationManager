"""Базова модель для всіх ORM моделей."""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовий клас для всіх моделей."""

    pass


class TimestampMixin:
    """
    Mixin для додавання timestamp полів до моделі.

    Attributes:
        created_at: Час створення запису
        updated_at: Час останнього оновлення запису
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
