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
    StaleResolutionRequest,
    DocumentStatusUpdate,
)
from backend.schemas.auth import TokenData
from backend.services.document_renderer import render_document
from shared.enums import DocumentStatus, DocumentType, get_document_type_label
from backend.core.config import get_settings
from backend.core.websocket import manager
from backend.services.staff_service import StaffService
from backend.schemas.responses import UploadResponse
from shared.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from pathlib import Path
from typing import Annotated

settings = get_settings()

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/types")
async def get_document_types():
    """
    Отримати список доступних типів документів.

    Повертає перелік всіх типів документів, які підтримує система,
    разом з їх назвами та ідентифікаторами.

    Returns:
    - Список об'єктів з id, name, description.
    """
    return [
        {
            "id": dt.value,
            "name": get_document_type_label(dt.value),
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
    status: str | None = Query(None, description="Фільтр за статусом (draft, on_signature, agreed, signed, scanned, processed)"),
    doc_type: DocumentType | None = Query(None),
    search: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    needs_scan: bool = Query(False),
    filter: str | None = Query(None, description="Фільтр: 'stale' для документів з проблемами"),
    exclude_statuses: str | None = Query(None, description="Статуси для виключення (через кому)"),
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати список документів з розширеною фільтрацією.

    Це основний ендпоінт для відображення реєстру документів.
    Підтримує пошук, фільтрацію за датами, статусами, співробітниками та типами.

    Parameters:
    - **skip** (int): Пагінація - пропустити N записів.
    - **limit** (int): Пагінація - кількість записів на сторінці.
    - **staff_id** (int, optional): Фільтр по конкретному співробітнику.
    - **status** (str, optional): Точний збіг статусу (наприклад, 'draft').
    - **doc_type** (str, optional): Тип документа.
    - **search** (str, optional): Пошук по тексту документа або коментарям.
    - **start_date/end_date** (str, optional): Діапазон дат створення (YYYY-MM-DD).
    - **needs_scan** (bool): Спеціальний фільтр - документи, що потребують сканування (підписані, але без файлу).
    - **filter** (str, optional): Пресети фільтрів ('pending', 'stale', 'not_confirmed').
    
    Returns:
    - **data**: Список документів з деталями (співробітник, дати, статус).
    - **total**: Загальна кількість знайдених документів.
    """
    query = db.query(Document)

    if needs_scan:
        # Filter documents that are signed_rector or processed but don't have a scan yet
        query = query.filter(
            Document.status.in_([DocumentStatus.SIGNED_RECTOR, DocumentStatus.PROCESSED]),
            Document.file_scan_path.is_(None)
        )
    elif filter == 'not_confirmed':
        # Filter documents that are signed_rector but don't have a scan yet
        query = query.filter(
            Document.status == DocumentStatus.SIGNED_RECTOR,
            Document.file_scan_path.is_(None)
        )
    elif filter == 'pending':
        # Filter for all pending documents (in workflow but not processed)
        pending_statuses = [
            DocumentStatus.SIGNED_BY_APPLICANT,
            DocumentStatus.APPROVED_BY_DISPATCHER,
            DocumentStatus.SIGNED_DEP_HEAD,
            DocumentStatus.AGREED,
            DocumentStatus.SIGNED_RECTOR,
            DocumentStatus.SCANNED,
        ]
        query = query.filter(Document.status.in_(pending_statuses))
    elif filter == 'stale':
        # Filter for stale documents (not processed, not updated for STALE_THRESHOLD_DAYS+)
        from backend.services.stale_document_service import StaleDocumentService
        stale_threshold = datetime.now() - timedelta(days=StaleDocumentService.STALE_THRESHOLD_DAYS)
        query = query.filter(
            Document.status != DocumentStatus.PROCESSED,
            Document.updated_at <= stale_threshold
        )
    else:
        # Normal filters
        if staff_id is not None:
            query = query.filter(Document.staff_id == staff_id)
        if status is not None:
            # Convert string status to enum
            try:
                query = query.filter(Document.status == DocumentStatus(status))
            except ValueError:
                pass  # Invalid status, skip filter
        if doc_type is not None:
            query = query.filter(Document.doc_type == doc_type)
        # Exclude specific statuses
        if exclude_statuses:
            excluded = []
            for s in exclude_statuses.split(','):
                s = s.strip()
                try:
                    excluded.append(DocumentStatus(s))
                except ValueError:
                    pass
            if excluded:
                query = query.filter(~Document.status.in_(excluded))

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

    total = int(query.count())
    items = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

    # Return simplified response using correct field names
    result_items = []
    for doc in items:
        staff = doc.staff
        # Generate title from doc_type
        doc_title = get_document_type_label(doc.doc_type.value) if doc.doc_type else "Документ"

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
                "name": get_document_type_label(doc.doc_type.value) if doc.doc_type else "",
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


@router.get("/stale")
async def get_stale_documents(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати список проблемних ("застарілих") документів.

    Повертає документи, рух яких зупинився (статус не змінювався довгий час).
    Використовується для моніторингу "завислих" процесів.

    Returns:
    - Список застарілих документів з інформацією про причину (stale_info).
    """
    from backend.services.stale_document_service import StaleDocumentService

    stale_docs = StaleDocumentService.get_stale_documents(db)

    # Convert to response format
    result_items = []
    for doc in stale_docs:
        staff = doc.staff
        doc_title = get_document_type_label(doc.doc_type.value) if doc.doc_type else "Документ"

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
                "name": get_document_type_label(doc.doc_type.value) if doc.doc_type else "",
            },
            "title": doc_title,
            "status": doc.status.value if doc.status else "draft",
            "date_start": doc.date_start.isoformat() if doc.date_start else None,
            "date_end": doc.date_end.isoformat() if doc.date_end else None,
            "days_count": doc.days_count,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "staff_name": staff.pib_nom if staff else "",
            "staff_position": staff.position if staff else "",
            "stale_info": StaleDocumentService.get_stale_document_info(doc),
        })

    total = len(result_items)
    items = result_items[skip:skip + limit]

    return {
        "data": items,
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
    }


