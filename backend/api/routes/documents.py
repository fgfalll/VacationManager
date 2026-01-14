"""API маршрути для управління документами."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    DBSession,
    DocumentSvc,
    GrammarSvc,
    ValidationSvc,
)
from backend.models.document import Document
from backend.schemas.document import (
    DocumentCreate,
    DocumentGenerateResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusUpdate,
    DocumentUpdate,
)
from backend.services.validation_service import ValidationService
from shared.enums import DocumentStatus, DocumentType
from shared.exceptions import ValidationError as CustomValidationError

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    staff_id: int | None = Query(None, description="Фільтр за ID співробітника"),
    status: DocumentStatus | None = Query(None, description="Фільтр за статусом"),
    doc_type: DocumentType | None = Query(None, description="Фільтр за типом документа"),
):
    """Отримати список документів."""
    query = db.query(Document)

    if staff_id is not None:
        query = query.filter(Document.staff_id == staff_id)
    if status is not None:
        query = query.filter(Document.status == status)
    if doc_type is not None:
        query = query.filter(Document.doc_type == doc_type)

    total = query.count()
    items = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

    # Додаємо дані співробітників
    result_items = []
    for doc in items:
        doc_dict = DocumentResponse.model_validate(doc).model_dump()
        doc_dict["staff_name"] = doc.staff.pib_nom
        doc_dict["staff_position"] = doc.staff.position
        doc_dict["progress"] = doc.get_workflow_progress()
        result_items.append(DocumentResponse(**doc_dict))

    return DocumentListResponse(
        items=result_items,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: DBSession,
):
    """Отримати документ за ID."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    response = DocumentResponse.model_validate(doc)
    response.staff_name = doc.staff.pib_nom
    response.staff_position = doc.staff.position
    response.progress = doc.get_workflow_progress()

    return response


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    doc_data: DocumentCreate,
    db: DBSession,
    validation: ValidationSvc,
):
    """Створити новий документ."""
    # Отримуємо співробітника
    from backend.models.staff import Staff

    staff = db.query(Staff).filter(Staff.id == doc_data.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")

    # Валідація дат
    try:
        validation.validate_vacation_dates(
            doc_data.date_start,
            doc_data.date_end,
            staff,
            db,
        )
    except CustomValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Обчислюємо кількість днів
    from backend.services.validation_service import ValidationService as VS
    days_count = VS.calculate_working_days(doc_data.date_start, doc_data.date_end)

    # Створюємо документ
    document = Document(
        **doc_data.model_dump(exclude={"custom_text"}),
        days_count=days_count,
        status=DocumentStatus.DRAFT,
    )
    if doc_data.custom_text:
        document.custom_text = doc_data.custom_text

    db.add(document)
    db.commit()
    db.refresh(document)

    response = DocumentResponse.model_validate(document)
    response.staff_name = document.staff.pib_nom
    response.staff_position = document.staff.position

    return response


@router.post("/{document_id}/generate", response_model=DocumentGenerateResponse)
async def generate_document(
    document_id: int,
    db: DBSession,
    doc_service: DocumentSvc,
):
    """Згенерувати PDF файл з документа."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    if doc.status != DocumentStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Документ має статус '{doc.status.value}', очікується 'draft'",
        )

    try:
        file_path = doc_service.generate_document(doc)
        return DocumentGenerateResponse(
            success=True,
            file_path=str(file_path),
            message="Документ успішно згенеровано",
            document_id=document_id,
        )
    except Exception as e:
        return DocumentGenerateResponse(
            success=False,
            message=f"Помилка генерації: {str(e)}",
            document_id=document_id,
        )


@router.put("/{document_id}/status", response_model=DocumentResponse)
async def update_document_status(
    document_id: int,
    status_update: DocumentStatusUpdate,
    db: DBSession,
    doc_service: DocumentSvc,
):
    """Оновити статус документа."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    # Rollback до Draft
    if status_update.status == DocumentStatus.DRAFT:
        try:
            doc_service.rollback_to_draft(doc)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        doc.status = status_update.status
        db.commit()

    db.refresh(doc)
    response = DocumentResponse.model_validate(doc)
    response.staff_name = doc.staff.pib_nom
    response.staff_position = doc.staff.position

    return response


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: DBSession,
):
    """Видалити документ."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    # Видаляємо файли якщо є
    if doc.file_docx_path:
        from pathlib import Path

        Path(doc.file_docx_path).unlink(missing_ok=True)
    if doc.file_scan_path:
        from pathlib import Path

        Path(doc.file_scan_path).unlink(missing_ok=True)

    db.delete(doc)
    db.commit()

    return None


@router.get("/pending", response_model=DocumentListResponse)
async def get_pending_documents(
    db: DBSession,
):
    """Отримати список документів, що очікують підпису."""
    query = db.query(Document).filter(Document.status == DocumentStatus.ON_SIGNATURE)
    items = query.order_by(Document.created_at.asc()).all()

    result_items = []
    for doc in items:
        doc_dict = DocumentResponse.model_validate(doc).model_dump()
        doc_dict["staff_name"] = doc.staff.pib_nom
        doc_dict["staff_position"] = doc.staff.position
        result_items.append(DocumentResponse(**doc_dict))

    return DocumentListResponse(
        items=result_items,
        total=len(items),
        page=1,
        page_size=len(items),
    )


@router.get("/{document_id}/progress")
async def get_document_progress(
    document_id: int,
    db: DBSession,
):
    """Отримати прогрес підписання документа."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    return {
        "document_id": document_id,
        "status": doc.status.value,
        "progress": doc.get_workflow_progress(),
    }


