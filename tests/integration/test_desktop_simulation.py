
import pytest
from datetime import date
from backend.models.document import Document
from backend.services.document_service import DocumentService
from backend.services.staff_service import StaffService
from shared.enums import DocumentType, DocumentStatus
from backend.core.database import get_db_context

@pytest.mark.asyncio
async def test_desktop_scan_upload_triggers_new_employee_creation(db_session, tmp_path):
    """
    Test that calling DocumentService.set_scanned (simulate Desktop App)
    triggers new employee creation.
    """
    # 1. Create a document with new_employee_data (simulate Desktop App creation via DB)
    new_employee_data = {
        "pib_nom": "Desktop User",
        "position": "lecturer",
        "rate": 1.0,
        "employment_type": "main",
        "work_basis": "contract",
        "term_start": "01.01.2024",
        "term_end": "31.12.2024",
        "vacation_balance": 10
    }
    
    doc = Document(
        staff_id=999, # Temporary ID, usually specialist/head
        doc_type=DocumentType.EMPLOYMENT_CONTRACT,
        date_start=date(2024, 1, 1),
        date_end=date(2024, 12, 31),
        days_count=0,
        status=DocumentStatus.SIGNED_BY_APPLICANT,
        new_employee_data=new_employee_data
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    
    # 2. Simulate scan upload via DocumentService (Desktop App path)
    # Create a dummy scan file
    scan_file = tmp_path / "scan.pdf"
    scan_file.write_text("dummy scan content")
    
    grammar = None # Mock or None if not needed for set_scanned
    service = DocumentService(db_session, grammar)
    
    # 3. Call set_scanned
    service.set_scanned(doc, file_path=str(scan_file), comment="Desktop Scan")
    
    # 4. Verify side effects
    db_session.refresh(doc)
    
    
    # Check if staff was created
    from backend.models.staff import Staff
    # We don't know the exact new ID, but it should be different from 999
    new_staff_id = doc.staff_id
    assert new_staff_id != 999
    
    new_staff = db_session.get(Staff, new_staff_id)
    assert new_staff is not None
    assert new_staff.pib_nom == "Desktop User"
    assert new_staff.is_active == True
    
    # Staff creation should verify
    assert doc.status == DocumentStatus.PROCESSED
    assert doc.new_employee_data is None # Should be cleared

@pytest.mark.asyncio
async def test_desktop_scan_upload_triggers_term_extension(db_session, sample_staff):
    """
    Test that calling DocumentService.set_scanned triggers term extension logic.
    """
    # 1. Setup staff with old term end
    sample_staff.term_end = date(2023, 12, 31)
    sample_staff.is_active = False # Simulate inactive
    db_session.commit()
    
    # 2. Create term extension document
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.TERM_EXTENSION,
        date_start=date(2024, 1, 1), # Start of new term
        date_end=date(2024, 12, 31), # End of new term
        days_count=0,
        status=DocumentStatus.SIGNED_RECTOR
    )
    db_session.add(doc)
    db_session.commit()
    
    # 3. Simulate Desktop App scan upload
    service = DocumentService(db_session, None)
    service.set_scanned(doc, file_path=None, comment="Extension Scan")
    
    # 4. Verify side effects
    db_session.refresh(sample_staff)
    assert sample_staff.term_end == date(2024, 12, 31)
    assert sample_staff.is_active == True
