"""API маршрути для завантаження сканів документів."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from backend.api.dependencies import DBSession
from backend.core.config import get_settings
from backend.core.websocket import manager
from backend.models.document import Document
from backend.services.staff_service import StaffService
from backend.schemas.responses import UploadResponse
from shared.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from shared.enums import DocumentStatus, DocumentType

router = APIRouter(prefix="/upload", tags=["upload"])
settings = get_settings()


@router.post("/{document_id}", response_model=UploadResponse)
async def upload_scan(
    document_id: int,
    file: Annotated[UploadFile, File(...)],
    db: DBSession,
):
    """
    Завантажити скан підписаного документа.

    Валідація:
    - Максимальний розмір: 10MB
    - Дозволені формати: PDF, JPG, JPEG, PNG
    - Документ має бути в статусі 'signed_rector'

    Для документів прийому на роботу:
    - Після завантаження скану створюється новий запис співробітника
    - Документу призначається staff_id
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


def _generate_scan_path(document: Document, extension: str) -> Path:
    """Генерує шлях для збереження скану."""
    year = document.date_start.year
    month = document.date_start.strftime("%m_%B").lower()

    surname = document.staff.pib_nom.split()[0] if document.staff.pib_nom.split() else "unknown"
    filename = f"{surname}_{document.id}_signed{extension}"

    return settings.storage_dir / str(year) / month / "signed" / filename
