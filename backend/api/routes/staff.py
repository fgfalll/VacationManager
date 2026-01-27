"""API маршрути для управління співробітниками."""

from typing import Annotated
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import DBSession
from backend.core.dependencies import get_current_user, require_admin, require_department_head, require_employee
from backend.models.staff import Staff
from backend.models.document import Document
from backend.models.schedule import AnnualSchedule
from backend.models.attendance import Attendance
from backend.schemas.staff import StaffCreate, StaffListResponse, StaffResponse, StaffUpdate
from backend.services.staff_service import StaffService
from shared.enums import EmploymentType

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", response_model=StaffListResponse)
async def list_staff(
    db: DBSession,
    skip: int = Query(0, ge=0, description="Кількість записів для пропуску"),
    limit: int = Query(50, ge=1, le=1000, description="Кількість записів на сторінці"),
    is_active: bool | None = Query(None, description="Фільтр за активністю"),
    employment_type: EmploymentType | None = Query(None, description="Фільтр за типом працевлаштування"),
    search: str | None = Query(None, description="Пошук за ПІБ"),
    filter: str | None = Query(None, description="Фільтр: 'expiring' для контрактів, що скоро закінчуються"),
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати список співробітників з пагінацією та фільтрацією.

    Дозволяє отримати список всіх співробітників компанії з можливістю фільтрації за статусом, типом працевлаштування та пошуком.

    Parameters:
    - **skip** (int): Кількість записів для пропуску (для пагінації).
    - **limit** (int): Максимальна кількість записів на сторінці.
    - **is_active** (bool, optional): Фільтр за активністю (True - активні, False - звільнені).
    - **employment_type** (str, optional): Фільтр за типом працевлаштування (main/external/internal).
    - **search** (str, optional): Пошуковий рядок (пошук за ПІБ).
    - **filter** (str, optional): Спеціальні фільтри (наприклад, 'expiring' для контрактів, що закінчуються).

    Returns:
    - **items**: Список об'єктів StaffResponse.
    - **total**: Загальна кількість записів, що відповідають фільтрам.
    - **page**: Номер поточної сторінки.
    - **page_size**: Розмір сторінки.
    """
    query = db.query(Staff)

    if is_active is not None:
        query = query.filter(Staff.is_active == is_active)

    if employment_type is not None:
        query = query.filter(Staff.employment_type == employment_type)

    if search:
        query = query.filter(Staff.pib_nom.ilike(f"%{search}%"))

    # Filter for expiring contracts (within 30 days)
    if filter == 'expiring':
        deadline = date.today() + timedelta(days=30)
        query = query.filter(
            Staff.is_active == True,
            Staff.term_end <= deadline,
        )

    total = int(query.count())
    items = query.order_by(Staff.pib_nom).offset(skip).limit(limit).all()

    # Додаємо computed properties
    result_items = []
    for staff in items:
        staff_dict = StaffResponse.model_validate(staff).model_dump()
        staff_dict["days_until_term_end"] = staff.days_until_term_end
        staff_dict["is_term_expiring_soon"] = staff.is_term_expiring_soon
        result_items.append(StaffResponse(**staff_dict))

    return StaffListResponse(
        items=result_items,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get("/{staff_id}", response_model=StaffResponse)
async def get_staff(
    staff_id: int,
    db: DBSession,
    current_user: get_current_user = Depends(require_department_head),
):
    """
    Отримати детальні дані співробітника за його ID.

    Повертає повну картку співробітника, включаючи інформацію про статус контракту та додаткові
    обчислювані поля для фронтенду.

    Parameters:
    - **staff_id** (int): Унікальний ідентифікатор співробітника.

    Returns:
    - Об'єкт StaffResponse з повною інформацією.

    Errors:
    - **404 Not Found**: Якщо співробітника з таким ID не знайдено.
    """
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    response = StaffResponse.model_validate(staff)
    response.days_until_term_end = staff.days_until_term_end
    response.is_term_expiring_soon = staff.is_term_expiring_soon
    # Add frontend-compatible aliases
    response.start_date = staff.term_start
    response.end_date = staff.term_end
    # Add frontend-compatible name fields from pib_nom (format: "Прізвище Ім'я По батькові")
    name_parts = staff.pib_nom.split()
    response.last_name = name_parts[0] if name_parts else ""  # Прізвище
    response.first_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""  # Ім'я По батькові
    # Add frontend-compatible status field
    response.status = "active" if staff.is_active else "inactive"

    return response


@router.post("", response_model=StaffResponse, status_code=201)
async def create_staff(
    staff_data: StaffCreate,
    db: DBSession,
    current_user: get_current_user = Depends(require_admin),
):
    """
    Створити нового співробітника.

    Додає новий запис до бази даних співробітників.
    Автоматично перевіряє унікальність ПІБ.
    Записує дію створення в історію змін.

    Parameters:
    - **staff_data** (StaffCreate): Дані нового співробітника (ПІБ, посада, ставка, дати та ін.).

    Returns:
    - Об'єкт StaffResponse створеного співробітника.

    Errors:
    - **400 Bad Request**: Якщо співробітник з таким ПІБ вже існує.
    """
    # Перевірка на унікальність ПІБ
    existing = db.query(Staff).filter(Staff.pib_nom == staff_data.pib_nom).first()
    if existing:
        raise HTTPException(status_code=400, detail="Співробітник з таким ПІБ вже існує")

    # Use StaffService to create with history logging
    user_identifier = current_user.username or current_user.email or str(current_user.id)
    service = StaffService(db, changed_by=user_identifier)

    staff = service.create_staff(staff_data.model_dump())
    db.commit()
    db.refresh(staff)

    return StaffResponse.model_validate(staff)


@router.put("/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: int,
    staff_data: StaffUpdate,
    db: DBSession,
    current_user: get_current_user = Depends(require_department_head),
):
    """
    Оновити дані існуючого співробітника.

    Оновлює поля профілю співробітника.
    Записує всі зміни (старе та нове значення) в історію змін (audit info).

    Parameters:
    - **staff_id** (int): ID співробітника.
    - **staff_data** (StaffUpdate): Поля для оновлення.

    Returns:
    - Оновлений об'єкт StaffResponse.

    Errors:
    - **404 Not Found**: Якщо співробітника не знайдено.
    """
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    update_data = staff_data.model_dump(exclude_unset=True)

    # Use StaffService to update with history logging
    user_identifier = current_user.username or current_user.email or str(current_user.id)
    service = StaffService(db, changed_by=user_identifier)

    service.update_staff(staff, update_data)
    db.commit()
    db.refresh(staff)

    return StaffResponse.model_validate(staff)


@router.delete("/{staff_id}", status_code=204)
async def delete_staff(
    staff_id: int,
    db: DBSession,
    current_user: get_current_user = Depends(require_admin),
):
    """
    Деактивувати (видалити) співробітника.

    Виконує "м'яке видалення" (soft delete): встановлює прапорець `is_active=False`
    та записує дату звільнення. Фізично запис з бази не видаляється для
    збереження історії та цілісності даних документів.

    Parameters:
    - **staff_id** (int): ID співробітника.

    Errors:
    - **404 Not Found**: Якщо співробітника не знайдено.
    """
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    # Use StaffService to deactivate with history logging
    user_identifier = current_user.username or current_user.email or str(current_user.id)
    service = StaffService(db, changed_by=user_identifier)

    service.deactivate_staff(staff, reason="Видалено через API")
    db.commit()

    return None


@router.get("/expiring-soon")
async def get_staff_with_expiring_contracts(
    db: DBSession,
    days: int = Query(30, ge=1, le=365, description="Кількість днів для попередження"),
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати список співробітників з контрактами, що закінчуються.

    Повертає список активних співробітників, у яких дата закінчення контракту (`term_end`)
    припадає на найближчі N днів.

    Parameters:
    - **days** (int): Кількість днів для перевірки (за замовчуванням 30).

    Returns:
    - Список співробітників з додатковими полями для UI.
    """
    deadline = date.today() + timedelta(days=days)

    query = db.query(Staff).filter(
        Staff.is_active == True,
        Staff.term_end <= deadline,
    )

    total = int(query.count())
    items = query.order_by(Staff.term_end).all()

    return {
        "items": [
            {
                "id": staff.id,
                "pib_nom": staff.pib_nom,
                "position": staff.position,
                "employment_type": staff.employment_type,
                "work_basis": staff.work_basis,
                "rate": float(staff.rate) if staff.rate else 0,
                "term_start": staff.term_start.isoformat() if staff.term_start else None,
                "term_end": staff.term_end.isoformat() if staff.term_end else None,
                "is_active": staff.is_active,
            }
            for staff in items
        ],
        "total": total,
        "page": 1,
        "page_size": total,
    }


@router.get("/search")
async def search_staff(
    q: str,
    db: DBSession = None,
    current_user: get_current_user = Depends(require_department_head),
):
    """
    Швидкий пошук співробітників (для автодоповнення).

    Шукає активних співробітників за входженням рядка в ПІБ або назву посади.
    Повертає обмежений список результатів (до 20 записів) у спрощеному форматі.

    Parameters:
    - **q** (str): Рядок пошуку.

    Returns:
    - Список скорочених об'єктів співробітників.
    """
    query = db.query(Staff).filter(
        Staff.is_active == True,
        (Staff.pib_nom.ilike(f"%{q}%") | Staff.position.ilike(f"%{q}%"))
    ).limit(20).all()

    return [
        {
            "id": staff.id,
            "name": staff.pib_nom,
            "position": staff.position,
            "department": staff.department,
            "annual_leave_days": staff.annual_leave_days,
            "sick_leave_days": staff.sick_leave_days,
        }
        for staff in query
    ]


@router.get("/{staff_id}/documents", response_model=list)
async def get_staff_documents(
    staff_id: int,
    db: DBSession = None,
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати історію документів співробітника.

    Повертає список всіх документів, пов'язаних з цим співробітником,
    відсортований за датою створення (нові спочатку).

    Parameters:
    - **staff_id** (int): ID співробітника.

    Returns:
    - Список документів з адаптованими для фронтенду полями.
    """
    from backend.schemas.document import DocumentResponse

    documents = db.query(Document).filter(Document.staff_id == staff_id).order_by(
        Document.created_at.desc()
    ).all()

    result = []
    for doc in documents:
        response = DocumentResponse.model_validate(doc)
        # Add title and document_type for frontend compatibility
        if doc.doc_type:
            response.title = doc.doc_type.name.replace("_", " ").title()
            response.document_type = {
                "id": doc.doc_type.value,
                "name": doc.doc_type.name.replace("_", " ").title()
            }
        # Add frontend-compatible date aliases
        response.start_date = doc.date_start
        response.end_date = doc.date_end
        result.append(response)

    return result


@router.get("/{staff_id}/schedule", response_model=list)
async def get_staff_schedule(
    staff_id: int,
    db: DBSession = None,
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати графік відпусток конкретного співробітника.

    Повертає всі заплановані періоди відпусток з річного графіку для цього співробітника.
    Сортування за роком та датою початку.

    Parameters:
    - **staff_id** (int): ID співробітника.

    Returns:
    - Список записів графіку відпусток.
    """
    from backend.schemas.schedule import ScheduleEntryResponse

    schedule_entries = db.query(AnnualSchedule).filter(
        AnnualSchedule.staff_id == staff_id
    ).order_by(AnnualSchedule.year, AnnualSchedule.planned_start).all()

    return [
        ScheduleEntryResponse.model_validate(entry) for entry in schedule_entries
    ]


@router.get("/{staff_id}/attendance", response_model=list)
async def get_staff_attendance(
    staff_id: int,
    db: DBSession,
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати історію відвідуваності та відсутностей співробітника.

    Повертає записи табеля (робочі дні, відпустки, лікарняні) для співробітника.

    Parameters:
    - **staff_id** (int): ID співробітника.

    Returns:
    - Список записів відвідуваності (Attendance).
    """
    attendance_records = db.query(Attendance).filter(
        Attendance.staff_id == staff_id
    ).order_by(Attendance.date.desc()).all()

    # Convert to dict with proper date format
    result = []
    for record in attendance_records:
        result.append({
            "id": record.id,
            "staff_id": record.staff_id,
            "date": record.date.isoformat() if record.date else None,
            "code": record.code,
            "hours": float(record.hours) if record.hours else 0,
            "notes": record.notes,
            "is_correction": record.is_correction,
            "correction_month": record.correction_month,
            "correction_year": record.correction_year,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        })

    return result


@router.get("/{staff_id}/history", response_model=list)
async def get_staff_history(
    staff_id: int,
    db: DBSession,
    current_user: get_current_user = Depends(require_department_head),
):
    """
    Отримати повний журнал змін (audit log) по співробітнику.

    Показує хто, коли і які зміни вносив у картку співробітника.

    Parameters:
    - **staff_id** (int): ID співробітника.

    Returns:
    - Список записів історії змін.
    """
    from backend.models.staff_history import StaffHistory

    history = db.query(StaffHistory).filter(
        StaffHistory.staff_id == staff_id
    ).order_by(StaffHistory.created_at.desc()).all()

    return [
        {
            "id": h.id,
            "staff_id": h.staff_id,
            "action": h.action_type,
            "previous_values": h.previous_values,
            "changed_by": h.changed_by,
            "comment": h.comment,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in history
    ]
