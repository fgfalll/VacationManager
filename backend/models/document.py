"""Модель документа."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from shared.enums import DocumentStatus, DocumentType

if TYPE_CHECKING:
    from backend.models.staff import Staff


class Document(Base, TimestampMixin):
    """
    Модель документа (заяви на відпустку).

    Attributes:
        id: Унікальний ідентифікатор
        staff_id: ID співробітника
        doc_type: Тип документа
        status: Статус документа
        date_start: Початок відпустки
        date_end: Кінець відпустки
        days_count: Кількість днів
        payment_period: Період оплати (наприклад, "у першій половині червня")
        custom_text: Кастомний текст (ручне редагування)
        file_docx_path: Шлях до .docx файлу
        file_scan_path: Шлях до скану підписаного документа
        signed_at: Час підписання
        processed_at: Число обробки (списання днів)
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(SQLEnum(DocumentType), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.DRAFT,
        nullable=False,
    )

    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    days_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_period: Mapped[str | None] = mapped_column(String(100))
    custom_text: Mapped[str | None] = mapped_column(Text)

    file_docx_path: Mapped[str | None] = mapped_column(String(500))
    file_scan_path: Mapped[str | None] = mapped_column(String(500))

    signed_at: Mapped[datetime | None] = mapped_column(DateTime)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="documents")

    def __repr__(self) -> str:
        return f"<Document {self.id}: {self.staff.pib_nom} - {self.doc_type.value} ({self.status.value})>"
