"""Модель документа."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
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
        extension_start_date: Початок продовження (для документів продовження контракту)
        old_contract_end_date: Дата закінчення попереднього контракту
        days_count: Кількість днів
        payment_period: Період оплати
        custom_text: Кастомний текст
        editor_content: JSON контент WYSIWYG редактора
        file_docx_path: Шлях до PDF файлу
        file_scan_path: Шлях до скану підписаного документа
        signed_at: Час підписання ректором
        processed_at: Час обробки (додано до табелю)
        rollback_reason: Причина відкату до чернетки

        # Workflow timestamps and comments
        applicant_signed_at: Час підписання заявником
        applicant_signed_comment: Коментар заявника

        approval_at: Час перевірки диспетчерською
        approval_comment: Коментар диспетчерської

        department_head_at: Час підписання завідувачем кафедри
        department_head_comment: Коментар завідувача

        approval_order_at: Час підписання наказом
        approval_order_comment: Коментар до наказу

        rector_at: Час підписання ректором
        rector_comment: Коментар ректора

        scanned_at: Час сканування (вхідний скан)
        scanned_comment: Коментар до скану

        tabel_added_at: Час додавання до табелю
        tabel_added_comment: Коментар до табелю

        # Correction tracking fields
        is_correction: Чи є документом корегуючого табеля
        correction_month: Місяць, що коригується
        correction_year: Рік, що коригується
        correction_sequence: Номер послідовності корекції
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
    extension_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Початок продовження контракту (для документів продовження)",
    )
    old_contract_end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Дата закінчення попереднього контракту (для документів продовження)",
    )
    days_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_period: Mapped[str | None] = mapped_column(String(100))
    custom_text: Mapped[str | None] = mapped_column(Text)
    editor_content: Mapped[str | None] = mapped_column(Text)
    rendered_html: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Rendered HTML content for document preview",
    )

    file_docx_path: Mapped[str | None] = mapped_column(String(500))
    file_scan_path: Mapped[str | None] = mapped_column(String(500))
    archive_metadata_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Path to JSON archive with snapshot of staff/approver/settings data",
    )

    # Legacy fields (kept for compatibility)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    rollback_reason: Mapped[str | None] = mapped_column(Text)

    # Workflow timestamps and comments
    applicant_signed_at: Mapped[datetime | None] = mapped_column(DateTime)
    applicant_signed_comment: Mapped[str | None] = mapped_column(Text)

    approval_at: Mapped[datetime | None] = mapped_column(DateTime)
    approval_comment: Mapped[str | None] = mapped_column(Text)

    department_head_at: Mapped[datetime | None] = mapped_column(DateTime)
    department_head_comment: Mapped[str | None] = mapped_column(Text)

    approval_order_at: Mapped[datetime | None] = mapped_column(DateTime)
    approval_order_comment: Mapped[str | None] = mapped_column(Text)

    rector_at: Mapped[datetime | None] = mapped_column(DateTime)
    rector_comment: Mapped[str | None] = mapped_column(Text)

    scanned_at: Mapped[datetime | None] = mapped_column(DateTime)
    scanned_comment: Mapped[str | None] = mapped_column(Text)

    tabel_added_at: Mapped[datetime | None] = mapped_column(DateTime)
    tabel_added_comment: Mapped[str | None] = mapped_column(Text)

    # Correction tracking fields - for documents added after month is locked
    is_correction: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Чи є документом корегуючого табеля",
    )
    correction_month: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Місяць, що коригується (для корегуючих документів)",
    )
    correction_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Рік, що коригується (для корегуючих документів)",
    )
    correction_sequence: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Номер послідовності корекції (1, 2, 3...)",
    )

    # Blocking fields - for documents that cannot be edited/deleted
    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Чи заблоковано редагування документа (завантажено скан або оброблено)",
    )
    blocked_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Причина блокування документа",
    )

    # Employment document fields - for storing new employee data before creation
    new_employee_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Дані нового співробітника для документів прийому на роботу",
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="documents")

    def __repr__(self) -> str:
        return f"<Document {self.id}: {self.staff.pib_nom} - {self.doc_type.value} ({self.status.value})>"

    def get_workflow_progress(self) -> dict:
        """Повертає прогрес документа по етапах."""
        return {
            "applicant": {
                "completed": bool(self.applicant_signed_at),
                "at": self.applicant_signed_at,
                "comment": self.applicant_signed_comment,
            },
            "approval": {
                "completed": bool(self.approval_at),
                "at": self.approval_at,
                "comment": self.approval_comment,
            },
            "department_head": {
                "completed": bool(self.department_head_at),
                "at": self.department_head_at,
                "comment": self.department_head_comment,
            },
            "approval_order": {
                "completed": bool(self.approval_order_at),
                "at": self.approval_order_at,
                "comment": self.approval_order_comment,
            },
            "rector": {
                "completed": bool(self.rector_at),
                "at": self.rector_at,
                "comment": self.rector_comment,
            },
            "scanned": {
                "completed": bool(self.scanned_at),
                "at": self.scanned_at,
                "comment": self.scanned_comment,
            },
            "tabel": {
                "completed": bool(self.tabel_added_at),
                "at": self.tabel_added_at,
                "comment": self.tabel_added_comment,
            },
        }

    def update_status_from_workflow(self) -> None:
        """Оновлює статус документа на основі етапів підписання."""
        progress = self.get_workflow_progress()

        # Перевіряємо, чи документ додано до корегуючого табелю
        # (коментар містить "корегуюч" коли місяць вже затверджено)
        is_in_correction = bool(
            self.tabel_added_comment and
            "корегуюч" in self.tabel_added_comment.lower()
        )

        # Визначаємо статус на основі пріоритету (від кінця до початку)

        # 1. PROCESSED: Якщо додано до табелю АБО до корегуючого табелю
        if progress["tabel"]["completed"] or is_in_correction:
            self.status = DocumentStatus.PROCESSED

        # 2. SCANNED: Якщо є скан і підпис ректора (але ще не в табелі)
        elif progress["rector"]["completed"] and progress["scanned"]["completed"]:
             self.status = DocumentStatus.SCANNED

        # 3. SIGNED: Якщо підписано ректором (але ще не скан)
        elif progress["rector"]["completed"]:
            self.status = DocumentStatus.SIGNED

        # 4. AGREED: Якщо є підпис зав. кафедри та погодження (усіх required)
        # Припускаємо, що approval_order це "погоджувачі", а department_head - завідувач
        elif progress["department_head"]["completed"] and progress["approval_order"]["completed"]:
            self.status = DocumentStatus.AGREED

        # 5. ON_SIGNATURE: Якщо хоча б хтось почав підписувати (або викладач, або диспетчер)
        elif (progress["department_head"]["completed"] or
              progress["approval_order"]["completed"] or
              progress["approval"]["completed"] or
              progress["applicant"]["completed"]):
            self.status = DocumentStatus.ON_SIGNATURE

        # 6. DRAFT: Жодних дій не виконано
        else:
            self.status = DocumentStatus.DRAFT

    def reset_workflow(self) -> None:
        """Скидає всі етапи підписання (при редагуванні документа).

        Raises:
            ValueError: Якщо документ вже відскановано.
        """
        if self.status in (DocumentStatus.SIGNED, DocumentStatus.PROCESSED):
            raise ValueError("Неможливо скинути етапи - документ вже відскановано")

        self.applicant_signed_at = None
        self.applicant_signed_comment = None
        self.approval_at = None
        self.approval_comment = None
        self.department_head_at = None
        self.department_head_comment = None
        self.approval_order_at = None
        self.approval_order_comment = None
        self.rector_at = None
        self.rector_comment = None
        self.scanned_at = None
        self.scanned_comment = None
        self.tabel_added_at = None
        self.tabel_added_comment = None
        self.status = DocumentStatus.DRAFT
