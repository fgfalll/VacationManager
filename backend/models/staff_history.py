"""Модель історії змін співробітника."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.staff import Staff


class StaffHistory(Base, TimestampMixin):
    """
    Модель для відстеження всіх змін у записах співробітників.

    Attributes:
        id: Унікальний ідентифікатор
        staff_id: ID співробітника (поточного запису)
        action_type: Тип дії (CREATE, UPDATE, DEACTIVATE, RESTORE)
        previous_values: JSON зі старими значеннями (тільки змінені поля)
        changed_by: Хто вніс зміни (ім'я користувача або "SYSTEM")
        comment: Коментар до зміни
    """

    __tablename__ = "staff_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    previous_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False, default="USER")
    comment: Mapped[str | None] = mapped_column(Text)

    # Relationships
    staff: Mapped["Staff"] = relationship(
        back_populates="history",
        foreign_keys="StaffHistory.staff_id",
    )

    def __repr__(self) -> str:
        return f"<StaffHistory {self.id}: {self.action_type} on staff {self.staff_id}>"
