"""API маршрути для управління річним графіком відпусток."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import DBSession, ValidationSvc
from backend.core.dependencies import get_current_user, require_department_head
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


@router.get("/annual")
async def get_annual_schedule(
    year: int = Query(..., description="Year"),
    month: int | None = Query(None, description="Month (1-12)"),
    department: str | None = Query(None, description="Filter by department"),
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Отримати річний графік відпусток.
    """
    query = db.query(AnnualSchedule).filter(AnnualSchedule.year == year)

    if department:
        query = query.join(Staff).filter(Staff.department == department)

    entries = query.order_by(AnnualSchedule.planned_start).all()

    # Filter by month in Python (SQLite doesn't support func.month)
    if month:
        entries = [e for e in entries if e.planned_start.month == month]

    result_items = []
    for entry in entries:
        staff = entry.staff
        result_items.append({
            "id": entry.id,
            "staff_id": entry.staff_id,
            "staff": {
                "id": staff.id if staff else 0,
                "pib_nom": staff.pib_nom if staff else "",
                "position": staff.position if staff else "",
            },
            "year": entry.year,
            "planned_start": entry.planned_start.isoformat() if entry.planned_start else None,
            "planned_end": entry.planned_end.isoformat() if entry.planned_end else None,
            "days_count": entry.days_count,
            "is_used": entry.is_used,
            "total_working_days": 22,
            "total_vacation_days": entry.days_count,
            "total_holiday_days": 0,
        })

    return {
        "data": result_items,
        "total": len(entries),
        "year": year,
    }


@router.get("/{year}")
async def get_schedule(
    year: int,
    db: DBSession = None,
    current_user = Depends(require_department_head),
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
        staff = entry.staff
        result_items.append({
            "id": entry.id,
            "year": entry.year,
            "staff_id": entry.staff_id,
            "staff_name": staff.pib_nom if staff else "",
            "staff_position": staff.position if staff else "",
            "planned_start": entry.planned_start.isoformat() if entry.planned_start else None,
            "planned_end": entry.planned_end.isoformat() if entry.planned_end else None,
            "days_count": entry.days_count,
            "is_used": entry.is_used,
        })

    return {
        "items": result_items,
        "total": len(entries),
        "year": year,
    }


@router.post("", response_model=ScheduleEntryResponse, status_code=201)
async def create_schedule_entry(
    entry_data: ScheduleEntryCreate,
    db: DBSession = None,
    validation: ValidationSvc = None,
    current_user = Depends(require_department_head),
):
    """
    Створити запис у графіку.
    """
    staff = db.query(Staff).filter(Staff.id == entry_data.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    entry = AnnualSchedule(
        year=entry_data.year,
        staff_id=entry_data.staff_id,
        planned_start=entry_data.planned_start,
        planned_end=entry_data.planned_end,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return ScheduleEntryResponse.model_validate(entry)


@router.put("/{entry_id}")
async def update_schedule_entry(
    entry_id: int,
    planned_start: Optional[date] = None,
    planned_end: Optional[date] = None,
    is_used: Optional[bool] = None,
    db: DBSession = None,
    current_user = Depends(require_department_head),
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

    return {"message": "Запис оновлено"}


@router.delete("/{entry_id}", status_code=204)
async def delete_schedule_entry(
    entry_id: int,
    db: DBSession = None,
    current_user = Depends(require_department_head),
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
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Автоматично розподілити відпустки по місяцях.
    """
    from backend.services.schedule_service import ScheduleService
    from shared.enums import EmploymentType

    service = ScheduleService(db)
    staff_list = service.get_staff_for_schedule(request.year)

    if not request.include_all_staff:
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

    result = service.auto_distribute(request.year, staff_list)

    return AutoDistributeResponse(
        success=True,
        message=f"Створено {result['entries_created']} записів",
        entries_created=result['entries_created'],
        warnings=result['warnings'],
    )


@router.get("/stats")
async def get_schedule_stats(
    year: int = Query(..., description="Year"),
    month: int | None = Query(None, description="Month (1-12)"),
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Отримати статистику графіка відпусток.
    """
    total_staff = db.query(func.count(Staff.id)).filter(Staff.is_active == True).scalar() or 0
    total_working_days = 22 * total_staff

    department_stats = db.query(
        Staff.department,
        func.count(Staff.id).label('total_staff'),
    ).filter(Staff.is_active == True).group_by(Staff.department).all()

    return {
        "total_staff": total_staff,
        "total_working_days": total_working_days,
        "department_breakdown": [
            {
                "department": dept,
                "total_staff": staff_count,
                "assigned_vacation_days": 0,
                "remaining_vacation_days": 0,
            }
            for dept, staff_count in department_stats
        ],
    }
