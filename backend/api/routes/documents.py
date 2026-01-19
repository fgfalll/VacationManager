"""API маршрути для управління документами."""

from datetime import date, datetime, timedelta
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    DBSession,
    DocumentSvc,
    GrammarSvc,
    GrammarSvc,
    ValidationSvc,
    ValidationSvc,
    get_db,
)
from backend.core.dependencies import get_current_user, require_employee
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from backend.models.document import Document
from backend.models.attendance import Attendance, ATTENDANCE_CODES
from backend.schemas.document import (
    DocumentCreate,
    DocumentGenerateResponse,
    DocumentResponse,
    PreviewResponse,
)
from backend.schemas.auth import TokenData
from backend.services.document_renderer import render_document
from shared.enums import DocumentStatus, DocumentType

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/types")
async def get_document_types():
    """Отримати список типів документів."""
    return [
        {
            "id": dt.value,
            "name": dt.name.replace("_", " ").title(),
            "description": dt.value,
        }
        for dt in DocumentType
    ]


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
    needs_scan: bool = Query(False),
    current_user: get_current_user = Depends(require_employee),
):
    """Отримати список документів."""
    query = db.query(Document)

    if needs_scan:
        # Filter documents that are signed or processed but don't have a scan yet
        query = query.filter(
            Document.status.in_([DocumentStatus.SIGNED, DocumentStatus.PROCESSED]),
            Document.file_scan_path.is_(None)
        )
    else:
        # Normal filters
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

        # Always re-render to use the correct template
        doc.rendered_html = render_document(doc, db)

        # Get blocking status from database (stored field)
        is_blocked = doc.is_blocked
        blocked_reason = doc.blocked_reason

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
            "rendered_html": doc.rendered_html,
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
            "file_scan_path": doc.file_scan_path,
            "is_blocked": is_blocked,
            "blocked_reason": blocked_reason,
            "progress": doc.get_workflow_progress() if hasattr(doc, 'get_workflow_progress') else {},
        })

    db.commit()  # Save any updated rendered_html values

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
    from backend.services.document_service import get_document_context_for_display
    
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    # Get context from archive if available, otherwise from DB
    context = get_document_context_for_display(doc, db)
    
    # Use archived staff data if from archive, otherwise use live data
    if context.get("from_archive"):
        staff_data = context.get("staff", {})
        staff_name = staff_data.get("pib_nom", "")
        staff_position = staff_data.get("position", "")
    else:
        staff = doc.staff
        staff_name = staff.pib_nom if staff else ""
        staff_position = staff.position if staff else ""
        # Re-render for drafts/non-archived documents
        doc.rendered_html = render_document(doc, db)
        db.commit()
    
    # Generate title from doc_type
    doc_title = doc.doc_type.name.replace("_", " ").title() if doc.doc_type else "Документ"
    
    # Use rendered_html from context (archive) or document
    rendered_html = context.get("rendered_html") or doc.rendered_html

    return {
        "id": doc.id,
        "staff_id": doc.staff_id,
        "doc_type": doc.doc_type.value if doc.doc_type else None,
        "title": doc_title,
        "content": doc.editor_content or doc.custom_text or "",
        "rendered_html": rendered_html,
        "status": doc.status.value if doc.status else "draft",
        "date_start": doc.date_start.isoformat() if doc.date_start else None,
        "date_end": doc.date_end.isoformat() if doc.date_end else None,
        "days_count": doc.days_count,
        "extension_start_date": doc.extension_start_date.isoformat() if doc.extension_start_date else None,
        "old_contract_end_date": doc.old_contract_end_date.isoformat() if doc.old_contract_end_date else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "staff_name": staff_name,
        "staff_position": staff_position,
        "file_docx_path": doc.file_docx_path,
        "file_scan_path": doc.file_scan_path,
        "archive_metadata_path": doc.archive_metadata_path,
        "from_archive": context.get("from_archive", False),
        "progress": doc.get_workflow_progress() if hasattr(doc, 'get_workflow_progress') else {},
        # Include signatories from context (snapshot or live)
        "signatories": context.get("signatories", []),
    }


