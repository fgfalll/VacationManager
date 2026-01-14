"""Pydantic схеми для співробітників."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from shared.enums import EmploymentType, WorkBasis
from shared.validators import validate_rate_range, validate_vacation_balance


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


class StaffCreate(StaffBase):
    """Схема для створення співробітника."""

    pass


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


class StaffResponse(StaffBase):
    """Схема відповіді співробітника."""

    id: int
    is_active: bool
    days_until_term_end: int | None = None
    is_term_expiring_soon: bool | None = None

    class Config:
        from_attributes = True


class StaffListResponse(BaseModel):
    """Схема для списку співробітників."""

    items: list[StaffResponse]
    total: int
    page: int
    page_size: int