@router.post("/{document_id}/workflow/{step}")
async def update_workflow_step(
    document_id: int,
    step: str,
    comment: str | None = None,
    action: str = "complete",
    db: DBSession,
    doc_service: DocumentSvc = None,
):
    """
    Оновити етап підписання документа.

    Args:
        document_id: ID документа
        step: Етап (applicant, approval, department_head, approval_order, rector, scanned, tabel)
        action: Дія (complete - позначити виконаним, clear - очистити)
        comment: Коментар до етапу
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    valid_steps = [
        "applicant", "approval", "department_head",
        "approval_order", "rector", "scanned", "tabel"
    ]
    if step not in valid_steps:
        raise HTTPException(
            status_code=400,
            detail=f"Невідомий етап. Доступні: {', '.join(valid_steps)}"
        )

    try:
        if action == "complete":
            if step == "applicant":
                doc_service.set_applicant_signed(doc, comment)
            elif step == "approval":
                doc_service.set_approval(doc, comment)
            elif step == "department_head":
                doc_service.set_department_head_signed(doc, comment)
            elif step == "approval_order":
                doc_service.set_approval_order(doc, comment)
            elif step == "rector":
                doc_service.set_rector_signed(doc, comment)
            elif step == "scanned":
                doc_service.set_scanned(doc, comment)
            elif step == "tabel":
                doc_service.set_tabel_added(doc, comment)
        elif action == "clear":
            doc_service.clear_workflow_step(doc, step)
        else:
            raise HTTPException(status_code=400, detail="Невідома дія")

        return {
            "success": True,
            "message": f"Етап '{step}' оновлено",
            "progress": doc.get_workflow_progress(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-documents", response_model=DocumentListResponse)
async def get_my_documents(
    staff_id: int,
    db: DBSession,
):
    """Отримати документи співробітника для відображення в web portal."""
    query = db.query(Document).filter(Document.staff_id == staff_id)
    items = query.order_by(Document.created_at.desc()).all()

    result_items = []
    for doc in items:
        doc_dict = DocumentResponse.model_validate(doc).model_dump()
        doc_dict["staff_name"] = doc.staff.pib_nom
        doc_dict["staff_position"] = doc.staff.position
        doc_dict["progress"] = doc.get_workflow_progress()
        result_items.append(DocumentResponse(**doc_dict))

    return DocumentListResponse(
        items=result_items,
        total=len(items),
        page=1,
        page_size=len(items),
    )