@router.get("/{document_id}/context")
async def get_document_context(
    document_id: int,
    db: DBSession,
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати повний контекст документа для відображення.
    Повертає дані з архіву якщо документ відскановано, інакше з бази даних.
    """
    from backend.services.document_service import get_document_context_for_display
    
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    context = get_document_context_for_display(doc, db)
    
    return {
        "document_id": document_id,
        "status": doc.status.value if doc.status else "draft",
        "from_archive": context.get("from_archive", False),
        "staff": context.get("staff", {}),
        "signatories": context.get("signatories", []),
        "settings": context.get("settings", {}),
        "rendered_html": context.get("rendered_html", ""),
        "dates": context.get("dates", {}),
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

    # Check for date overlaps with existing documents
    confirmed_statuses = [
        DocumentStatus.ON_SIGNATURE,
        DocumentStatus.SIGNED,
        DocumentStatus.PROCESSED
    ]

    existing_docs = db.query(Document).filter(
        Document.staff_id == doc_data.staff_id,
        Document.status.in_(confirmed_statuses)
    ).all()

    overlapping_docs = []
    for existing_doc in existing_docs:
        if existing_doc.date_start and existing_doc.date_end:
            # Check if date ranges overlap
            if (doc_data.date_start <= existing_doc.date_end and
                doc_data.date_end >= existing_doc.date_start):
                overlapping_docs.append({
                    "id": existing_doc.id,
                    "doc_type": existing_doc.doc_type.name.replace("_", " ").title() if existing_doc.doc_type else "Документ",
                    "date_start": existing_doc.date_start.isoformat(),
                    "date_end": existing_doc.date_end.isoformat(),
                })

    if overlapping_docs:
        overlap_info = ", ".join([f"№{d['id']} ({d['doc_type']}: {d['date_start']} - {d['date_end']})" for d in overlapping_docs])
        raise HTTPException(
            status_code=400,
            detail=f"Обрані дати перетинаються з існуючими документами: {overlap_info}"
        )

    # Check for date overlaps with attendance records (vacation codes from ATTENDANCE_CODES)
    # Get all attendance records with vacation codes for this staff
    all_attendance = db.query(Attendance).filter(
        Attendance.staff_id == doc_data.staff_id,
        Attendance.code.in_(list(ATTENDANCE_CODES.keys()))
    ).all()

    overlapping_attendance = []
    for att in all_attendance:
        att_start = att.date
        att_end = att.date_end if att.date_end else att.date

        # Check if ranges overlap
        if (doc_data.date_start <= att_end and doc_data.date_end >= att_start):
            overlapping_attendance.append({
                "id": att.id,
                "code": att.code,
                "date_start": att_start.isoformat(),
                "date_end": att_end.isoformat(),
            })

    if overlapping_attendance:
        att_info = ", ".join([f"№{a['id']} ({a['code']}: {a['date_start']} - {a['date_end']})" for a in overlapping_attendance])
        raise HTTPException(
            status_code=400,
            detail=f"Обрані дати перетинаються з існуючими відмітками: {att_info}"
        )

    # Calculate days_count from date_start and date_end
    days_count = (doc_data.date_end - doc_data.date_start).days + 1

    # Create document with calculated days_count
    doc_dict = doc_data.model_dump()
    doc_dict['days_count'] = days_count

    document = Document(**doc_dict)

    db.add(document)
    db.commit()
    db.refresh(document)

    # Render and store HTML using db session for settings
    document.rendered_html = render_document(document, db)
    db.commit()

    # Create response with frontend-compatible fields
    response = DocumentResponse.model_validate(document)
    response.title = document.doc_type.name.replace("_", " ").title()
    response.document_type = {
        "id": document.doc_type.value,
        "name": document.doc_type.name.replace("_", " ").title()
    }
    response.start_date = document.date_start
    response.end_date = document.date_end

    return response


@router.post("/{document_id}/upload-scan")
async def upload_document_scan(
    document_id: int,
    db: DBSession,
    file: UploadFile = File(...),
    current_user: get_current_user = Depends(require_employee),
):
    """Завантажити скан-копію документа."""

    # ... (code omitted)

    # 6. Update document
    document.file_scan_path = file_path
    document.is_blocked = True
    document.blocked_reason = "Документ має завантажений скан. Редагування заблоковано."
    document.scanned_at = datetime.now()
    document.scanned_comment = f"Uploaded via Web Portal by {current_user.username or 'Unknown'}"

    # Update status based on workflow
    document.update_status_from_workflow()
    
    db.commit()
    db.refresh(document)
    
    return {"message": "Скан успішно завантажено", "file_path": file_path}


@router.post("/direct-scan-upload")
async def direct_scan_upload(
    db: DBSession,
    staff_id: int = Query(...),
    doc_type: str = Query(...),
    date_start: str = Query(...),
    date_end: str = Query(...),
    days_count: int = Query(...),
    file: UploadFile = File(...),
    current_user: TokenData = Depends(require_employee),
):
    """
    Пряме завантаження скану (створення документу та завантаження файлу).
    Логіка аналогічна desktop/ui/employee_card_dialog.py.
    """
    from backend.services.attendance_service import AttendanceService
    from decimal import Decimal

    # Parse dates
    try:
        dt_start = datetime.strptime(date_start, "%Y-%m-%d").date()
        dt_end = datetime.strptime(date_end, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Невірний формат дати (YYYY-MM-DD)")

    # 1. Create document entry
    document = Document(
        staff_id=staff_id,
        doc_type=DocumentType(doc_type),
        date_start=dt_start,
        date_end=dt_end,
        days_count=days_count,
        payment_period="Скан завантажено вручну",
        status=DocumentStatus.SIGNED,  # Already signed by default
        tabel_added_comment="Додано зі скану (документ створено співробітником самостійно via Web)",
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Render document HTML using the same logic as document preview
    document.rendered_html = render_document(document, db)
    db.commit()

    # 2. Save file
    storage_dir = os.path.join("storage", "scans")
    os.makedirs(storage_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = file.filename.split(".")[-1]
    filename = f"scan_{document.id}_{timestamp}.{ext}"
    file_path = os.path.join(storage_dir, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        db.delete(document) # Rollback document creation on file failure
        db.commit()
        raise HTTPException(status_code=500, detail=f"Помилка збереження файлу: {str(e)}")

    document.file_scan_path = file_path
    document.is_blocked = True
    document.blocked_reason = "Документ має завантажений скан. Редагування заблоковано."
    document.scanned_at = datetime.now()
    document.scanned_comment = f"Uploaded via Web Portal by {current_user.username or 'Unknown'}"
    document.scanned_comment = f"Uploaded via Web Portal by {current_user.username or 'Unknown'}"
    db.commit()

    # Handle term extension documents - update staff term_end and reactivate if needed
    is_extension = doc_type == DocumentType.TERM_EXTENSION.value or "term_extension" in doc_type
    if is_extension:
        from backend.services.staff_service import StaffService
        StaffService(db, changed_by="DIRECT_SCAN_UPLOAD").process_term_extension(document)

    # 3. Add to attendance if it's a vacation type
    is_vacation = doc_type in ["vacation_paid", "vacation_unpaid", "vacation_main", "vacation_additional",
                           "vacation_study", "vacation_children", "vacation_unpaid_study",
                           "vacation_unpaid_mandatory", "vacation_unpaid_agreement", "vacation_unpaid_other"]

    if is_vacation:
        try:
            # Determine code based on doc_type
            code = "В" # Paid vacation default
            if "unpaid" in doc_type:
                code = "НА"
            elif "term_extension" in doc_type:
                code = None 

            if code:
                # Iterate dates and create attendance
                current_date = dt_start
                while current_date <= dt_end:
                    AttendanceService.create_attendance(
                        db,
                        staff_id=staff_id,
                        date=current_date,
                        code=code,
                        hours=0 # Vacation is 0 hours
                    )
                    current_date += timedelta(days=1)
                    
        except Exception as e:
            # Log error but don't fail the upload
            print(f"Error auto-creating attendance: {e}")

    db.commit()
    
    return {"message": "Документ створено та скан завантажено", "document_id": document.id}


@router.post("/preview", response_model=PreviewResponse)
async def preview_document(
    doc_data: DocumentCreate,
    db: DBSession,
    current_user: TokenData = Depends(require_employee),
):
    """
    Generate HTML preview for a document without saving it.
    """
    from backend.models.staff import Staff
    from backend.services.document_renderer import render_document_html

    staff = db.query(Staff).filter(Staff.id == doc_data.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    # Calculate days count if provided dates are valid
    days_count = 0
    if doc_data.date_start and doc_data.date_end:
        delta = doc_data.date_end - doc_data.date_start
        days_count = delta.days + 1

    html = render_document_html(
        doc_type=doc_data.doc_type,
        staff_name=staff.pib_nom,
        staff_position=staff.position,
        date_start=doc_data.date_start,
        date_end=doc_data.date_end,
        days_count=days_count,
        payment_period=doc_data.payment_period,
        custom_text=doc_data.custom_text,
        db_session=db,
        staff_id=staff.id,
        employment_type=staff.employment_type.value if hasattr(staff.employment_type, 'value') else staff.employment_type
    )

    return PreviewResponse(html=html)


@router.get("/staff/{staff_id}/blocked-days")
async def get_blocked_days(
    staff_id: int,
    db: DBSession,
    current_user: TokenData = Depends(require_employee),
):
    """
    Отримати заблоковані дні (відпустки та відвідування) для співробітника.
    Повертає масив дат, які вже зайняті:
    - Документами у станах on_signature, signed, processed
    - Записами відвідування з кодами відпусток (з ATTENDANCE_CODES)
    """
    # Get documents with confirmed statuses
    confirmed_statuses = [
        DocumentStatus.ON_SIGNATURE,
        DocumentStatus.SIGNED,
        DocumentStatus.PROCESSED
    ]

    documents = db.query(Document).filter(
        Document.staff_id == staff_id,
        Document.status.in_(confirmed_statuses)
    ).all()

    blocked_dates = []
    seen_dates = set()  # To avoid duplicates

    # Add document dates
    for doc in documents:
        if doc.date_start and doc.date_end:
            current_date = doc.date_start
            while current_date <= doc.date_end:
                date_key = current_date.isoformat()
                if date_key not in seen_dates:
                    seen_dates.add(date_key)
                    blocked_dates.append({
                        "date": date_key,
                        "doc_id": doc.id,
                        "doc_type": doc.doc_type.value if doc.doc_type else None,
                        "doc_type_name": doc.doc_type.name.replace("_", " ").title() if doc.doc_type else None,
                        "source": "document",
                    })
                current_date += timedelta(days=1)

    # Add attendance records with vacation codes (single date or range)
    attendance_records = db.query(Attendance).filter(
        Attendance.staff_id == staff_id,
        Attendance.code.in_(list(ATTENDANCE_CODES.keys()))
    ).all()

    for att in attendance_records:
        if att.date:
            start_date = att.date
            end_date = att.date_end if att.date_end else att.date

            current_date = start_date
            while current_date <= end_date:
                date_key = current_date.isoformat()
                if date_key not in seen_dates:
                    seen_dates.add(date_key)
                    blocked_dates.append({
                        "date": date_key,
                        "doc_id": att.id,
                        "doc_type": f"attendance_{att.code}",
                        "doc_type_name": f"Відмітка: {att.code}",
                        "source": "attendance",
                    })
                current_date += timedelta(days=1)

    return {
        "staff_id": staff_id,
        "blocked_dates": blocked_dates,
        "total_blocked_days": len(blocked_dates)
    }
