"""API маршрути для дашборду."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func

from backend.api.dependencies import DBSession
from backend.core.dependencies import get_current_user
from backend.models.staff import Staff
from backend.models.document import Document
from shared.enums import DocumentStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    db: DBSession = None,
    current_user=Depends(get_current_user),
):
    """
    Отримати загальну статистику (KPIs).

    Повертає ключові показники для віджетів на головній:
    - Загальна кількість співробітників.
    - Активні співробітники.
    - Документи в роботі (pending).
    - Найближчі відпустки (upcoming info).
    """
    today = date.today()

    # Total staff count
    total_staff = int(db.query(func.count(Staff.id)).scalar() or 0)

    # Active staff count
    active_staff = int(db.query(func.count(Staff.id)).filter(Staff.is_active == True).scalar() or 0)

    # Pending documents (all non-draft, non-processed statuses)
    pending_statuses = [
        DocumentStatus.SIGNED_BY_APPLICANT,
        DocumentStatus.APPROVED_BY_DISPATCHER,
        DocumentStatus.SIGNED_DEP_HEAD,
        DocumentStatus.AGREED,
        DocumentStatus.SIGNED_RECTOR,
        DocumentStatus.SCANNED,
    ]
    pending_documents = int(db.query(func.count(Document.id)).filter(
        Document.status.in_(pending_statuses)
    ).scalar() or 0)

    # Upcoming vacations - filter by explicit vacation types
    vacation_types = [
        "vacation_paid", "vacation_unpaid", "vacation_main", "vacation_additional",
        "vacation_chornobyl", "vacation_creative", "vacation_study", "vacation_children",
        "vacation_maternity", "vacation_childcare", "vacation_unpaid_study",
        "vacation_unpaid_mandatory", "vacation_unpaid_agreement", "vacation_unpaid_other"
    ]
    
    upcoming_vacations = int(db.query(func.count(Document.id)).filter(
        Document.doc_type.in_(vacation_types),
        Document.date_start >= today,
        Document.status.in_([DocumentStatus.AGREED, DocumentStatus.SIGNED_RECTOR])
    ).scalar() or 0)

    return {
        "total_staff": total_staff,
        "active_staff": active_staff,
        "pending_documents": pending_documents,
        "upcoming_vacations": upcoming_vacations,
    }


@router.get("/today")
async def get_today_documents(
    db: DBSession = None,
    current_user=Depends(get_current_user),
):
    """
    Отримати активність за сьогодні.

    Повертає лічильники створених сьогодні документів
    (в статусах draft та pending).
    Показує продуктивність за день.
    """
    today = date.today()
    today_start = today
    today_end = today + timedelta(days=1)

    # Drafts created today
    draft_count = int(db.query(func.count(Document.id)).filter(
        Document.created_at >= today_start,
        Document.created_at < today_end,
        Document.status == DocumentStatus.DRAFT
    ).scalar() or 0)

    # Pending documents created today (not draft, not processed)
    pending_count = int(db.query(func.count(Document.id)).filter(
        Document.created_at >= today_start,
        Document.created_at < today_end,
        Document.status != DocumentStatus.DRAFT,
        Document.status != DocumentStatus.PROCESSED
    ).scalar() or 0)

    return {
        "draft": draft_count,
        "pending": pending_count,
    }


@router.get("/contract-expiring")
async def get_expiring_contracts(
    db: DBSession = None,
    current_user=Depends(get_current_user),
    days: int = 30,
):
    """
    Моніторинг закінчення контрактів.

    Повертає кількість співробітників, у яких закінчується термін дії договору
    протягом вказаного періоду (days).

    Parameters:
    - **days**: Поріг попередження (днів).
    """
    today = date.today()
    future_date = today + timedelta(days=days)

    # Count active employees with contracts ending within N days
    expiring_count = int(db.query(func.count(Staff.id)).filter(
        Staff.is_active == True,
        Staff.term_end >= today,
        Staff.term_end <= future_date
    ).scalar() or 0)

    return {
        "count": expiring_count,
        "days_threshold": days,
    }
