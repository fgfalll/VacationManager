"""Сервіс генерації PDF документів з WYSIWYG редактора."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from backend.core.config import get_settings
from backend.models.document import Document
from backend.models.settings import Approvers, SystemSettings
from backend.services.grammar_service import GrammarService
from shared.enums import DocumentStatus, DocumentType
from shared.exceptions import DocumentGenerationError


settings = get_settings()

# WeasyPrint executable path
WEASYPRINT_EXE = Path(__file__).parent.parent.parent / 'weasyprint' / 'dist' / 'weasyprint.exe'

# Ukrainian month names
UKRAINIAN_MONTHS = {
    1: "січень", 2: "лютий", 3: "березень", 4: "квітень",
    5: "травень", 6: "червень", 7: "липень", 8: "серпень",
    9: "вересень", 10: "жовтень", 11: "листопад", 12: "грудень"
}

# Ukrainian status names
UKRAINIAN_STATUS = {
    DocumentStatus.DRAFT: "чернетки",
    DocumentStatus.ON_SIGNATURE: "на_підписі",
    DocumentStatus.SIGNED: "підписані",
    DocumentStatus.PROCESSED: "оброблені",
}


def _get_ukrainian_month(date_start, date_end) -> str:
    """Повертає українську назву місяця або діапазон."""
    start_month = UKRAINIAN_MONTHS.get(date_start.month, "")
    end_month = UKRAINIAN_MONTHS.get(date_end.month, "")

    if date_start.month == date_end.month:
        return start_month
    else:
        return f"{start_month}-{end_month}"


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


class DocumentService:
    """
    Сервіс для генерації PDF документів з WYSIWYG редактора.

    Конвертує HTML контент з редактора у PDF формат.

    Example:
        >>> service = DocumentService(db, grammar_service)
        >>> path = service.generate_document(document)
        >>> print(path)
        Path("storage/2025/01_january/on_signature/dmytrenko_42.pdf")
    """

    def __init__(self, db, grammar: GrammarService):
        """
        Ініціалізує сервіс.

        Args:
            db: Сесія бази даних
            grammar: Сервіс морфології
        """
        self.db = db
        self.grammar = grammar
        self.storage_dir = settings.storage_dir

    def generate_document(self, document: Document, raw_html: str | None = None) -> Path:
        """
        Генерує PDF файл з WYSIWYG контенту.

        Args:
            document: Об'єкт документа
            raw_html: Готовий HTML для PDF (якщо передано, використовується напряму)

        Returns:
            Path до створеного файлу

        Raises:
            DocumentGenerationError: Якщо не вдалося згенерувати документ
        """
        try:
            if not raw_html and not document.editor_content:
                raise DocumentGenerationError(
                    "Відсутній контент. Спочатку створіть документ у редакторі."
                )

            output_path = self._get_output_path(document)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            self._generate_pdf(document, output_path, raw_html)

            document.file_docx_path = str(output_path)
            document.status = DocumentStatus.ON_SIGNATURE
            self.db.commit()

            return output_path

        except Exception as e:
            self.db.rollback()
            raise DocumentGenerationError(f"Помилка генерації документа: {e}") from e

    def _generate_pdf(self, document: Document, output_path: Path, raw_html: str | None = None):
        """Генерує PDF з WYSIWYG контенту."""
        if raw_html:
            html_content = self._wrap_html_for_pdf(raw_html)
        else:
            editor_data = json.loads(document.editor_content)
            blocks = editor_data.get('blocks', {})
            html_content = self._build_fallback_html(blocks)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            html_path = f.name

        try:
            if not os.path.exists(WEASYPRINT_EXE):
                raise DocumentGenerationError(f"WeasyPrint not found at: {WEASYPRINT_EXE}")

            result = subprocess.run(
                [WEASYPRINT_EXE, html_path, str(output_path)],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                raise DocumentGenerationError(f"WeasyPrint failed: {result.stderr or 'Unknown error'}")

            print(f"PDF generated: {output_path}")

        finally:
            debug_html_path = Path(output_path).parent / f"{Path(output_path).stem}_debug.html"
            if os.path.exists(html_path):
                shutil.copy(html_path, debug_html_path)
                print(f"DEBUG: HTML saved to {debug_html_path}")
                with open(debug_html_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Find the content part after the style
                    import re
                    match = re.search(r'<div class="document">(.*?)</div>', content, re.DOTALL)
                    if match:
                        print(f"DEBUG: Document content: {match.group(1)[:1500]}")
                    else:
                        print(f"DEBUG: HTML preview: {content[:2000]}")
                os.remove(html_path)

    def _wrap_html_for_pdf(self, content_html: str) -> str:
        """Обгортає готовий HTML контент у повний документ з CSS для друку."""
        css = """
        <style type="text/css">
            @page { size: A4; margin: 2cm 1.5cm 2cm 3cm; }
            body { font-family: "Times New Roman", Times, serif; font-size: 14pt; line-height: 1.5; margin: 0; padding: 0; }
            .document { width: 100%; }
            .document > div { margin-left: 0 !important; text-align: left !important; }
            .document > div[data-block="header"] { margin-left: 50% !important; }
            .document > div[data-block="header"] p { margin: 0 !important; }
            .document > div[data-block="header"] > div { margin: 0 !important; padding: 0 !important; }
            .document > div[data-block="title"] { text-align: center !important; margin: 15px 0 !important; }
            .document > div[data-block="content"] { text-align: justify !important; }
            .document > div[data-block="content"] p { margin: 0; text-indent: 1.27cm; }
            .document > div[data-block="applicant_signature"] { margin-top: 25px !important; }
            .document > div[data-block="applicant_signature"] > div { display: flex; justify-content: space-between; }
            .document > div[data-block="applicant_signature"] > div > div { flex: 1; }
            .document > div[data-block="applicant_signature"] > div > div:nth-child(2) { text-align: center; padding: 0 10px; }
            .document > div[data-block="applicant_signature"] > div > div:nth-child(2) span { border-bottom: 1px solid black; display: inline-block; width: 100%; }
            .document > div[data-block="approvals"] { margin-top: 40px !important; }
            .document > div[data-block="approvals"] > p { font-weight: bold; margin: 15px 0 !important; }
            .document > div[data-block="approvals"] .signatory-row { display: flex; justify-content: space-between; align-items: flex-start; margin-top: 15px !important; width: 100%; }
            #signatories-list { width: 100% !important; }
            .document > div[data-block="approvals"] .signatory-row > div { flex: 1; min-width: 0; }
            .document > div[data-block="approvals"] .signatory-row > div:nth-child(1) { text-align: left; }
            .document > div[data-block="approvals"] .signatory-row > div:nth-child(2) { text-align: center; padding: 0 10px; flex: 0 0 auto; margin-top: 0; }
            .document > div[data-block="approvals"] .signatory-row > div:nth-child(3) { text-align: right; margin-top: 0; }
            .document > div[data-block="approvals"] .signatory-row > div:nth-child(2) span { border-bottom: 1px solid black; display: inline-block; width: 100%; }
            span.auto-field { background: none; }
        </style>
        """
        return f'<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"><title>Заява</title>{css}</head><body><div class="document">{content_html}</div></body></html>'

    def _build_fallback_html(self, blocks: dict) -> str:
        """Будує простий HTML з блоків (fallback без raw HTML)."""
        block_order = ['header', 'title', 'content', 'applicant_signature', 'approvals']
        content_parts = []
        for block_name in block_order:
            if block_name in blocks and blocks[block_name]:
                content_parts.append(f'<div data-block="{block_name}">{blocks[block_name]}</div>')
        return self._wrap_html_for_pdf('\n'.join(content_parts))

    def _get_output_path(self, document: Document) -> Path:
        """Генерує шлях для збереження файлу."""
        year = document.date_start.year
        month_ua = _get_ukrainian_month(document.date_start, document.date_end)
        status_folder = UKRAINIAN_STATUS.get(document.status, "чернетки")

        # Форматуємо ім'я файлу
        initials = _format_surname_initials(document.staff.pib_nom)
        days = document.days_count

        if document.doc_type == DocumentType.TERM_EXTENSION:
            # Для продовження: year/продовження/status/filename.pdf
            filename = f"{initials} продовження {days} днів.pdf"
            return self.storage_dir / str(year) / "продовження" / status_folder / filename
        else:
            # Для відпусток: year/month/status/filename.pdf
            doc_type = "відпустка" if document.doc_type == DocumentType.VACATION_PAID else "відпустка_без_зарплати"
            filename = f"{initials} {doc_type} {month_ua} {days} днів.pdf"
            return self.storage_dir / str(year) / month_ua / status_folder / filename

    def rollback_to_draft(self, document: Document, reason: str | None = None) -> None:
        """Повертає документ у статус Draft, видаляє старі файли."""
        try:
            if document.file_docx_path:
                pdf_path = Path(document.file_docx_path)
                if pdf_path.exists():
                    pdf_path.unlink()

            if document.file_scan_path:
                scan_path = Path(document.file_scan_path)
                obsolete_dir = self.storage_dir / "obsolete"
                obsolete_dir.mkdir(exist_ok=True)
                timestamp = int(__import__('time').time())
                new_name = f"{scan_path.stem}_{timestamp}{scan_path.suffix}"
                obsolete_path = obsolete_dir / new_name
                if scan_path.exists():
                    shutil.move(str(scan_path), str(obsolete_path))

            document.status = DocumentStatus.DRAFT
            document.file_docx_path = None
            document.file_scan_path = None
            document.signed_at = None
            document.processed_at = None
            document.rollback_reason = reason
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise DocumentGenerationError(f"Помилка відкату документа: {e}") from e

    def process_document(self, document: Document) -> None:
        """Обробляє підписаний документ."""
        try:
            if document.status != DocumentStatus.SIGNED:
                raise DocumentGenerationError("Документ має бути підписаним для обробки")

            if document.doc_type.value == "vacation_paid":
                document.staff.vacation_balance -= document.days_count

            if document.file_scan_path:
                scan_path = Path(document.file_scan_path)
                processed_dir = self._get_output_path(document).parent
                processed_path = processed_dir / scan_path.name
                if scan_path.exists():
                    shutil.move(str(scan_path), str(processed_path))
                    document.file_scan_path = str(processed_path)

            document.status = DocumentStatus.PROCESSED
            document.processed_at = __import__('datetime').datetime.now()
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise DocumentGenerationError(f"Помилка обробки документа: {e}") from e

    def set_applicant_signed(self, document: Document, comment: str | None = None) -> None:
        """Заявник підписав документ."""
        document.applicant_signed_at = __import__('datetime').datetime.now()
        document.applicant_signed_comment = comment
        self.db.commit()

    def set_approval(self, document: Document, comment: str | None = None) -> None:
        """Диспетчерська перевірила документ (Перевірено диспетчерською)."""
        document.approval_at = __import__('datetime').datetime.now()
        document.approval_comment = comment
        self.db.commit()

    def set_department_head_signed(self, document: Document, comment: str | None = None) -> None:
        """Завідувач кафедри підписав документ."""
        document.department_head_at = __import__('datetime').datetime.now()
        document.department_head_comment = comment
        self.db.commit()

    def set_approval_order(self, document: Document, comment: str | None = None) -> None:
        """Підписано наказом."""
        document.approval_order_at = __import__('datetime').datetime.now()
        document.approval_order_comment = comment
        self.db.commit()

    def set_rector_signed(self, document: Document, comment: str | None = None) -> None:
        """Ректор підписав документ."""
        document.rector_at = __import__('datetime').datetime.now()
        document.rector_comment = comment
        self.db.commit()

    def set_scanned(self, document: Document, comment: str | None = None) -> None:
        """Документ відскановано (вхідний скан)."""
        document.scanned_at = __import__('datetime').datetime.now()
        document.scanned_comment = comment
        self.db.commit()

    def set_tabel_added(self, document: Document, comment: str | None = None) -> None:
        """Додано до табелю."""
        document.tabel_added_at = __import__('datetime').datetime.now()
        document.tabel_added_comment = comment
        self.db.commit()

    def clear_workflow_step(self, document: Document, step: str) -> None:
        """Очищає етап підписання."""
        import datetime
        now = datetime.datetime.now()
        if step == "applicant":
            document.applicant_signed_at = None
            document.applicant_signed_comment = None
        elif step == "approval":
            document.approval_at = None
            document.approval_comment = None
        elif step == "department_head":
            document.department_head_at = None
            document.department_head_comment = None
        elif step == "approval_order":
            document.approval_order_at = None
            document.approval_order_comment = None
        elif step == "rector":
            document.rector_at = None
            document.rector_comment = None
        elif step == "scanned":
            document.scanned_at = None
            document.scanned_comment = None
        elif step == "tabel":
            document.tabel_added_at = None
            document.tabel_added_comment = None
        self.db.commit()
