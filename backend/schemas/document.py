"""Pydantic схеми для документів."""

from datetime import date, datetime

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
        """Перевірка, що кінець відпустки пізніше за початок."""
        if "date_start" in info.data and v <= info.data["date_start"]:
            raise ValueError("Кінець відпустки має бути пізніше за початок")
        return v


class DocumentCreate(DocumentBase):
    """Схема для створення документа."""

    pass


class DocumentUpdate(BaseModel):
    """Схема для оновлення документа."""

    status: DocumentStatus | None = None
    date_start: date | None = None
    date_end: date | None = None
    payment_period: str | None = None
    custom_text: str | None = None


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

    # Вкладений об'єкт співробітника
    staff_name: str | None = None
    staff_position: str | None = None

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


class DocumentStatusUpdate(BaseModel):
    """Схема для оновлення статусу документа."""

    status: DocumentStatus = Field(..., description="Новий статус")
