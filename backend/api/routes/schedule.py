"""API маршрути для управління річним графіком відпусток."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import DBSession, ValidationSvc
from backend.models.schedule import AnnualSchedule
from backend.models.staff import Staff
from backend.schemas.schedule import (
    AutoDistributeRequest,
    AutoDistributeResponse,
    ScheduleEntryCreate,
    ScheduleEntryResponse,
    ScheduleListResponse,
)
from shared.exceptions import ValidationError as CustomValidationError

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/{year}", response_model=ScheduleListResponse)
async def get_schedule(
    year: int,
    db: DBSession,
):
    """
    Отримати графік відпусток на рік.
    """
    entries = (
        db.query(AnnualSchedule)
        .filter(AnnualSchedule.year == year)
        .order_by(AnnualSchedule.planned_start)
        .all()
    )

    result_items = []
    for entry in entries:
        entry_dict = ScheduleEntryResponse.model_validate(entry).model_dump()
        entry_dict["staff_name"] = entry.staff.pib_nom
        entry_dict["staff_position"] = entry.staff.position
        entry_dict["staff_rate"] = float(entry.staff.rate)
        entry_dict["staff_employment_type"] = entry.staff.employment_type
        result_items.append(ScheduleEntryResponse(**entry_dict))

    return ScheduleListResponse(
        items=result_items,
        total=len(entries),
        year=year,
    )


@router.post("", response_model=ScheduleEntryResponse, status_code=201)
async def create_schedule_entry(
    entry_data: ScheduleEntryCreate,
    db: DBSession,
    validation: ValidationSvc,
):
    """
    Створити запис у графіку.
    """
    # Отримуємо співробітника
    staff = db.query(Staff).filter(Staff.id == entry_data.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    # Валідація
    try:
        validation.validate_schedule_dates(
            entry_data.planned_start,
            entry_data.planned_end,
            staff,
            db,
        )
    except CustomValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Перевірка на унікальність
    existing = (
        db.query(AnnualSchedule)
        .filter(
            AnnualSchedule.year == entry_data.year,
            AnnualSchedule.staff_id == entry_data.staff_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Запис для {entry_data.year} року та цього співробітника вже існує",
        )

    entry = AnnualSchedule(**entry_data.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)

    response = ScheduleEntryResponse.model_validate(entry)
    response.staff_name = entry.staff.pib_nom
    response.staff_position = entry.staff.position
    response.staff_rate = float(entry.staff.rate)
    response.staff_employment_type = entry.staff.employment_type

    return response


@router.put("/{entry_id}", response_model=ScheduleEntryResponse)
async def update_schedule_entry(
    entry_id: int,
    planned_start: date | None = None,
    planned_end: date | None = None,
    is_used: bool | None = None,
    db: DBSession = None,
):
    """
    Оновити запис у графіку.
    """
    entry = db.query(AnnualSchedule).filter(AnnualSchedule.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    if planned_start is not None:
        entry.planned_start = planned_start
    if planned_end is not None:
        entry.planned_end = planned_end
    if is_used is not None:
        entry.is_used = is_used

    db.commit()
    db.refresh(entry)

    response = ScheduleEntryResponse.model_validate(entry)
    response.staff_name = entry.staff.pib_nom
    response.staff_position = entry.staff.position
    response.staff_rate = float(entry.staff.rate)
    response.staff_employment_type = entry.staff.employment_type

    return response


@router.delete("/{entry_id}", status_code=204)
async def delete_schedule_entry(
    entry_id: int,
    db: DBSession,
):
    """
    Видалити запис з графіку.
    """
    entry = db.query(AnnualSchedule).filter(AnnualSchedule.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    db.delete(entry)
    db.commit()

    return None


@router.post("/auto-distribute", response_model=AutoDistributeResponse)
async def auto_distribute_vacations(
    request: AutoDistributeRequest,
    db: DBSession,
):
    """
    Автоматично розподілити відпустки по місяцях.
    """
    from backend.services.schedule_service import ScheduleService
    from shared.enums import EmploymentType

    service = ScheduleService(db)

    # Отримуємо список співробітників
    staff_list = service.get_staff_for_schedule(request.year)

    if not request.include_all_staff:
        # Фільтруємо: тільки ставка 1.0 та внутрішні сумісники
        staff_list = [
            s for s in staff_list
            if s.rate >= 1.0 or s.employment_type == EmploymentType.INTERNAL
        ]

    if not staff_list:
        return AutoDistributeResponse(
            success=False,
            message="Немає співробітників для розподілу",
            entries_created=0,
        )

    # Використовуємо сервіс для розподілу
    result = service.auto_distribute(request.year, staff_list)

    return AutoDistributeResponse(
        success=True,
        message=f"Створено {result['entries_created']} записів",
        entries_created=result['entries_created'],
        warnings=result['warnings'],
    )
