"""Pydantic схеми для співробітників."""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from shared.enums import EmploymentType, WorkBasis, STAFF_POSITION_LABELS
from shared.validators import validate_rate_range, validate_vacation_balance

# Reverse mapping for Ukrainian labels to enum values
POSITION_LABELS_REVERSE: dict[str, str] = {v: k for k, v in STAFF_POSITION_LABELS.items()}


def _normalize_position(position: str) -> str:
    """
    Normalize position: convert Ukrainian label to enum value if needed.
    Accepts both enum values (head_of_department) and Ukrainian labels (Завідувач кафедри).
    """
    # If it's already a valid enum value, return as-is
    if position in STAFF_POSITION_LABELS:
        return position
    # If it's a Ukrainian label, convert to enum value
    if position in POSITION_LABELS_REVERSE:
        return POSITION_LABELS_REVERSE[position]
    # If not recognized, return as-is (could be custom position)
    return position


class StaffBase(BaseModel):
    """Базова схема співробітника."""

    pib_nom: str = Field(..., min_length=3, max_length=200, description="ПІБ у називному відмінку")
    degree: str | None = Field(None, max_length=50, description="Вчений ступінь")
    rate: Decimal = Field(..., description="Ставка (0.25, 0.5, 0.75, 1.0)")
    position: str = Field(..., min_length=2, max_length=100, description="Посада")
    employment_type: EmploymentType = Field(..., description="Тип працевлаштування")
    work_basis: WorkBasis = Field(..., description="Основа роботи")
    term_start: date = Field(..., description="Початок договору")
    term_end: date = Field(..., description="Кінець договору")
    vacation_balance: int = Field(default=0, description="Залишок днів відпустки")
    email: str | None = Field(None, description="Email")
    phone: str | None = Field(None, description="Телефон")

    @field_validator("rate", mode="before")
    @classmethod
    def parse_rate(cls, v):
        """Convert float rate to Decimal before validation."""
        if isinstance(v, float):
            return Decimal(str(v))
        return v

    @field_validator("rate")
    @classmethod
    def validate_rate(cls, v: Decimal) -> Decimal:
        """Валідація ставки."""
        return validate_rate_range(float(v))

    @field_validator("vacation_balance")
    @classmethod
    def validate_balance(cls, v: int) -> int:
        """Валідація балансу відпустки."""
        return validate_vacation_balance(v)

    @field_validator("term_end")
    @classmethod
    def end_after_start(cls, v: date, info: ValidationInfo) -> date:
        """Перевірка, що кінець договору пізніше за початок."""
        if "term_start" in info.data and v <= info.data["term_start"]:
            raise ValueError("Кінець договору має бути пізніше за початок")
        return v

    @field_validator("position", mode="before")
    @classmethod
    def normalize_position(cls, v: Any) -> str:
        """Convert Ukrainian position label to enum value if needed."""
        if isinstance(v, str):
            return _normalize_position(v)
        return v


class StaffCreate(BaseModel):
    """Схема для створення співробітника."""

    pib_nom: str = Field(..., min_length=3, max_length=200, description="ПІБ у називному відмінку")
    degree: str | None = Field(None, max_length=50, description="Вчений ступінь")
    rate: Decimal = Field(..., description="Ставка (0.25, 0.5, 0.75, 1.0)")
    position: str = Field(..., min_length=2, max_length=100, description="Посада")
    employment_type: EmploymentType = Field(..., description="Тип працевлаштування")
    work_basis: WorkBasis = Field(..., description="Основа роботи")
    term_start: date = Field(..., description="Початок договору")
    term_end: date = Field(..., description="Кінець договору")
    vacation_balance: int = Field(default=0, description="Залишок днів відпустки")
    email: str | None = Field(None, description="Email")
    phone: str | None = Field(None, description="Телефон")

    @field_validator("rate", mode="before")
    @classmethod
    def parse_rate(cls, v):
        """Convert float rate to Decimal before validation."""
        if isinstance(v, float):
            return Decimal(str(v))
        return v

    @field_validator("position", mode="before")
    @classmethod
    def normalize_position(cls, v: Any) -> str:
        """Convert Ukrainian position label to enum value if needed."""
        if isinstance(v, str):
            return _normalize_position(v)
        return v


class StaffUpdate(BaseModel):
    """Схема для оновлення співробітника."""

    pib_nom: str | None = Field(None, min_length=3, max_length=200)
    degree: str | None = Field(None, max_length=50)
    rate: Decimal | None = None
    position: str | None = Field(None, min_length=2, max_length=100)
    employment_type: EmploymentType | None = None
    work_basis: WorkBasis | None = None
    term_start: date | None = None
    term_end: date | None = None
    vacation_balance: int | None = None
    is_active: bool | None = None
    email: str | None = None
    phone: str | None = None

    @field_validator("position", mode="before")
    @classmethod
    def normalize_position(cls, v: Any) -> str:
        """Convert Ukrainian position label to enum value if needed."""
        if isinstance(v, str):
            return _normalize_position(v)
        return v


class StaffResponse(StaffBase):
    """Схема відповіді співробітника."""

    id: int
    is_active: bool
    days_until_term_end: int | None = None
    is_term_expiring_soon: bool | None = None

    # Frontend-compatible field aliases
    start_date: date | None = None  # Alias for term_start
    end_date: date | None = None  # Alias for term_end

    # Frontend-compatible name fields
    first_name: str | None = None
    last_name: str | None = None

    # Frontend-compatible status field (maps from is_active)
    status: str | None = None

    class Config:
        from_attributes = True


class StaffListResponse(BaseModel):
    """Схема для списку співробітників."""

    items: list[StaffResponse]
    total: int
    page: int
    page_size: int
