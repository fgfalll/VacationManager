"""Сервіс для моніторингу застарілих документів.

Відстежує документи, статус яких не змінювався більше 1 дня,
та управляє сповіщеннями про застарілі документи.
"""

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from backend.models.document import Document
from shared.enums import DocumentStatus


class StaleDocumentService:
    """Сервіс для роботи з застарілими документами."""

    STALE_THRESHOLD_DAYS = 1  # Days before marking as stale
    MAX_NOTIFICATIONS = 3     # Notifications before requiring action

    # Statuses that should be monitored (exclude terminal states)
    MONITORED_STATUSES = [
        DocumentStatus.DRAFT,
        DocumentStatus.SIGNED_BY_APPLICANT,
        DocumentStatus.APPROVED_BY_DISPATCHER,
        DocumentStatus.SIGNED_DEP_HEAD,
        DocumentStatus.AGREED,
        DocumentStatus.SIGNED_RECTOR,
        DocumentStatus.SCANNED,
    ]

    @classmethod
    def is_document_stale(cls, doc: Document) -> bool:
        """
        Check if a single document is stale.
        
        A document is stale if:
        - It's not in a terminal status (PROCESSED)
        - status_changed_at is older than STALE_THRESHOLD_DAYS
        - No explanation has been provided
        """
        if doc.status == DocumentStatus.PROCESSED:
            return False

        if doc.stale_explanation:
            return False

        if not doc.status_changed_at:
            # Use updated_at as fallback
            check_time = doc.updated_at or doc.created_at
        else:
            check_time = doc.status_changed_at

        if not check_time:
            return False

        threshold = datetime.now() - timedelta(days=cls.STALE_THRESHOLD_DAYS)
        return check_time < threshold

    @classmethod
    def get_stale_documents(cls, db: Session) -> list[Document]:
        """
        Get all documents that are currently stale.
        
        Returns documents where status hasn't changed for STALE_THRESHOLD_DAYS
        and are not in terminal status.
        """
        threshold = datetime.now() - timedelta(days=cls.STALE_THRESHOLD_DAYS)

        # Query documents in monitored statuses
        query = db.query(Document).filter(
            Document.status.in_(cls.MONITORED_STATUSES),
            Document.stale_explanation.is_(None),  # No explanation yet
        )

        # Filter by status_changed_at or updated_at
        stale_docs = []
        for doc in query.all():
            check_time = doc.status_changed_at or doc.updated_at or doc.created_at
            if check_time and check_time < threshold:
                stale_docs.append(doc)

        return stale_docs

    @classmethod
    def get_documents_requiring_action(cls, db: Session) -> list[Document]:
        """
        Get documents that have accumulated MAX_NOTIFICATIONS or more.
        These require user action (explanation or removal).
        """
        return db.query(Document).filter(
            Document.status.in_(cls.MONITORED_STATUSES),
            Document.stale_notification_count >= cls.MAX_NOTIFICATIONS,
            Document.stale_explanation.is_(None),
        ).all()

    @classmethod
    def check_and_notify_stale_documents(cls, db: Session) -> dict:
        """
        Check for stale documents and increment their notification count.
        
        Returns summary of notifications sent.
        """
        stale_docs = cls.get_stale_documents(db)
        notified = []
        requires_action = []

        for doc in stale_docs:
            doc.stale_notification_count += 1

            if doc.stale_notification_count >= cls.MAX_NOTIFICATIONS:
                requires_action.append({
                    "id": doc.id,
                    "staff_id": doc.staff_id,
                    "doc_type": doc.doc_type.value if doc.doc_type else None,
                    "status": doc.status.value if doc.status else None,
                    "notification_count": doc.stale_notification_count,
                })
            else:
                notified.append({
                    "id": doc.id,
                    "staff_id": doc.staff_id,
                    "doc_type": doc.doc_type.value if doc.doc_type else None,
                    "status": doc.status.value if doc.status else None,
                    "notification_count": doc.stale_notification_count,
                })

        db.commit()

        return {
            "checked_at": datetime.now().isoformat(),
            "total_stale": len(stale_docs),
            "notified": notified,
            "requires_action": requires_action,
        }

    @classmethod
    def resolve_stale_document(
        cls,
        db: Session,
        document_id: int,
        action: Literal["explain", "remove"],
        explanation: str | None = None,
    ) -> dict:
        """
        Resolve a stale document by providing explanation or removing it.
        
        Args:
            db: Database session
            document_id: ID of the document
            action: "explain" to provide explanation, "remove" to delete
            explanation: Required if action is "explain"
            
        Returns:
            Result dict with success status and message
        """
        doc = db.query(Document).filter(Document.id == document_id).first()
        
        if not doc:
            return {
                "success": False,
                "message": "Документ не знайдено",
                "document_id": document_id,
            }

        if action == "explain":
            if not explanation or not explanation.strip():
                return {
                    "success": False,
                    "message": "Пояснення є обов'язковим",
                    "document_id": document_id,
                }
            
            doc.stale_explanation = explanation.strip()
            doc.stale_notification_count = 0  # Reset counter
            db.commit()
            
            return {
                "success": True,
                "message": "Пояснення збережено",
                "document_id": document_id,
            }

        elif action == "remove":
            # Check if document can be deleted
            if doc.is_blocked:
                return {
                    "success": False,
                    "message": f"Документ заблоковано: {doc.blocked_reason}",
                    "document_id": document_id,
                }
            
            if doc.status == DocumentStatus.PROCESSED:
                return {
                    "success": False,
                    "message": "Неможливо видалити оброблений документ",
                    "document_id": document_id,
                }

            db.delete(doc)
            db.commit()
            
            return {
                "success": True,
                "message": "Документ видалено",
                "document_id": document_id,
            }

        return {
            "success": False,
            "message": f"Невідома дія: {action}",
            "document_id": document_id,
        }

    @classmethod
    def get_stale_document_info(cls, doc: Document) -> dict:
        """
        Get detailed info about a stale document for API response.
        """
        check_time = doc.status_changed_at or doc.updated_at or doc.created_at
        days_stale = 0
        if check_time:
            days_stale = (datetime.now() - check_time).days

        staff = doc.staff
        return {
            "id": doc.id,
            "staff_id": doc.staff_id,
            "staff_name": staff.pib_nom if staff else "",
            "doc_type": doc.doc_type.value if doc.doc_type else None,
            "doc_type_name": doc.doc_type.name.replace("_", " ").title() if doc.doc_type else None,
            "status": doc.status.value if doc.status else None,
            "days_stale": days_stale,
            "notification_count": doc.stale_notification_count,
            "stale_explanation": doc.stale_explanation,
            "status_changed_at": doc.status_changed_at.isoformat() if doc.status_changed_at else None,
        }
