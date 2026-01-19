"""API маршрути для дашборду."""

from datetime import date

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
    total_staff = db.query(func.count(Staff.id)).scalar() or 0

    # Active staff count
    active_staff = db.query(func.count(Staff.id)).filter(Staff.is_active == True).scalar() or 0

    # Pending documents (draft + on_signature)
    pending_documents = db.query(func.count(Document.id)).filter(
        Document.status.in_([DocumentStatus.DRAFT, DocumentStatus.ON_SIGNATURE])
    ).scalar() or 0

    # Upcoming vacations - check if doc_type name starts with VACATION
    upcoming_vacations = db.query(func.count(Document.id)).filter(
        Document.doc_type.name.startswith('VACATION'),
        Document.date_start >= today,
        Document.status.in_([DocumentStatus.AGREED, DocumentStatus.SIGNED])
    ).scalar() or 0

    return {
        "total_staff": total_staff,
        "active_staff": active_staff,
        "pending_documents": pending_documents,
        "upcoming_vacations": upcoming_vacations,
    }
