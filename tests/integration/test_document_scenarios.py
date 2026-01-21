
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.document import Document
from backend.models.staff import Staff
from shared.enums import DocumentStatus, DocumentType
from backend.api.routes.upload import upload_scan

# Mocking UploadFile
class MockUploadFile:
    def __init__(self, filename, content=b"test pdf content"):
        self.filename = filename
        self.content = content
        self.file = MagicMock()
        self.content_type = "application/pdf"
        self.size = len(content)

    async def read(self):
        return self.content

@pytest.mark.asyncio
async def test_term_extension_flow(db_session, sample_staff):
    """
    Scenario 1: Term extension document generated -> signed, scanned -> extended contract term for employee generated.
    """
    # 1. Setup: Employee with expiring contract
    sample_staff.term_end = date.today()
    db_session.commit()
    
    # 2. Create Term Extension Document
    new_term_end = date.today() + timedelta(days=365)
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.TERM_EXTENSION, # or specific type
        status=DocumentStatus.SIGNED_RECTOR, # Ready for scan upload
        date_start=date.today(),
        date_end=new_term_end, # This should be the new term end
        days_count=365,
        payment_period="N/A",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    
    # 3. Simulate Reactivation/Extension via Scan Upload
    # We call the route handler directly to simulate the request
    file = MockUploadFile("extension.pdf")
    
    
    from unittest.mock import patch
    with patch("backend.api.routes.upload.manager") as mock_manager:
        mock_manager.notify_document_signed = AsyncMock()
        mock_manager.notify_document_status_changed = AsyncMock()
        
        await upload_scan(
            document_id=doc.id,
            file=file,
            db=db_session
        )
        
    db_session.refresh(sample_staff)
    
    # 4. Assertions
    # The term_end should be updated to doc.date_end
    assert sample_staff.term_end == new_term_end, "Staff term_end was not updated after term extension scan upload"


@pytest.mark.asyncio
async def test_reactivation_flow(db_session, sample_staff):
    """
    Scenario 3: Reactivation on document generation -> signed, pdf uploaded -> successfully activated employee
    """
    # 1. Setup: Inactive Employee
    sample_staff.is_active = False
    db_session.commit()
    
    # 2. Create Document (e.g., Employment or Term Extension)
    # Using Term Extension as valid Reactivation reason here
    new_term_end = date.today() + timedelta(days=365)
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.TERM_EXTENSION,
        status=DocumentStatus.SIGNED_RECTOR,
        date_start=date.today(),
        date_end=new_term_end,
        days_count=365
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    
    # 3. Simulate Scan Upload
    file = MockUploadFile("reactivation.pdf")
    
    from unittest.mock import patch
    with patch("backend.api.routes.upload.manager") as mock_manager:
        mock_manager.notify_document_signed = AsyncMock()
        mock_manager.notify_document_status_changed = AsyncMock()
        
        await upload_scan(
            document_id=doc.id,
            file=file,
            db=db_session
        )
        
    db_session.refresh(sample_staff)
    
    # 4. Assertions
    assert sample_staff.is_active == True, "Staff was not reactivated after scan upload"
    assert sample_staff.term_end == new_term_end, "Staff term_end was not updated during reactivation"


@pytest.mark.asyncio
async def test_direct_scan_reactivation_flow(db_session, sample_staff):
    """
    Scenario 2: Reactivation through pdf upload -> successfully activated employee
    (Using direct_scan_upload endpoint logic)
    """
    # 1. Setup: Inactive Employee
    sample_staff.is_active = False
    db_session.commit()
    
    new_term_end = date.today() + timedelta(days=365)
    
    # 2. Simulate Direct Scan Upload
    # direct_scan_upload(db, staff_id, doc_type, date_start, date_end, days_count, file, current_user)
    
    file = MockUploadFile("direct_reactivation.pdf")
    
    from backend.api.routes.documents import direct_scan_upload
    from backend.schemas.auth import TokenData
    
    # Mock current_user
    current_user = TokenData(username="test_user", user_id=1, role="admin")
    
    # We need to ensure that direct_scan_upload triggers the logic.
    # Currently it DOES NOT call _handle_term_extension. So we expect this to fail initially (TDD).
    
    with patch("backend.api.routes.documents.shutil"), \
         patch("backend.api.routes.documents.open"), \
         patch("backend.api.routes.documents.render_document", return_value="<html></html>"):
         
        await direct_scan_upload(
            db=db_session,
            staff_id=sample_staff.id,
            doc_type=DocumentType.TERM_EXTENSION.value,
            date_start=date.today().strftime("%Y-%m-%d"),
            date_end=new_term_end.strftime("%Y-%m-%d"),
            days_count=365,
            file=file,
            current_user=current_user
        )
        
    db_session.refresh(sample_staff)
    
    # 4. Assertions
    assert sample_staff.is_active == True, "Staff was not reactivated after direct scan upload"
    assert sample_staff.term_end == new_term_end, "Staff term_end was not updated during direct reactivation"


