"""Модель співробітника."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SQLEnum, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from shared.enums import EmploymentType, WorkBasis

if TYPE_CHECKING:
    from backend.models.attendance import Attendance
    from backend.models.document import Document
    from backend.models.schedule import AnnualSchedule
    from backend.models.staff_history import StaffHistory
    from backend.models.telegram_link_request import TelegramLinkRequest


class WorkScheduleType(str, Enum):
    """Тип робочого графіка."""
    STANDARD = "standard"  # Повний робочий день (8 годин)
    PART_TIME = "part_time"  # Неповний робочий день/тиждень


class Staff(Base, TimestampMixin):
    """
    Модель співробітника кафедри.

    Attributes:
        id: Унікальний ідентифікатор
        pib_nom: ПІБ у називному відмінку
        degree: Вчений ступінь (к.т.н., д.т.н.)
        rate: Ставка (0.25, 0.5, 0.75, 1.0)
        position: Посада
        department: Відділ/кафедра
        work_schedule: Тип робочого графіка (standard/part_time)
        employment_type: Тип працевлаштування
        work_basis: Основа роботи
        term_start: Початок договору
        term_end: Кінець договору
        vacation_balance: Залишок днів відпустки
        is_active: Чи активний запис (soft delete)
    """

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    pib_nom: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    pib_dav: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="ПІБ у давальному відмінку (для документів)",
    )
    degree: Mapped[str | None] = mapped_column(String(50))
    rate: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    position: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False, default="Кафедра комп'ютерних та інформаційних технологій")
    work_schedule: Mapped[WorkScheduleType] = mapped_column(
        SQLEnum(WorkScheduleType),
        nullable=False,
        default=WorkScheduleType.STANDARD,
        comment="Тип робочого графіка: standard (повний) або part_time (неповний)",
    )
    employment_type: Mapped[EmploymentType] = mapped_column(SQLEnum(EmploymentType), nullable=False)
    work_basis: Mapped[WorkBasis] = mapped_column(SQLEnum(WorkBasis), nullable=False)
    term_start: Mapped[date] = mapped_column(nullable=False)
    term_end: Mapped[date] = mapped_column(nullable=False)
    vacation_balance: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Contact fields (optional)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Telegram integration fields
    telegram_user_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        unique=True,
        comment="Telegram user ID для Mini App автентифікації",
    )
    telegram_username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Telegram username (без @)",
    )
    telegram_permissions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON список прав: view_documents, sign_documents, view_stale, manage_stale",
    )

    # Relationships
    documents: Mapped[list["Document"]] = relationship(
        back_populates="staff",
        cascade="all, delete-orphan",
        order_by="desc(Document.created_at)",
    )
    schedule_entries: Mapped[list["AnnualSchedule"]] = relationship(
        back_populates="staff",
        cascade="all, delete-orphan",
        order_by="AnnualSchedule.planned_start",
    )
    history: Mapped[list["StaffHistory"]] = relationship(
        back_populates="staff",
        cascade="all, delete-orphan",
        order_by="desc(StaffHistory.created_at)",
        foreign_keys="[StaffHistory.staff_id]",
    )
    attendance_records: Mapped[list["Attendance"]] = relationship(
        back_populates="staff",
        cascade="all, delete-orphan",
        order_by="Attendance.date",
    )
    telegram_link_requests: Mapped[list["TelegramLinkRequest"]] = relationship(
        back_populates="staff",
    )

    @property
    def days_until_term_end(self) -> int:
        """
        Кількість днів до закінчення контракту.

        Returns:
            int: Кількість днів (може бути від'ємним, якщо контракт закінчився)
        """
        return (self.term_end - date.today()).days

    @property
    def is_term_expiring_soon(self) -> bool:
        """
        Чи закінчується контракт менш ніж через 30 днів.

        Returns:
            bool: True якщо контракт закінчується скоро
        """
        return self.days_until_term_end < 30

    @property
    def is_term_expired(self) -> bool:
        """
        Чи закінчився контракт.

        Returns:
            bool: True якщо контракт вже закінчився або закінчується сьогодні
        """
        return self.days_until_term_end <= 0

    def __repr__(self) -> str:
        return f"<Staff {self.id}: {self.pib_nom} ({self.position})>"

    @property
    def daily_work_hours(self) -> Decimal:
        """
        Обчислює кількість робочих годин на день на основі ставки.

        Returns:
            Decimal: Кількість годин (наприклад, 8.0 для 1.0 ставки, 4.0 для 0.5 ставки)
        """
        return Decimal("8.0") * self.rate

    @property
    def is_part_time(self) -> bool:
        """
        Чи працює на умовах неповного робочого дня.

        Returns:
            bool: True якщо ставка менше 1.0 або work_schedule = part_time
        """
        return self.rate < Decimal("1.0") or self.work_schedule == WorkScheduleType.PART_TIME

    def format_rate(self) -> str:
        """
        Форматує ставку для відображення.

        Returns:
            str: Форматована ставка (наприклад, "0,50")
        """
        return f"{float(self.rate):.2f}".replace(".", ",")
