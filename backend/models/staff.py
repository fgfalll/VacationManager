"""Модель співробітника."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SQLEnum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from shared.enums import EmploymentType, WorkBasis

if TYPE_CHECKING:
    from backend.models.document import Document
    from backend.models.schedule import AnnualSchedule
    from backend.models.staff_history import StaffHistory


class Staff(Base, TimestampMixin):
    """
    Модель співробітника кафедри.

    Attributes:
        id: Унікальний ідентифікатор
        pib_nom: ПІБ у називному відмінку
        degree: Вчений ступінь (к.т.н., д.т.н.)
        rate: Ставка (0.25, 0.5, 0.75, 1.0)
        position: Посада
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
    degree: Mapped[str | None] = mapped_column(String(50))
    rate: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    position: Mapped[str] = mapped_column(String(100), nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(SQLEnum(EmploymentType), nullable=False)
    work_basis: Mapped[WorkBasis] = mapped_column(SQLEnum(WorkBasis), nullable=False)
    term_start: Mapped[date] = mapped_column(nullable=False)
    term_end: Mapped[date] = mapped_column(nullable=False)
    vacation_balance: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
            bool: True якщо контракт вже закінчився
        """
        return self.days_until_term_end < 0

    def __repr__(self) -> str:
        return f"<Staff {self.id}: {self.pib_nom} ({self.position})>"