@router.post("/{document_id}/stale/resolve")
async def resolve_stale_document_endpoint(
    document_id: int,
    request: StaleResolutionRequest,
    db: DBSession,
    current_user: TokenData = Depends(require_employee),
):
    """
    Вирішити проблему застарілого документа.

    Дозволяє користувачу "відреагувати" на попередження про застарілий документ:
    - Нагадати (подовжити термін очікування).
    - Видалити документ.
    - Інша дія.

    Parameters:
    - **document_id** (int): ID документа.
    - **request** (StaleResolutionRequest): Дія та пояснення.

    Errors:
    - **400 Bad Request**: Невірна дія або помилка виконання.
    """
    from backend.services.stale_document_service import StaleDocumentService

    result = StaleDocumentService.resolve_stale_document(
        db=db,
        document_id=document_id,
        action=request.action,
        explanation=request.explanation,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.patch("/{document_id}")
async def update_document_status(
    document_id: int,
    status_update: DocumentStatusUpdate,
    db: DBSession,
    current_user: TokenData = Depends(require_employee),
):
    """
    Оновити статус документа (підписати/погодити).

    Використовується для ручної зміни статусу або підписання.
    В залежності від статусу викликає відповідний метод сервісу.

    Parameters:
    - **document_id**: ID документа.
    - **status_update**: Новий статус.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    if doc.is_blocked and status_update.status != DocumentStatus.PROCESSED:
         # Allow processing blocked documents but prevent other edits
         # Actually, signatures should be allowed?
         # Check specific block reason if needed. For now, trust the service.
         pass

    # Map status to service method
    # Note: We create a temporary service instance
    service = DocumentSvc(db, GrammarSvc())

    try:
        if status_update.status == DocumentStatus.SIGNED_BY_APPLICANT:
            service.set_applicant_signed(doc)
        elif status_update.status == DocumentStatus.APPROVED_BY_DISPATCHER:
            service.set_approval(doc)
        elif status_update.status == DocumentStatus.SIGNED_DEP_HEAD:
            service.set_department_head_signed(doc)
        elif status_update.status == DocumentStatus.AGREED:
            service.set_approval_order(doc)
        elif status_update.status == DocumentStatus.SIGNED_RECTOR:
            service.set_rector_signed(doc)
        elif status_update.status == DocumentStatus.PROCESSED:
            service.process_document(doc)
        else:
            # Fallback for just updating status field (not recommended for workflow)
            # Maybe for DRAFT?
            if status_update.status == DocumentStatus.DRAFT:
                service.rollback_to_draft(doc)
            else:
                doc.status = status_update.status
                db.commit()

        # Re-fetch to return full object
        db.refresh(doc)
        # Re-render html to update status text in doc if needed
        doc.rendered_html = render_document(doc, db)
        db.commit()

        response = DocumentResponse.model_validate(doc)
        # Populate extra fields
        response.title = get_document_type_label(doc.doc_type.value) if doc.doc_type else "Документ"
        response.document_type = {
            "id": doc.doc_type.value,
            "name": get_document_type_label(doc.doc_type.value) if doc.doc_type else "Документ"
        }
        return response

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{document_id}/forward")
async def forward_document(
    document_id: int,
    db: DBSession,
    current_user: TokenData = Depends(require_employee),
):
    """
    Передати документ далі по маршруту (Погодити).

    Використовується для етапів погодження (Диспетчер, Узгодження).
    Визначає наступний крок на основі поточного статусу.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    service = DocumentSvc(db, GrammarSvc())

    try:
        current_status = doc.status

        if current_status == DocumentStatus.SIGNED_BY_APPLICANT:
            # Dispatcher approval
            service.set_approval(doc)
        elif current_status == DocumentStatus.SIGNED_DEP_HEAD:
            # Coordination/Agreed
            service.set_approval_order(doc)
        elif current_status in (DocumentStatus.APPROVED_BY_DISPATCHER, DocumentStatus.AGREED):
             # Document is already in the target state (idempotency for double-clicks)
             # APPROVED_BY_DISPATCHER comes from SIGNED_BY_APPLICANT (forward)
             # AGREED comes from SIGNED_DEP_HEAD (forward)
             pass
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Невідома дія 'forward' для статусу {current_status.value}"
            )

        db.refresh(doc)
        response = DocumentResponse.model_validate(doc)
        response.title = get_document_type_label(doc.doc_type.value) if doc.doc_type else "Документ"
        response.document_type = {
            "id": doc.doc_type.value,
            "name": get_document_type_label(doc.doc_type.value) if doc.doc_type else "Документ"
        }
        return response

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: DBSession,
    current_user: TokenData = Depends(require_employee),
):
    """
    Видалити документ.

    Дозволяє видалити документ (наприклад, чернетку або помилково створений).
    Вже підписані/оброблені документи видаляти не можна (окрім адмінів, але тут спрощена логіка).
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    if doc.is_blocked:
        raise HTTPException(status_code=400, detail=doc.blocked_reason or "Документ заблоковано")

    # Prevent deleting processed documents
    if doc.status == DocumentStatus.PROCESSED:
         raise HTTPException(status_code=400, detail="Не можна видаляти оброблені документи")

    # If document has file, clean it up?
    # For now just delete record. Service might handle file cleanup but we keep it simple.
    
    db.delete(doc)
    db.commit()


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: DBSession,
    current_user: get_current_user = Depends(require_employee),
):
    """
    Отримати повну інформацію про документ.

    Повертає всі дані документа, включаючи згенерований HTML контент,
    посилання на файли (.docx, скани), історію статусів та дані підписантів.
    Якщо документ заархівовано, намагається відновити контекст з архіву.

    Parameters:
    - **document_id** (int): ID документа.

    Returns:
    - Детальна структура документа.

    Errors:
    - **404 Not Found**: Документ не знайдено.
    """
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
    doc_title = get_document_type_label(doc.doc_type.value) if doc.doc_type else "Документ"
    
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
    Отримати контекст документа для відображення (Snapshot).

    Повертає "зліпок" даних на момент архівування (якщо є), або актуальні дані.
    Використовується для коректного відображення історичних документів,
    навіть якщо дані співробітника змінилися з того часу.

    Returns:
    - Структура з HTML, даними співробітника, підписантів та налаштувань.
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
    """
    Створити нову заяву (документ).

    Основний метод створення документів.
    1. Перевіряє валідність дат та перетинів з іншими відпустками/документами.
    2. Створює запис в БД.
    3. Генерує HTML-контент документа на основі шаблону.
    4. Привласнює початковий статус (DRAFT).

    Parameters:
    - **doc_data** (DocumentCreate): Дані для створення (тип, дати, staff_id).

    Returns:
    - Створений документ (DocumentResponse).

    Errors:
    - **400 Bad Request**: Перетин дат або логічні помилки (дата закінчення раніше початку).
    - **404 Not Found**: Співробітника не знайдено.
    """
    from backend.models.staff import Staff

    staff = db.query(Staff).filter(Staff.id == doc_data.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    # Check for date overlaps with existing documents
    confirmed_statuses = [
        DocumentStatus.SIGNED_BY_APPLICANT,
        DocumentStatus.APPROVED_BY_DISPATCHER,
        DocumentStatus.SIGNED_DEP_HEAD,
        DocumentStatus.AGREED,
        DocumentStatus.SIGNED_RECTOR,
        DocumentStatus.SCANNED,
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
                    "doc_type": get_document_type_label(existing_doc.doc_type.value) if existing_doc.doc_type else "Документ",
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
    response.title = get_document_type_label(document.doc_type.value) if document.doc_type else "Документ"
    response.document_type = {
        "id": document.doc_type.value,
        "name": get_document_type_label(document.doc_type.value) if document.doc_type else "Документ"
    }
    response.start_date = document.date_start
    response.end_date = document.date_end

    return response


def _generate_scan_path(document: Document, extension: str) -> Path:
    """Генерує шлях для збереження скану."""
    year = document.date_start.year
    month = document.date_start.strftime("%m_%B").lower()

    surname = document.staff.pib_nom.split()[0] if document.staff.pib_nom.split() else "unknown"
    filename = f"{surname}_{document.id}_signed{extension}"

    return settings.storage_dir / str(year) / month / "signed" / filename


@router.post("/{document_id}/upload", response_model=UploadResponse)
async def upload_scan(
    document_id: int,
    file: Annotated[UploadFile, File(...)],
    db: DBSession,
):
    """
    Завантажити скан-копію документа (Upload Scan).

    Основний ендпоінт для завантаження підписаних скан-копій.
    Файл зберігається на сервері, шлях прописується в БД.
    Статус документа змінюється на SCANNED.

    Parameters:
    - **document_id**: ID документа.
    - **file**: Файл (PDF/Image, max 10MB).
    """
    # Отримуємо документ
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    if doc.status != DocumentStatus.SIGNED_RECTOR:
        raise HTTPException(
            status_code=400,
            detail=f"Документ має статус '{doc.status.value}', очікується 'signed_rector'",
        )

    # Валідація файлу
    if not file.filename:
        raise HTTPException(status_code=400, detail="Не вказано ім'я файлу")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимий формат файлу. Дозволені: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Читаємо файл
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Файл завеликий. Максимум: {MAX_FILE_SIZE / 1024 / 1024:.1f} MB",
        )

    # Зберігаємо файл
    try:
        save_path = _generate_scan_path(doc, file_ext)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "wb") as f:
            f.write(contents)

        # Оновлюємо документ
        old_status = doc.status.value
        doc.file_scan_path = str(save_path)
        doc.is_blocked = True
        doc.blocked_reason = "Документ має завантажений скан. Редагування заблоковано."

        # Create archive snapshot with staff/approver data
        from backend.services.document_service import save_document_archive
        try:
            archive_path = save_document_archive(doc, db)
            doc.archive_metadata_path = str(archive_path)
        except Exception as e:
            # Log but don't fail - archive is optional
            import logging
            logging.warning(f"Failed to create document archive: {e}")

        # Handle employment documents - create new staff record
        is_employment = doc.doc_type.value.startswith("employment_")
        if is_employment and doc.new_employee_data:
            service = StaffService(db, changed_by="UPLOAD_SCAN")
            new_staff = service.create_staff_from_document(doc)
            
            if new_staff:
                import logging
                logging.info(f"Created new staff record {new_staff.id} for employment document {doc.id}")
            else:
                # Failed to create staff, but still mark as scanned
                doc.status = DocumentStatus.SCANNED
        else:
            doc.status = DocumentStatus.SCANNED

        # Handle term extension documents - update staff term_end and reactivate if needed
        is_extension = doc.doc_type.value.startswith("term_extension") or doc.doc_type == DocumentType.TERM_EXTENSION
        if is_extension:
            StaffService(db, changed_by="UPLOAD_SCAN").process_term_extension(doc)

        from datetime import datetime
        doc.signed_at = datetime.now()
        db.commit()

        # WebSocket повідомлення про завантаження скану
        await manager.notify_document_signed(document_id, str(save_path))
        await manager.notify_document_status_changed(document_id, doc.status.value, old_status)

        return UploadResponse(
            success=True,
            file_path=str(save_path),
            message="Скан успішно завантажено",
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка збереження файлу: {str(e)}")




@router.post("/direct-scan-upload")
async def direct_scan_upload(
    db: DBSession,
    staff_id: int = Query(...),
    doc_type: str = Query(...),
    date_start: str = Query(...),
    date_end: str = Query(...),
    days_count: int = Query(...),
    file: UploadFile = File(...),
    # Optional subposition fields for employment documents
    new_position: str | None = Query(None, description="Position for new subposition"),
    new_rate: float | None = Query(None, description="Rate for new subposition (0.25, 0.5, 0.75)"),
    new_employment_type: str | None = Query(None, description="Employment type (internal, external)"),
    current_user: TokenData = Depends(require_employee),
):
    """
    Пряме завантаження скану (створення архівного документа).

    Створює документ одразу зі статусом SCANNED на основі завантаженого файлу.
    Використовується для внесення історичних даних або документів, створених поза системою.

    **Особливості для прийому на роботу (employment docs):**
    Якщо передані параметри `new_position`, `new_rate`, система може автоматично створити
    нову картку співробітника (сумісництво) і прив'язати документ до неї.

    Parameters:
    - **staff_id**: ID співробітника.
    - **doc_type**: Тип документа.
    - **date_start/end**: Дати дії.
    - **file**: Скан-копія.
    - **new_position/rate/employment_type**: Опціональні параметри для створення сумісництва.
    """
    from backend.services.attendance_service import AttendanceService
    from backend.models.staff import Staff
    from decimal import Decimal

    # Parse dates
    try:
        dt_start = datetime.strptime(date_start, "%Y-%m-%d").date()
        dt_end = datetime.strptime(date_end, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Невірний формат дати (YYYY-MM-DD)")

    target_staff_id = staff_id
    
    # For employment documents with subposition data, create a new staff record
    is_employment = doc_type.startswith("employment_")
    if is_employment and new_position and new_rate and new_employment_type:
        # Get original staff to copy name and other data
        original_staff = db.query(Staff).filter(Staff.id == staff_id).first()
        if not original_staff:
            raise HTTPException(status_code=404, detail="Співробітника не знайдено")
        
        # Create new staff record for subposition
        new_staff = Staff(
            pib_nom=original_staff.pib_nom,
            pib_dav=original_staff.pib_dav,
            degree=original_staff.degree,
            position=new_position.upper(),
            rate=Decimal(str(new_rate)),
            employment_type=new_employment_type,
            work_basis="contract",
            term_start=dt_start,
            term_end=dt_end,
            is_active=True,
            vacation_balance=0,
            department=original_staff.department or "",
            work_schedule=original_staff.work_schedule,
        )
        db.add(new_staff)
        db.commit()
        db.refresh(new_staff)
        target_staff_id = new_staff.id

    # 1. Create document entry
    document = Document(
        staff_id=target_staff_id,
        doc_type=DocumentType(doc_type),
        date_start=dt_start,
        date_end=dt_end,
        days_count=days_count,
        payment_period="Скан завантажено вручну",
        status=DocumentStatus.SCANNED,  # Scanned document
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
    Попередній перегляд HTML документа.

    Генерує візуальне представлення документа без збереження в БД.
    Дозволяє користувачу перевірити правильність даних перед створенням.

    Returns:
    - HTML рядок (PreviewResponse).
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
    Отримати зайняті (заблоковані) дні для календаря.
    
    Повертає список дат, які не можна обирати для нових відпусток, оскільки
    вони вже зайняті іншими затвердженими документами або записами в табелі.

    Parameters:
    - **staff_id** (int): ID співробітника.

    Returns:
    - **blocked_dates**: Список об'єктів {date, reason, type}.
    """
    # Get documents with confirmed statuses
    confirmed_statuses = [
        DocumentStatus.SIGNED_BY_APPLICANT,
        DocumentStatus.APPROVED_BY_DISPATCHER,
        DocumentStatus.SIGNED_DEP_HEAD,
        DocumentStatus.AGREED,
        DocumentStatus.SIGNED_RECTOR,
        DocumentStatus.SCANNED,
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
                        "doc_type_name": get_document_type_label(doc.doc_type.value) if doc.doc_type else None,
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
