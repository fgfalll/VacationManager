"""API маршрути для управління відвідуваністю."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func

from backend.api.dependencies import DBSession
from backend.core.dependencies import get_current_user, require_department_head
from backend.models.attendance import Attendance
from backend.models.staff import Staff

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/list")
async def list_all_attendance(
    skip: int = Query(0, ge=0, description="Skip records for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Limit records per page"),
    staff_id: Optional[int] = Query(None, description="Filter by staff ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
    is_correction: Optional[bool] = Query(None, description="Filter by correction status"),
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Отримати всі записи відвідуваності з пагінацією та фільтрацією.

    Показує всі записи з інформацією про те, чи знаходиться вони в основному
    табелі або в коригувальному табелі.
    """
    query = db.query(Attendance)

    # Apply filters
    if staff_id:
        query = query.filter(Attendance.staff_id == staff_id)
    if year:
        query = query.filter(func.extract("year", Attendance.date) == year)
    if month:
        query = query.filter(func.extract("month", Attendance.date) == month)
    if is_correction is not None:
        query = query.filter(Attendance.is_correction == is_correction)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    records = query.order_by(Attendance.date.desc(), Attendance.id.desc()).offset(skip).limit(limit).all()

    result_items = []
    for record in records:
        # Determine table type and correction info
        if record.is_correction:
            table_type = "correction"
            table_info = f"Корекція: {record.correction_month}.{record.correction_year} #{record.correction_sequence}"
        else:
            table_type = "main"
            table_info = "Основний табель"

        result_items.append({
            "id": record.id,
            "staff_id": record.staff_id,
            "staff": {
                "pib_nom": record.staff.pib_nom if record.staff else "",
                "position": record.staff.position if record.staff else "",
                "rate": float(record.staff.rate) if record.staff and record.staff.rate else 1.0,
            },
            "date": record.date.isoformat() if record.date else None,
            "date_end": record.date_end.isoformat() if record.date_end else None,
            "code": record.code,
            "hours": float(record.hours) if record.hours else 0,
            "notes": record.notes,
            "table_type": table_type,
            "table_info": table_info,
            "is_correction": record.is_correction,
            "correction_month": record.correction_month,
            "correction_year": record.correction_year,
            "correction_sequence": record.correction_sequence,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        })

    return {
        "items": result_items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/daily")
async def get_daily_attendance(
    date: str,
    department: Optional[str] = None,
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Отримати відвідуваність за день.
    """
    query = db.query(Attendance).filter(
        func.date(Attendance.date) == date
    )

    if department:
        query = query.join(Staff).filter(Staff.department == department)

    records = query.order_by(Attendance.created_at).all()

    # Calculate stats based on attendance codes
    stats = {"present": 0, "absent": 0, "late": 0, "remote": 0}

    result_items = []
    for record in records:
        # Determine status from attendance code
        if record.code == "Р":
            status = "present"
            stats["present"] += 1
        elif record.code in ("ПР", "С"):
            status = "absent"
            stats["absent"] += 1
        elif record.code == "РС":
            status = "remote"
            stats["remote"] += 1
        else:
            status = "present"

        result_items.append({
            "id": record.id,
            "staff_id": record.staff_id,
            "staff": {
                "pib_nom": record.staff.pib_nom if record.staff else "",
                "position": record.staff.position if record.staff else "",
                "rate": record.staff.rate if record.staff else 1.0,
            },
            "date": record.date.isoformat() if record.date else None,
            "code": record.code,
            "hours": float(record.hours) if record.hours else 0,
            "notes": record.notes,
            "is_correction": record.is_correction,
        })

    return {
        "items": result_items,
        "total": len(records),
        "date": date,
        **stats,
    }


@router.post("")
async def create_attendance(
    staff_id: int,
    date: str,
    code: str,
    notes: Optional[str] = None,
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Створити запис відвідуваності.
    """
    from datetime import date as date_type

    parsed_date = date_type.fromisoformat(date) if isinstance(date, str) else date
    attendance = Attendance(
        staff_id=staff_id,
        date=parsed_date,
        code=code,
        hours=8.0,
        notes=notes,
    )
    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return {
        "id": attendance.id,
        "staff_id": attendance.staff_id,
        "date": attendance.date.isoformat() if attendance.date else None,
        "code": attendance.code,
    }


@router.post("/correction")
async def submit_correction(
    attendance_id: int,
    new_code: str,
    reason: str,
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Подати запит на виправлення відвідуваності.
    """
    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id
    ).first()

    if not attendance:
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    # Update the attendance record
    attendance.code = new_code
    attendance.is_correction = True
    attendance.correction_month = attendance.date.month
    attendance.correction_year = attendance.date.year
    attendance.notes = reason
    db.commit()

    return {"message": "Запис оновлено"}


@router.post("/submit")
async def submit_tabel(
    year: int,
    month: int,
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Подати табель на затвердження (позначаємо місяць як поданий).
    """
    # Update all attendance records for the month to be non-correctable
    records = db.query(Attendance).filter(
        func.extract("year", Attendance.date) == year,
        func.extract("month", Attendance.date) == month,
    ).all()

    for record in records:
        record.is_correction = False

    db.commit()

    return {"message": "Табель подано на затвердження", "records_count": len(records)}


@router.post("/tabel/approve")
async def approve_tabel(
    year: int,
    month: int,
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Затвердити табель.
    """
    return {"message": f"Табель за {month}/{year} затверджено", "approved_by": current_user.user_id}


@router.get("/tabel")
async def get_tabel(
    year: int,
    month: int,
    db: DBSession = None,
    current_user = Depends(require_department_head),
):
    """
    Отримати табель за місяць.
    """
    records = db.query(Attendance).filter(
        func.extract("year", Attendance.date) == year,
        func.extract("month", Attendance.date) == month,
    ).all()

    return {
        "id": 0,
        "year": year,
        "month": month,
        "status": "approved",
        "attendance_records": [
            {
                "id": r.id,
                "staff_id": r.staff_id,
                "date": r.date,
                "code": r.code,
                "hours": float(r.hours) if r.hours else 0,
                "is_locked": r.is_correction,
            }
            for r in records
        ],
    }
