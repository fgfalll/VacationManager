"""API маршрути для управління документами."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    DBSession,
    DocumentSvc,
    GrammarSvc,
    ValidationSvc,
)
from backend.core.dependencies import get_current_user, require_employee
from backend.models.document import Document
from backend.schemas.document import (
    DocumentCreate,
    DocumentGenerateResponse,
    DocumentResponse,
)
from shared.enums import DocumentStatus, DocumentType

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    staff_id: int | None = Query(None),
    status: DocumentStatus | None = Query(None),
    doc_type: DocumentType | None = Query(None),
    search: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: get_current_user = Depends(require_employee),
):
    """Отримати список документів."""
    query = db.query(Document)

    if staff_id is not None:
        query = query.filter(Document.staff_id == staff_id)
    if status is not None:
        query = query.filter(Document.status == status)
    if doc_type is not None:
        query = query.filter(Document.doc_type == doc_type)

    if search:
        # Search by custom_text or editor_content
        query = query.filter(
            (Document.custom_text.ilike(f"%{search}%")) |
            (Document.editor_content.ilike(f"%{search}%"))
        )

    if start_date:
        query = query.filter(Document.created_at >= start_date)
    if end_date:
        query = query.filter(Document.created_at <= end_date)

    total = query.count()
    items = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

    # Return simplified response using correct field names
    result_items = []
    for doc in items:
        staff = doc.staff
        # Generate title from doc_type
        doc_title = doc.doc_type.name.replace("_", " ").title() if doc.doc_type else "Документ"
        result_items.append({
            "id": doc.id,
            "staff_id": doc.staff_id,
            "staff": {
                "id": staff.id if staff else 0,
                "pib_nom": staff.pib_nom if staff else "",
                "position": staff.position if staff else "",
            },
            "doc_type": doc.doc_type.value if doc.doc_type else None,
            "document_type": {
                "id": doc.doc_type.value if doc.doc_type else "",
                "name": doc.doc_type.name.replace("_", " ").title() if doc.doc_type else "",
            },
            "title": doc_title,
            "content": doc.editor_content or doc.custom_text or "",
            "status": doc.status.value if doc.status else "draft",
            "date_start": doc.date_start.isoformat() if doc.date_start else None,
            "date_end": doc.date_end.isoformat() if doc.date_end else None,
            "days_count": doc.days_count,
            "extension_start_date": doc.extension_start_date.isoformat() if doc.extension_start_date else None,
            "old_contract_end_date": doc.old_contract_end_date.isoformat() if doc.old_contract_end_date else None,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "staff_name": staff.pib_nom if staff else "",
            "staff_position": staff.position if staff else "",
            "progress": doc.get_workflow_progress() if hasattr(doc, 'get_workflow_progress') else {},
        })

    return {
        "data": result_items,
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: DBSession,
    current_user: get_current_user = Depends(require_employee),
):
    """Отримати документ за ID."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    staff = doc.staff
    # Generate title from doc_type
    doc_title = doc.doc_type.name.replace("_", " ").title() if doc.doc_type else "Документ"
    return {
        "id": doc.id,
        "staff_id": doc.staff_id,
        "doc_type": doc.doc_type.value if doc.doc_type else None,
        "title": doc_title,
        "content": doc.editor_content or doc.custom_text or "",
        "status": doc.status.value if doc.status else "draft",
        "date_start": doc.date_start.isoformat() if doc.date_start else None,
        "date_end": doc.date_end.isoformat() if doc.date_end else None,
        "days_count": doc.days_count,
        "extension_start_date": doc.extension_start_date.isoformat() if doc.extension_start_date else None,
        "old_contract_end_date": doc.old_contract_end_date.isoformat() if doc.old_contract_end_date else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "staff_name": staff.pib_nom if staff else "",
        "staff_position": staff.position if staff else "",
        "file_docx_path": doc.file_docx_path,
        "file_scan_path": doc.file_scan_path,
        "progress": doc.get_workflow_progress() if hasattr(doc, 'get_workflow_progress') else {},
    }


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    doc_data: DocumentCreate,
    db: DBSession,
    validation: ValidationSvc,
    current_user: get_current_user = Depends(require_employee),
):
    """Створити новий документ."""
    from backend.models.staff import Staff

    staff = db.query(Staff).filter(Staff.id == doc_data.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    # Create document
    document = Document(**doc_data.model_dump())
    db.add(document)
    db.commit()
    db.refresh(document)

    return DocumentResponse.model_validate(document)
