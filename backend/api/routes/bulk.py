"""API маршрути для масових операцій з документами."""

from fastapi import APIRouter, Depends, HTTPException
from backend.api.dependencies import DBSession, GrammarSvc
from backend.core.dependencies import require_department_head
from backend.schemas.document import BulkValidationRequest, BulkGenerateRequest
from backend.services.bulk_document_service import BulkDocumentService

router = APIRouter(prefix="/bulk", tags=["bulk"])


@router.post("/validate")
async def validate_bulk_generation(
    request: BulkValidationRequest,
    db: DBSession,
    grammar: GrammarSvc,
    current_user=Depends(require_department_head),
):
    """
    Перевірити можливість масового створення документів для списку співробітників.
    Повертає списки staff, для яких можна і не можна створити документи.
    """
    from backend.models.staff import Staff

    # Fetch staff objects
    staff_list = db.query(Staff).filter(Staff.id.in_(request.staff_ids)).all()
    
    if not staff_list:
        raise HTTPException(status_code=404, detail="Співробітників не знайдено")

    service = BulkDocumentService(db, grammar)
    
    result = service.validate_staff_for_batch(
        staff_list=staff_list,
        date_start=request.date_start,
        date_end=request.date_end
    )
    
    # Transform result for frontend response (Staff objects to simplified dicts)
    valid_staff = [
        {
            "id": s.id,
            "pib_nom": s.pib_nom,
            "position": s.position
        } for s in result['valid']
    ]
    
    invalid_staff = [
        {
            "id": item['staff'].id,
            "pib_nom": item['staff'].pib_nom,
            "reasons": item['reasons']
        } for item in result['invalid']
    ]

    return {
        "valid": valid_staff,
        "invalid": invalid_staff,
        "total_requested": len(staff_list),
        "valid_count": len(valid_staff),
        "invalid_count": len(invalid_staff)
    }


@router.post("/generate")
async def generate_bulk_documents(
    request: BulkGenerateRequest,
    db: DBSession,
    grammar: GrammarSvc,
    current_user=Depends(require_department_head),
):
    """
    Масове створення документів.
    """
    from backend.models.staff import Staff

    staff_list = db.query(Staff).filter(Staff.id.in_(request.staff_ids)).all()
    
    if not staff_list:
        raise HTTPException(status_code=404, detail="Співробітників не знайдено")

    service = BulkDocumentService(db, grammar)
    
    # Filter only valid staff again just in case
    validation_result = service.validate_staff_for_batch(
        staff_list=staff_list,
        date_start=request.date_start,
        date_end=request.date_end
    )
    
    valid_staff_list = validation_result['valid']
    
    if not valid_staff_list:
        raise HTTPException(status_code=400, detail="Немає валідних співробітників для генерації")

    # Generate documents
    documents = service.generate_batch(
        staff_list=valid_staff_list,
        doc_type=request.doc_type,
        date_start=request.date_start,
        date_end=request.date_end,
        file_suffix=request.file_suffix
    )
    
    return {
        "success": True,
        "generated_count": len(documents),
        "message": f"Успішно створено {len(documents)} документів",
        "document_ids": [d.id for d in documents]
    }
