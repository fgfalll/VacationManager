"""Integration tests for stale document monitoring feature."""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from backend.models.document import Document
from backend.services.stale_document_service import StaleDocumentService
from shared.enums import DocumentStatus, DocumentType


@pytest.mark.asyncio
async def test_document_becomes_stale_after_threshold(db_session, sample_staff):
    """
    Test that a document is marked as stale after STALE_THRESHOLD_DAYS.
    """
    # Create a document with status_changed_at in the past
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.DRAFT,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
    )
    doc.status_changed_at = datetime.now() - timedelta(days=2)  # 2 days ago
    db_session.add(doc)
    db_session.commit()

    # Document should be stale
    assert StaleDocumentService.is_document_stale(doc) is True


@pytest.mark.asyncio
async def test_document_not_stale_when_recent(db_session, sample_staff):
    """
    Test that a recently created/updated document is NOT stale.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.DRAFT,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
    )
    doc.status_changed_at = datetime.now()  # Just now
    db_session.add(doc)
    db_session.commit()

    # Document should not be stale
    assert StaleDocumentService.is_document_stale(doc) is False


@pytest.mark.asyncio
async def test_processed_document_not_stale(db_session, sample_staff):
    """
    Test that PROCESSED documents are never marked as stale.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.PROCESSED,
        date_start=date.today() - timedelta(days=20),
        date_end=date.today() - timedelta(days=15),
        days_count=6,
    )
    doc.status_changed_at = datetime.now() - timedelta(days=30)  # Long ago
    db_session.add(doc)
    db_session.commit()

    # Processed documents are never stale
    assert StaleDocumentService.is_document_stale(doc) is False


@pytest.mark.asyncio  
async def test_notification_count_increments(db_session, sample_staff):
    """
    Test that check_and_notify increments stale_notification_count.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.DRAFT,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
        stale_notification_count=0,
    )
    doc.status_changed_at = datetime.now() - timedelta(days=2)
    db_session.add(doc)
    db_session.commit()

    # Run stale check
    result = StaleDocumentService.check_and_notify_stale_documents(db_session)
    
    # Refresh and verify count increased
    db_session.refresh(doc)
    assert doc.stale_notification_count == 1
    assert result["total_stale"] == 1


@pytest.mark.asyncio
async def test_document_requires_action_after_max_notifications(db_session, sample_staff):
    """
    Test that document requires action after MAX_NOTIFICATIONS.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.SIGNED_BY_APPLICANT,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
        stale_notification_count=StaleDocumentService.MAX_NOTIFICATIONS,  # Already at max
    )
    doc.status_changed_at = datetime.now() - timedelta(days=2)
    db_session.add(doc)
    db_session.commit()

    # Get documents requiring action
    requires_action = StaleDocumentService.get_documents_requiring_action(db_session)
    
    assert len(requires_action) == 1
    assert requires_action[0].id == doc.id


@pytest.mark.asyncio
async def test_resolve_with_explanation(db_session, sample_staff):
    """
    Test resolving a stale document with an explanation.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.DRAFT,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
        stale_notification_count=3,
    )
    db_session.add(doc)
    db_session.commit()

    # Resolve with explanation
    result = StaleDocumentService.resolve_stale_document(
        db=db_session,
        document_id=doc.id,
        action="explain",
        explanation="Чекаю на підпис директора"
    )

    assert result["success"] is True
    
    db_session.refresh(doc)
    assert doc.stale_explanation == "Чекаю на підпис директора"
    assert doc.stale_notification_count == 0  # Reset after explanation


@pytest.mark.asyncio
async def test_resolve_with_removal(db_session, sample_staff):
    """
    Test resolving a stale document by removing it.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.DRAFT,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    # Remove document
    result = StaleDocumentService.resolve_stale_document(
        db=db_session,
        document_id=doc_id,
        action="remove",
    )

    assert result["success"] is True
    
    # Verify document is deleted
    deleted = db_session.query(Document).filter(Document.id == doc_id).first()
    assert deleted is None


@pytest.mark.asyncio
async def test_cannot_remove_blocked_document(db_session, sample_staff):
    """
    Test that blocked documents cannot be removed.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.SIGNED_RECTOR,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
        is_blocked=True,
        blocked_reason="Документ відскановано",
    )
    db_session.add(doc)
    db_session.commit()

    # Try to remove
    result = StaleDocumentService.resolve_stale_document(
        db=db_session,
        document_id=doc.id,
        action="remove",
    )

    assert result["success"] is False
    assert "заблоковано" in result["message"]


@pytest.mark.asyncio
async def test_document_with_explanation_not_stale(db_session, sample_staff):
    """
    Test that a document with explanation is not considered stale.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.DRAFT,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
        stale_explanation="Чекаю на документи",
    )
    doc.status_changed_at = datetime.now() - timedelta(days=10)  # Very old
    db_session.add(doc)
    db_session.commit()

    # Should not be stale because explanation exists
    assert StaleDocumentService.is_document_stale(doc) is False


@pytest.mark.asyncio
async def test_status_change_resets_stale_tracking(db_session, sample_staff):
    """
    Test that changing status resets stale tracking fields.
    """
    doc = Document(
        staff_id=sample_staff.id,
        doc_type=DocumentType.VACATION_PAID,
        status=DocumentStatus.DRAFT,
        date_start=date.today() + timedelta(days=10),
        date_end=date.today() + timedelta(days=15),
        days_count=6,
        stale_notification_count=3,
        stale_explanation="Old explanation",
    )
    doc.status_changed_at = datetime.now() - timedelta(days=5)
    db_session.add(doc)
    db_session.commit()

    # Simulate a workflow step completion
    doc.applicant_signed_at = datetime.now()
    doc.update_status_from_workflow()
    db_session.commit()

    # Status should have changed and tracking reset
    db_session.refresh(doc)
    assert doc.status == DocumentStatus.SIGNED_BY_APPLICANT
    assert doc.stale_notification_count == 0
    assert doc.stale_explanation is None
    assert doc.status_changed_at is not None
