"""Модель погодження табеля."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class TabelApproval(Base, TimestampMixin):
    """
    Модель погодження табеля кадровою службою.

    Attributes:
        id: Унікальний ідентифікатор
        month: Місяць табеля (1-12)
        year: Рік табеля
        is_correction: Чи є це корегуючим табелем
        correction_month: Місяць, що коригується (для корегуючих табелів)
        correction_year: Рік, що коригується (для корегуючих табелів)
        correction_sequence: Номер корекції для місяця (1, 2, 3...) для окремих вкладок
        is_approved: Чи погоджено табель з кадрами
        generated_at: Коли згенеровано табель
        approved_at: Коли погоджено табель
        approved_by: Хто погодив (логін користувача)
    """

    __tablename__ = "tabel_approval"

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    correction_month: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    correction_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    correction_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        correction = f" (корег. {self.correction_month:02d}.{self.correction_year} #{self.correction_sequence})" if self.is_correction else ""
        status = "✓" if self.is_approved else "○"
        return f"<TabelApproval {status} {self.month:02d}.{self.year}{correction}>"

    @property
    def is_locked(self) -> bool:
        """Чи заблоковано цей місяць для редагування."""
        return self.is_approved
