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
    Отримати статистику для dashboard.

    Returns:
        dict: Статистика з кількістю працівників, документів та відпусток
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

    # Upcoming vacations - check if doc_type starts with VACATION
    upcoming_vacations = int(db.query(func.count(Document.id)).filter(
        Document.doc_type.startswith('VACATION'),
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
    Отримати кількість документів, створених сьогодні.

    Returns:
        dict: Кількість документів за статусами (draft, pending)
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
    Отримати кількість контрактів, що скоро закінчуються.

    Args:
        days: Кількість днів для перевірки (за замовчуванням 30)

    Returns:
        dict: Кількість працівників з контрактами, що закінчуються
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
