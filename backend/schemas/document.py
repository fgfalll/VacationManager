"""Pydantic схеми для документів."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from shared.enums import DocumentStatus, DocumentType


class DocumentBase(BaseModel):
    """Базова схема документа."""

    staff_id: int = Field(..., gt=0, description="ID співробітника")
    doc_type: DocumentType = Field(..., description="Тип документа")
    date_start: date = Field(..., description="Початок відпустки")
    date_end: date = Field(..., description="Кінець відпустки")
    payment_period: str | None = Field(None, max_length=100, description="Період оплати")
    custom_text: str | None = Field(None, description="Кастомний текст")

    @field_validator("date_end")
    @classmethod
    def end_after_start(cls, v: date, info: ValidationInfo) -> date:
        """Перевірка, що кінець відпустки не раніше за початок."""
        # Allow single day vacation (start == end), so checking strictly less than
        if "date_start" in info.data and v < info.data["date_start"]:
            raise ValueError("Кінець відпустки має бути не раніше за початок")
        return v


class DocumentCreate(DocumentBase):
    """Схема для створення документа."""

    new_employee_data: dict[str, Any] | None = Field(None, description="Дані нового співробітника (тільки для документів прийому)")


class DocumentUpdate(BaseModel):
    """Схема для оновлення документа."""

    status: DocumentStatus | None = None
    date_start: date | None = None
    date_end: date | None = None
    payment_period: str | None = None
    custom_text: str | None = None


class WorkflowStep(BaseModel):
    """Схема для етапу підписання."""
    completed: bool
    at: datetime | None
    comment: str | None


class DocumentProgress(BaseModel):
    """Схема прогресу документа."""
    applicant: WorkflowStep
    approval: WorkflowStep
    department_head: WorkflowStep
    approval_order: WorkflowStep
    rector: WorkflowStep
    scanned: WorkflowStep
    tabel: WorkflowStep


class DocumentResponse(DocumentBase):
    """Схема відповіді документа."""

    id: int
    status: DocumentStatus
    days_count: int
    file_docx_path: str | None
    file_scan_path: str | None
    created_at: datetime
    updated_at: datetime
    signed_at: datetime | None
    processed_at: datetime | None

    # Tabel tracking
    tabel_added_at: datetime | None = None
    tabel_added_comment: str | None = None

    # Вкладений об'єкт співробітника
    staff_name: str | None = None
    staff_position: str | None = None

    # Correction tracking fields
    is_correction: bool = False
    correction_month: int | None = None
    correction_year: int | None = None
    correction_sequence: int = 1

    # Прогрес документа
    progress: DocumentProgress | None = None

    # Frontend-compatible fields
    title: str | None = None  # Document title
    document_type: dict | None = None  # {id, name} for frontend compatibility
    # Frontend-compatible date field aliases
    start_date: date | None = None  # Alias for date_start
    end_date: date | None = None  # Alias for date_end

    # New employee data for employment documents
    new_employee_data: dict[str, Any] | None = Field(None, description="Дані нового співробітника")

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Схема для списку документів."""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentGenerateResponse(BaseModel):
    """Схема відповіді при генерації документа."""

    success: bool
    file_path: str | None = None
    message: str
    document_id: int


class PreviewResponse(BaseModel):
    """Schema for document preview response."""
    html: str


class DocumentStatusUpdate(BaseModel):
    """Схема для оновлення статусу документа."""

    status: DocumentStatus = Field(..., description="Новий статус")


class EmploymentCreate(BaseModel):
    """Схема для даних нового співробітника при створенні документа прийому на роботу."""

    pib_nom: str = Field(..., min_length=1, max_length=200, description="ПІБ у називному відмінку")
    degree: str | None = Field(None, max_length=50, description="Вчений ступінь")
    rate: float = Field(..., ge=0.25, le=2.0, description="Ставка (0.25, 0.5, 0.75, 1.0)")
    position: str = Field(..., min_length=1, max_length=100, description="Посада")
    employment_type: str = Field(..., description="Тип працевлаштування (main/external/internal)")
    work_basis: str = Field(..., description="Основа роботи (contract/competitive/statement)")
    term_start: date = Field(..., description="Початок контракту")
    term_end: date = Field(..., description="Кінець контракту")
    vacation_balance: int = Field(default=0, description="Залишок днів відпустки")
    email: str | None = Field(None, description="Email")
    phone: str | None = Field(None, description="Телефон")

    @field_validator("term_end")
    @classmethod
    def end_after_start(cls, v: date, info: ValidationInfo) -> date:
        """Перевірка, що кінець контракту не раніше за початок."""
        if "term_start" in info.data and v <= info.data["term_start"]:
            raise ValueError("Дата закінчення контракту має бути пізніше за дату початку")
        return v


class BulkValidationRequest(BaseModel):
    """Схема запиту на валідацію масового створення документів."""

    staff_ids: list[int] = Field(..., description="Список ID співробітників")
    date_start: date = Field(..., description="Початок відпустки")
    date_end: date = Field(..., description="Кінець відпустки")


class BulkGenerateRequest(BaseModel):
    """Схема запиту на масове створення документів."""

    staff_ids: list[int] = Field(..., description="Список ID співробітників")
    doc_type: DocumentType = Field(..., description="Тип документа")
    date_start: date = Field(..., description="Початок відпустки")
    date_end: date = Field(..., description="Кінець відпустки")
    file_suffix: str = Field(default="", description="Суфікс для назви файлу")


class StaleResolutionRequest(BaseModel):
    """Схема для вирішення старого документа."""
    action: Literal["explain", "remove"] = Field(..., description="Дія: пояснити або видалити")
    explanation: str | None = Field(None, description="Пояснення (обов'язково якщо action='explain')")

