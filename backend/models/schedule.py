"""Модель річного графіка відпусток."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.staff import Staff


class AnnualSchedule(Base, TimestampMixin):
    """
    Запис у річному графіку відпусток.

    Attributes:
        id: Унікальний ідентифікатор
        year: Рік графіку
        staff_id: ID співробітника
        planned_start: Плановий початок відпустки
        planned_end: Плановий кінець відпустки
        is_used: Чи створено заяву на основі цього запису
    """

    __tablename__ = "annual_schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False)
    planned_start: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end: Mapped[date] = mapped_column(Date, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="schedule_entries")

    @property
    def days_count(self) -> int:
        """Кількість днів відпустки за планом."""
        return (self.planned_end - self.planned_start).days + 1

    def __repr__(self) -> str:
        return f"<AnnualSchedule {self.id}: {self.year} - {self.staff.pib_nom}>"