@pytest.mark.asyncio
async def test_new_employee_flow(db_session):
    """
    Scenario 4: New employee from document creation -> signed and scanned -> employee created -> document assigned
    """
    # 1. Setup: Employment Document with new_employee_data
    # No existing staff_id initially, but the model requires staff_id.
    # In the current implementation (checked upload.py), the doc seems to be linked to a dummy staff or similar?
    # Wait, `doc.staff_id` is foreign key and nullable=False in `Document` model.
    # Let's check `Document` model again.
    # `staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False)`
    # This means for "New Employee" flow, we probably use a placeholder staff or the system creates a temp staff?
    # Or maybe the document is created with a temporary connection?
    # Actually, usually for "New Employee", we might use a special system user/staff or validation is relaxed?
    # Let's look at `upload.py` logic: `_create_staff_from_employment_document` is called.
    # But `Document` creation requires `staff_id`.
    # Let's assume for this test we attach it to an existing "Technical" staff or similiar, or we create a dummy one.
    # Or maybe there is a "candidate" table? No.
    # Let's look at how the app handles it. Maybe there is a specific 'VacationManager' system staff?
    # For the test, I will create a dummy staff to attach the document to, as if it was created by an admin.

    # Create a dummy admin/creator staff
    admin_staff = Staff(
         pib_nom="Admin", rate=1.0, position="Admin",
         term_start=date.today(), term_end=date.today(),
         employment_type="main", work_basis="contract"
    )
    db_session.add(admin_staff)
    db_session.commit()

    new_employee_data = {
        "pib_nom": "New User Created",
        "rate": 1.0,
        "position": "Assistant",
        "employment_type": "main",
        "work_basis": "contract",
        "term_start": date.today().strftime("%d.%m.%Y"),
        "term_end": (date.today() + timedelta(days=365)).strftime("%d.%m.%Y"),
        "email": "new@example.com",
        "phone": "1234567890"
    }

    doc = Document(
        staff_id=admin_staff.id, # Linked to creator initially? Or self?
        # Actually logic in upload.py: `doc.staff_id = new_staff.id` at line 99.
        # So it RE-assigns the staff_id.
        doc_type=DocumentType.EMPLOYMENT_CONTRACT, # assuming this type exists or similar
        status=DocumentStatus.SIGNED_RECTOR,
        date_start=date.today(),
        date_end=date.today() + timedelta(days=365),
        days_count=365,
        new_employee_data=new_employee_data
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Simulate Scan Upload
    file = MockUploadFile("hiring.pdf")

    from unittest.mock import patch
    with patch("backend.api.routes.upload.manager") as mock_manager:
        mock_manager.notify_document_signed = AsyncMock()
        mock_manager.notify_document_status_changed = AsyncMock()

        await upload_scan(
            document_id=doc.id,
            file=file,
            db=db_session
        )

    db_session.refresh(doc)

    # 3. Assertions
    assert doc.staff_id != admin_staff.id, "Document staff_id should be updated to the new employee"

    new_staff = db_session.query(Staff).get(doc.staff_id)
    assert new_staff is not None
    assert new_staff.pib_nom == "New User Created"
    assert new_staff.is_active == True


@pytest.mark.asyncio
async def test_add_subposition_flow(db_session, sample_staff):
    """
    Scenario 5: Add subposition (сумісництво) to existing employee via employment document.
    An employee with a main position gets an additional internal/external position with reduced rate.
    """
    # 1. Setup: Existing employee with main position (rate = 1.0)
    assert sample_staff.employment_type == "main", "Sample staff should have main employment type"
    assert sample_staff.rate == 1.0, "Sample staff should have rate 1.0 for main position"
    original_position = sample_staff.position

    # 2. Create Employment Document for Subposition (Internal)
    # Using the same PIB but different employment_type, position, and rate < 1.0
    new_term_end = date.today() + timedelta(days=365)
    subposition_data = {
        "pib_nom": sample_staff.pib_nom,  # Same person
        "rate": 0.5,  # Reduced rate for subposition
        "position": "LECTURER",  # Different position for subposition
        "employment_type": "internal",  # Internal subposition
        "work_basis": "contract",
        "term_start": date.today().strftime("%d.%m.%Y"),
        "term_end": new_term_end.strftime("%d.%m.%Y"),
        "email": "sub@example.com",
        "phone": "9876543210"
    }

    doc = Document(
        staff_id=sample_staff.id,  # Initially linked to existing staff
        doc_type=DocumentType.EMPLOYMENT_CONTRACT,
        status=DocumentStatus.SIGNED_RECTOR,
        date_start=date.today(),
        date_end=new_term_end,
        days_count=365,
        new_employee_data=subposition_data
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    # 3. Simulate Scan Upload
    file = MockUploadFile("subposition.pdf")

    from unittest.mock import patch
    with patch("backend.api.routes.upload.manager") as mock_manager:
        mock_manager.notify_document_signed = AsyncMock()
        mock_manager.notify_document_status_changed = AsyncMock()

        await upload_scan(
            document_id=doc.id,
            file=file,
            db=db_session
        )

    db_session.refresh(doc)

    # 4. Assertions
    # Document should now be linked to the new subposition staff record
    assert doc.staff_id != sample_staff.id, "Document staff_id should be updated to the new subposition staff"

    # Original staff record should remain unchanged
    db_session.refresh(sample_staff)
    assert sample_staff.employment_type == "main", "Original staff employment_type should remain 'main'"
    assert sample_staff.rate == 1.0, "Original staff rate should remain 1.0"
    assert sample_staff.position == original_position, "Original staff position should remain unchanged"

    # New staff record should be created for subposition
    subposition_staff = db_session.query(Staff).get(doc.staff_id)
    assert subposition_staff is not None, "New subposition staff record should be created"
    assert subposition_staff.pib_nom == sample_staff.pib_nom, "Subposition should have same PIB as original"
    assert subposition_staff.employment_type == "internal", "Subposition should have 'internal' employment type"
    assert float(subposition_staff.rate) == 0.5, "Subposition should have rate 0.5"
    assert subposition_staff.position == "LECTURER", "Subposition should have new position"
    assert subposition_staff.is_active == True, "Subposition should be active"

    # Verify both records exist for the same person
    all_staff_records = db_session.query(Staff).filter(Staff.pib_nom == sample_staff.pib_nom).all()
    assert len(all_staff_records) == 2, "Should have 2 staff records for the same person (main + subposition)"

