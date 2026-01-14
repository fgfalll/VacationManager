"""Pydantic схеми для річного графіка відпусток."""

from datetime import date

from pydantic import BaseModel, Field

from shared.enums import EmploymentType


class ScheduleEntryBase(BaseModel):
    """Базова схема запису графіка."""

    staff_id: int = Field(..., gt=0, description="ID співробітника")
    year: int = Field(..., ge=2020, le=2100, description="Рік графіку")
    planned_start: date = Field(..., description="Плановий початок")
    planned_end: date = Field(..., description="Плановий кінець")


class ScheduleEntryCreate(ScheduleEntryBase):
    """Схема для створення запису графіка."""

    pass


class ScheduleEntryResponse(ScheduleEntryBase):
    """Схема відповіді запису графіка."""

    id: int
    is_used: bool
    days_count: int

    # Дані співробітника
    staff_name: str | None = None
    staff_position: str | None = None
    staff_rate: float | None = None
    staff_employment_type: EmploymentType | None = None

    class Config:
        from_attributes = True


class ScheduleListResponse(BaseModel):
    """Схема для списку записів графіка."""

    items: list[ScheduleEntryResponse]
    total: int
    year: int


class AutoDistributeRequest(BaseModel):
    """Запит на автоматичний розподіл відпусток."""

    year: int = Field(..., ge=2020, le=2100, description="Рік для розподілу")
    include_all_staff: bool = Field(
        default=False,
        description="Включити всіх співробітників (не тільки ставка=1.0)"
    )


class AutoDistributeResponse(BaseModel):
    """Відповідь на автоматичний розподіл."""

    success: bool
    message: str
    entries_created: int
    warnings: list[str] = []
