"""API маршрути для табеля обліку робочого часу."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import DBSession
from backend.core.dependencies import get_current_user, require_department_head
from backend.services.tabel_service import (
    generate_tabel_html,
    save_tabel_archive,
    list_tabel_archives,
    reconstruct_tabel_from_archive,
    reconstruct_tabel_html_from_archive,
)
from backend.services.tabel_approval_service import TabelApprovalService
from backend.models.settings import SystemSettings

router = APIRouter(prefix="/tabel", tags=["tabel"])


@router.get("/generate")
async def generate_tabel(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    is_correction: bool = Query(
        False, description="Whether this is a correction tabel"
    ),
    correction_month: Optional[int] = Query(
        None, ge=1, le=12, description="Correction month"
    ),
    correction_year: Optional[int] = Query(
        None, ge=2020, le=2100, description="Correction year"
    ),
    db: DBSession = None,
    current_user=Depends(require_department_head),
):
    """
    Згенерувати HTML друкованої форми табеля.

    Створює стандартну друковану форму П-5.
    Підтримує генерацію як для основного табеля, так і для коригуючого.
    Використовує параметри організації з налаштувань.

    Parameters:
    - **month/year**: Період табеля.
    - **is_correction**: Чи генерувати форму коригування.
    - **correction_month/year**: Період, за який робиться корекція (якщо is_correction=True).

    Returns:
    - HTML код сторінки для друку.
    """
    try:
        # Get settings from database
        institution_name = SystemSettings.get_value(db, "institution_name", "ЦНТУ")
        edrpou_code = SystemSettings.get_value(db, "edrpou_code", "02065502")

        html = generate_tabel_html(
            month=month,
            year=year,
            institution_name=institution_name,
            edrpou_code=edrpou_code,
            is_correction=is_correction,
            correction_month=correction_month,
            correction_year=correction_year,
        )

        return {
            "html": html,
            "month": month,
            "year": year,
            "is_correction": is_correction,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Помилка генерації табеля: {str(e)}"
        )


@router.get("/preview")
async def preview_tabel(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    db: DBSession = None,
    current_user=Depends(require_department_head),
):
    """
    Попередній перегляд табеля.

    Генерує HTML для швидкого перегляду без параметрів корекції.
    Використовується для перевірки вигляду перед друком.
    """
    try:
        institution_name = SystemSettings.get_value(db, "institution_name", "ЦНТУ")
        edrpou_code = SystemSettings.get_value(db, "edrpou_code", "02065502")

        html = generate_tabel_html(
            month=month,
            year=year,
            institution_name=institution_name,
            edrpou_code=edrpou_code,
        )

        return {"html": html}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Помилка попереднього перегляду: {str(e)}"
        )


@router.post("/archive")
async def create_tabel_archive(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    is_correction: bool = Query(
        False, description="Whether this is a correction tabel"
    ),
    correction_month: Optional[int] = Query(
        None, ge=1, le=12, description="Correction month"
    ),
    correction_year: Optional[int] = Query(
        None, ge=2020, le=2100, description="Correction year"
    ),
    correction_sequence: int = Query(1, ge=1, description="Correction sequence number"),
    db: DBSession = None,
    current_user=Depends(require_department_head),
):
    """
    Створити незмінний архів табеля (Snapshot).

    Зберігає поточний стан табеля у вигляді JSON-архіву.
    Це дозволяє відтворити точний вигляд табеля на момент закриття місяця,
    навіть якщо дані співробітників зміняться.

    Parameters:
    - **correction_sequence**: Номер версії корекції (якщо застосовно).

    Returns:
    - Шлях до збереженого файлу архіву.
    """
    try:
        institution_name = SystemSettings.get_value(db, "institution_name", "ЦНТУ")
        edrpou_code = SystemSettings.get_value(db, "edrpou_code", "02065502")

        archive_path = save_tabel_archive(
            month=month,
            year=year,
            institution_name=institution_name,
            edrpou_code=edrpou_code,
            is_correction=is_correction,
            correction_month=correction_month,
            correction_year=correction_year,
            correction_sequence=correction_sequence,
        )

        return {
            "success": True,
            "path": str(archive_path),
            "message": "Архів табеля збережено",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Помилка збереження архіву: {str(e)}"
        )


@router.get("/archives")
async def get_tabel_archives(
    current_user=Depends(require_department_head),
):
    """
    Отримати список всіх збережених архівів.

    Сканує директорію архівів та повертає структурований список файлів.
    Файли групуються за роком та місяцем.

    Returns:
    - Дерево архівів (Main та Corrections).
    """
    try:
        archives = list_tabel_archives()
        return archives
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Помилка отримання архівів: {str(e)}"
        )


@router.get("/archives/{archive_filename}")
async def get_archive_detail(
    archive_filename: str,
    current_user=Depends(require_department_head),
):
    """
    Відтворити табель з архівного файлу.

    Завантажує дані з JSON-файлу та рендерить HTML.
    Дозволяє переглядати історичні табелі точно такими, якими вони були збережені.

    Parameters:
    - **archive_filename**: Ім'я файлу архіву.

    Returns:
    - Деталі архіву та відновлений HTML.
    """
    try:
        # Construct archive path
        archive_dir = Path(__file__).parent.parent.parent.parent / "tabel" / "archive"
        archive_path = archive_dir / archive_filename

        if not archive_path.exists():
            raise HTTPException(status_code=404, detail="Архів не знайдено")

        archive_data = reconstruct_tabel_from_archive(archive_path)
        html = reconstruct_tabel_html_from_archive(archive_data)

        return {
            "archive_data": archive_data,
            "html": html,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Помилка відтворення архіву: {str(e)}"
        )


@router.get("/locked-months")
async def get_locked_months(
    db: DBSession = None,
    current_user=Depends(require_department_head),
):
    """
    Отримати список закритих (заблокованих) місяців.

    Місяць вважається закритим, якщо він був поданий на затвердження
    або автоматично закрився системою (налаштовується).
    У закритих місяцях заборонено пряме редагування відвідуваності.

    Returns:
    - Список об'єктів {month, year, is_locked, approved_by}.
    """
    service = TabelApprovalService(db)
    locked_months = service.get_locked_months()
    return {"locked_months": locked_months}


@router.get("/corrections")
async def get_correction_months(
    db: DBSession = None,
    current_user=Depends(require_department_head),
):
    """
    Отримати доступні періоди корегування.

    Повертає список місяців, для яких існують або відкриті сесії корегування.
    Зазвичай показує останні активні коригування.

    Returns:
    - Список періодів.
    """
    service = TabelApprovalService(db)
    corrections = service.get_correction_months()
    return {"corrections": corrections}


@router.post("/approve")
async def approve_tabel(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    is_correction: bool = Query(
        False, description="Whether this is a correction tabel"
    ),
    correction_month: Optional[int] = Query(
        None, ge=1, le=12, description="Correction month"
    ),
    correction_year: Optional[int] = Query(
        None, ge=2020, le=2100, description="Correction year"
    ),
    correction_sequence: int = Query(1, ge=1, description="Correction sequence number"),
    db: DBSession = None,
    current_user=Depends(require_department_head),
):
    """
    Затвердити табель (фінальний підпис).

    Ставить відмітку про перевірку табеля кадровою службою.
    Після цього табель готовий до друку та архівування.

    Returns:
    - Статус операції.
    """
    service = TabelApprovalService(db)

    try:
        result = service.confirm_approval(
            month=month,
            year=year,
            is_correction=is_correction,
            correction_month=correction_month,
            correction_year=correction_year,
            correction_sequence=correction_sequence,
            user=current_user.user_id if hasattr(current_user, "user_id") else "user",
        )

        return {
            "success": True,
            "message": f"Табель за {month}/{year} погоджено",
            "result": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def get_tabel_status(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    db: DBSession = None,
    current_user=Depends(require_department_head),
):
    """
    Перевірити статус табеля.

    Повертає інформацію про стан місяця:
    - is_locked: чи закритий для редагування.
    - should_show_warning: чи потрібно попередити користувача про щось (наприклад, незаповнені дні).
    """
    service = TabelApprovalService(db)

    is_locked = service.is_month_locked(month, year)
    should_warn = service.should_show_warning(month, year)

    return {
        "month": month,
        "year": year,
        "is_locked": is_locked,
        "should_show_warning": should_warn,
    }
