"""Bulk Document Generation Service."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.models.document import Document
from backend.models.settings import Approvers
from backend.services.grammar_service import GrammarService
from backend.services.document_service import DocumentService
from shared.enums import DocumentType, DocumentStatus


settings = get_settings()

# Ukrainian month names
UKRAINIAN_MONTHS = {
    1: "січень", 2: "лютий", 3: "березень", 4: "квітень",
    5: "травень", 6: "червень", 7: "липень", 8: "серпень",
    9: "вересень", 10: "жовтень", 11: "листопад", 12: "грудень"
}


def _format_surname_initials(pib_nom: str) -> str:
    """Форматує ПІБ як Прізвище І.Б."""
    parts = pib_nom.split()
    if len(parts) >= 3:
        surname = parts[0]
        first_name = parts[1][0] if len(parts[1]) > 0 else ""
        patronymic = parts[2][0] if len(parts[2]) > 0 else ""
        return f"{surname} {first_name}.{patronymic}."
    elif len(parts) == 2:
        surname = parts[0]
        first_name = parts[1][0] if len(parts[1]) > 0 else ""
        return f"{surname} {first_name}."
    elif len(parts) == 1:
        return parts[0]
    return pib_nom


def _get_ukrainian_month(d: date) -> str:
    """Повертає українську назву місяця."""
    return UKRAINIAN_MONTHS.get(d.month, "")


class BulkDocumentService:
    """
    Сервіс для масової генерації документів відпусток.

    Дозволяє генерувати документи для групи співробітників
    з однаковими налаштуваннями.
    """

    def __init__(self, db: Session, grammar: GrammarService):
        """
        Ініціалізує сервіс.

        Args:
            db: Сесія бази даних
            grammar: Сервіс морфології
        """
        self.db = db
        self.grammar = grammar
        self.storage_dir = settings.storage_dir
        self.doc_service = DocumentService(db, grammar)

    def generate_batch(
        self,
        staff_list: list,
        doc_type: str,
        date_start: date,
        date_end: date,
        signatories: list[dict] | None = None,
        file_suffix: str = ""
    ) -> list[Document]:
        """
        Генерує документи для списку співробітників.

        Args:
            staff_list: Список об'єктів Staff
            doc_type: Тип документа (vacation_paid, vacation_unpaid)
            date_start: Початок періоду
            date_end: Кінець періоду
            signatories: Список погоджувачів (опціонально)
            file_suffix: Суфікс для імені файлу

        Returns:
            Список створених документів
        """
        documents = []
        days_count = (date_end - date_start).days + 1

        for staff in staff_list:
            try:
                doc = self._create_document(
                    staff=staff,
                    doc_type=doc_type,
                    date_start=date_start,
                    date_end=date_end,
                    days_count=days_count,
                    signatories=signatories,
                    file_suffix=file_suffix
                )
                documents.append(doc)
            except Exception as e:
                print(f"Error creating document for {staff.pib_nom}: {e}")

        return documents

    def _create_document(
        self,
        staff,
        doc_type: str,
        date_start: date,
        date_end: date,
        days_count: int,
        signatories: list[dict] | None,
        file_suffix: str = ""
    ) -> Document:
        """
        Створює один документ для співробітника.
        """
        # Determine payment period
        if date_start.day <= 15:
            payment_period = "перша половина"
        else:
            payment_period = "друга половина"

        # Create document
        doc = Document(
            staff_id=staff.id,
            doc_type=doc_type,
            date_start=date_start,
            date_end=date_end,
            days_count=days_count,
            payment_period=payment_period,
            editor_content="",  # Will be filled by WYSIWYG
            status=DocumentStatus.DRAFT,
            created_by="bulk"
        )

        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        # Generate output path
        output_path = self._get_output_path(doc, staff, file_suffix)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Update document with file path
        doc.file_docx_path = str(output_path)
        # Status stays as DRAFT - will change to SIGNED_BY_APPLICANT when applicant signs
        self.db.commit()

        return doc

    def _get_output_path(self, doc: Document, staff, file_suffix: str = "") -> Path:
        """
        Генерує шлях для збереження файлу.

        Формат: storage/{year}/{month}/{status}/{initials} {type} {suffix} {days} днів.pdf
        """
        year = doc.date_start.year
        month_ua = _get_ukrainian_month(doc.date_start)
        # Use document's actual status for folder
        UKRAINIAN_STATUS = {
            DocumentStatus.DRAFT: "чернетки",
            DocumentStatus.SIGNED_BY_APPLICANT: "підписано_заявником",
            DocumentStatus.APPROVED_BY_DISPATCHER: "погоджено_диспетчером",
            DocumentStatus.SIGNED_DEP_HEAD: "підписано_зав_кафедри",
            DocumentStatus.AGREED: "погоджено",
            DocumentStatus.SIGNED_RECTOR: "підписано_ректором",
            DocumentStatus.SCANNED: "відскановано",
            DocumentStatus.PROCESSED: "оброблені",
        }
        status_folder = UKRAINIAN_STATUS.get(doc.status, "чернетки")

        # Format initials
        initials = _format_surname_initials(staff.pib_nom)

        # Document type label
        if doc_type_value := doc.doc_type.value:
            if doc_type_value == "vacation_paid":
                doc_label = "відпустка"
            elif doc_type_value == "vacation_unpaid":
                doc_label = "відпустка_без_зарплати"
            else:
                doc_label = doc_type_value
        else:
            doc_label = "відпустка"

        # Build filename
        if file_suffix:
            filename = f"{initials} {doc_label} {file_suffix} {doc.days_count} днів.pdf"
        else:
            filename = f"{initials} {doc_label} {month_ua} {doc.days_count} днів.pdf"

        return self.storage_dir / str(year) / month_ua / status_folder / filename

    def validate_staff_for_batch(
        self,
        staff_list: list,
        date_start: date,
        date_end: date
    ) -> dict[str, list]:
        """
        Перевіряє список співробітників на можливість створення документів.

        Returns:
            dict з ключами 'valid' (список staff), 'invalid' (список з причинами)
        """
        valid = []
        invalid = []

        for staff in staff_list:
            reasons = []

            # Check balance for paid vacation
            doc_type = "vacation_paid"  # Default for bulk
            if doc_type == "vacation_paid":
                if staff.vacation_balance < (date_end - date_start).days + 1:
                    reasons.append(f"Недостатньо балансу: {staff.vacation_balance} днів")

            # Check contract end
            if date_end > staff.term_end:
                reasons.append(f"Дата закінчення ({date_end}) пізніше закінчення контракту ({staff.term_end})")

            # Check for overlapping documents
            for doc in staff.documents:
                if doc.status in ('draft', 'signed_by_applicant', 'approved_by_dispatcher', 'signed_dep_head', 'agreed', 'signed_rector'):
                    # Check overlap
                    if not (date_end < doc.date_start or date_start > doc.date_end):
                        reasons.append(f"Перетин з існуючим документом #{doc.id}")

            if reasons:
                invalid.append({
                    'staff': staff,
                    'reasons': reasons
                })
            else:
                valid.append(staff)

        return {'valid': valid, 'invalid': invalid}

    def get_available_dates(
        self,
        staff,
        days_needed: int = 14,
        max_days_ahead: int = 90
    ) -> list[tuple[date, date]]:
        """
        Знаходить доступні періоди для співробітника.

        Returns:
            Список кортежів (date_start, date_end) з доступними періодами
        """
        today = date.today()
        contract_end = staff.term_end
        max_date = min(today + timedelta(days=max_days_ahead), contract_end - timedelta(days=days_needed))

        # Get locked dates from existing documents
        locked = set()
        for doc in staff.documents:
            if doc.status in ('signed_by_applicant', 'approved_by_dispatcher', 'signed_dep_head', 'agreed', 'signed_rector', 'scanned', 'processed'):
                current = doc.date_start
                while current <= doc.date_end:
                    locked.add(current)
                    current += timedelta(days=1)

        available_periods = []
        current = today

        while current <= max_date:
            # Check if period is available
            all_available = True
            for offset in range(days_needed):
                check_date = current + timedelta(days=offset)

                if check_date > contract_end:
                    all_available = False
                    break

                # Skip weekends
                if check_date.weekday() >= 5:
                    continue

                if check_date in locked:
                    all_available = False
                    break

            if all_available:
                period_end = current + timedelta(days=days_needed - 1)
                available_periods.append((current, period_end))
                current = period_end + timedelta(days=1)
            else:
                current += timedelta(days=1)

        return available_periods
