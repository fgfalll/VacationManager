"""Модель запиту на прив'язку Telegram акаунту."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.staff import Staff


class LinkRequestStatus(str, Enum):
    """Статус запиту на прив'язку."""
    PENDING = "pending"      # Очікує розгляду
    APPROVED = "approved"    # Підтверджено
    REJECTED = "rejected"    # Відхилено


class TelegramLinkRequest(Base, TimestampMixin):
    """
    Запит на прив'язку Telegram акаунту до співробітника.

    Attributes:
        id: Унікальний ідентифікатор
        telegram_user_id: Telegram user ID
        telegram_username: @username (без @)
        phone_number: Номер телефону (якщо поділився)
        first_name: Ім'я в Telegram
        last_name: Прізвище в Telegram
        status: Статус запиту
        staff_id: ID співробітника (після прив'язки)
        approved_by: Хто схвалив/відхилив
        rejection_reason: Причина відхилення
        processed_at: Коли оброблено
    """

    __tablename__ = "telegram_link_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Telegram user info
    telegram_user_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Telegram user ID",
    )
    telegram_username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Telegram username (без @)",
    )
    phone_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Номер телефону",
    )
    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Ім'я в Telegram",
    )
    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Прізвище в Telegram",
    )
    
    # Request status
    status: Mapped[LinkRequestStatus] = mapped_column(
        SQLEnum(LinkRequestStatus),
        nullable=False,
        default=LinkRequestStatus.PENDING,
        index=True,
    )
    
    # Approval/Rejection info
    staff_id: Mapped[int | None] = mapped_column(
        ForeignKey("staff.id"),
        nullable=True,
        comment="ID співробітника (після прив'язки)",
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Хто схвалив/відхилив запит",
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Причина відхилення",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Дата обробки запиту",
    )
    
    # Relationships
    staff: Mapped["Staff"] = relationship(
        back_populates="telegram_link_requests",
        foreign_keys=[staff_id],
    )

    @property
    def display_name(self) -> str:
        """Повне ім'я користувача Telegram."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    @property
    def telegram_display(self) -> str:
        """Відображення Telegram акаунту."""
        if self.telegram_username:
            return f"@{self.telegram_username}"
        return f"ID: {self.telegram_user_id}"

    def __repr__(self) -> str:
        return f"<TelegramLinkRequest {self.id}: {self.display_name} ({self.status.value})>"
