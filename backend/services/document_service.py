"""Сервіс генерації PDF документів з WYSIWYG редактора."""

import datetime
import json
import os
import shutil
import subprocess
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generator

from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.models.document import Document
from backend.models.settings import Approvers, SystemSettings
from backend.services.attendance_service import AttendanceConflictError, AttendanceLockedError
from backend.services.grammar_service import GrammarService
from shared.enums import DocumentStatus, DocumentType
from shared.exceptions import DocumentGenerationError
from shared.constants import SETTING_PDF_TERM_EXTENSION_TEMPLATE


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
    DocumentStatus.SIGNED_BY_APPLICANT: "підписано_заявником",
    DocumentStatus.APPROVED_BY_DISPATCHER: "погоджено_диспетчером",
    DocumentStatus.SIGNED_DEP_HEAD: "підписано_зав_кафедри",
    DocumentStatus.AGREED: "погоджено",
    DocumentStatus.SIGNED_RECTOR: "підписано_ректором",
    DocumentStatus.SCANNED: "відскановано",
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


def _get_employment_doc_type_label(doc_type) -> str:
    """Повертає українську назву типу документа прийому."""
    employment_labels = {
        "employment_contract": "прийом_контракт",
        "employment_competition": "прийом_конкурс",
        "employment_pdf": "прийом_PDF",
    }
    return employment_labels.get(doc_type.value, "прийом")


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
        Path("storage/2025/01_january/підписано_заявником/dmytrenko_42.pdf")
    """

    def __init__(self, db: Session, grammar: GrammarService) -> None:
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
            # Для PDF типів документів - копіюємо завантажений шаблон
            if document.doc_type == DocumentType.TERM_EXTENSION_PDF:
                template_path = SystemSettings.get_value(
                    self.db, SETTING_PDF_TERM_EXTENSION_TEMPLATE, ""
                )
                if not template_path or not Path(template_path).exists():
                    raise DocumentGenerationError(
                        "Не налаштовано PDF шаблон для цього типу документа. "
                        "Зверніться до адміністратора."
                    )

                output_path = self._get_output_path(document)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Копіюємо PDF шаблон
                import shutil
                shutil.copy(template_path, output_path)

                document.file_docx_path = str(output_path)
                self.db.commit()

                return output_path

            if not raw_html and not document.editor_content:
                raise DocumentGenerationError(
                    "Відсутній контент. Спочатку створіть документ у редакторі."
                )

            output_path = self._get_output_path(document)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            self._generate_pdf(document, output_path, raw_html)

            document.file_docx_path = str(output_path)
            # Status stays as DRAFT - will change to SIGNED_BY_APPLICANT when applicant signs
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

        finally:
            debug_html_path = Path(output_path).parent / f"{Path(output_path).stem}_debug.html"
            if os.path.exists(html_path):
                shutil.copy(html_path, debug_html_path)
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

    def generate_document_from_template(self, document: Document, staff_data: dict, signatories: list = None, bulk_mode: bool = False) -> Path:
        """
        Генерує документ з HTML шаблону (без WYSIWYG редактора).

        Args:
            document: Об'єкт документа
            staff_data: Дані співробітника (словник)
            signatories: Список погоджувачів
            bulk_mode: Якщо True, зберігає в підпапку "bulk"

        Returns:
            Path до створеного файлу
        """
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path as FilePath
        from backend.models.settings import SystemSettings

        # Get template directory
        templates_dir = FilePath(__file__).parent.parent.parent / 'desktop' / 'templates' / 'documents'

        # Choose template based on doc type
        if document.doc_type in (
            DocumentType.TERM_EXTENSION,
            DocumentType.TERM_EXTENSION_CONTRACT,
            DocumentType.TERM_EXTENSION_COMPETITION,
            DocumentType.TERM_EXTENSION_PDF,
        ):
            # Map to specific term extension template or use default
            template_map = {
                DocumentType.TERM_EXTENSION: 'term_extension.html',
                DocumentType.TERM_EXTENSION_CONTRACT: 'term_extension_contract.html',
                DocumentType.TERM_EXTENSION_COMPETITION: 'term_extension_competition.html',
                DocumentType.TERM_EXTENSION_PDF: 'term_extension_pdf.html',
            }
            template_name = template_map.get(document.doc_type, 'term_extension.html')
        elif document.doc_type == DocumentType.VACATION_UNPAID:
            template_name = 'vacation_unpaid.html'
        elif document.doc_type in (
            DocumentType.VACATION_PAID,
            DocumentType.VACATION_MAIN,
            DocumentType.VACATION_ADDITIONAL,
            DocumentType.VACATION_CHORNOBYL,
            DocumentType.VACATION_CREATIVE,
            DocumentType.VACATION_STUDY,
            DocumentType.VACATION_CHILDREN,
            DocumentType.VACATION_MATERNITY,
            DocumentType.VACATION_CHILDCARE,
        ):
            # Map to specific template or use vacation_paid as default
            template_map = {
                DocumentType.VACATION_MAIN: 'vacation_main.html',
                DocumentType.VACATION_ADDITIONAL: 'vacation_additional.html',
                DocumentType.VACATION_CHORNOBYL: 'vacation_chornobyl.html',
                DocumentType.VACATION_CREATIVE: 'vacation_creative.html',
                DocumentType.VACATION_STUDY: 'vacation_study.html',
                DocumentType.VACATION_CHILDREN: 'vacation_children.html',
                DocumentType.VACATION_MATERNITY: 'vacation_maternity.html',
                DocumentType.VACATION_CHILDCARE: 'vacation_childcare.html',
            }
            template_name = template_map.get(document.doc_type, 'vacation_paid.html')
        elif document.doc_type in (
            DocumentType.VACATION_UNPAID_STUDY,
            DocumentType.VACATION_UNPAID_MANDATORY,
            DocumentType.VACATION_UNPAID_AGREEMENT,
            DocumentType.VACATION_UNPAID_OTHER,
        ):
            # Map to specific unpaid template or use vacation_unpaid as default
            template_map = {
                DocumentType.VACATION_UNPAID_STUDY: 'vacation_unpaid_study.html',
                DocumentType.VACATION_UNPAID_MANDATORY: 'vacation_unpaid_mandatory.html',
                DocumentType.VACATION_UNPAID_AGREEMENT: 'vacation_unpaid_agreement.html',
                DocumentType.VACATION_UNPAID_OTHER: 'vacation_unpaid_other.html',
            }
            template_name = template_map.get(document.doc_type, 'vacation_unpaid.html')
        else:
            template_name = 'vacation_paid.html'  # Default

        # Load template
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        template = env.get_template(template_name)

        # Get settings from database using SystemSettings (like builder tab)
        university_name = SystemSettings.get_value(self.db, 'university_name', '')
        rector_name_nominative = SystemSettings.get_value(self.db, 'rector_name_nominative', '')

        # Format rector name from nominative to dative (same as builder tab)
        rector_name = ""
        if rector_name_nominative:
            parts = rector_name_nominative.split()
            if len(parts) >= 3:
                # Check if first word is surname (doesn't end with typical female name endings)
                if parts[0].endswith(('а', 'я', 'я')) and not parts[0].endswith(('вна', 'вич', 'ська', 'цька')):
                    # "Вікторія Іванівна Філонич" - First Middle Last
                    first_name = self.grammar.to_dative(parts[0])
                    last_name = parts[-1].upper()
                    rector_name = f"{first_name} {last_name}"
                else:
                    # "Філонич Вікторія Іванівна" - Last First Middle
                    # Find the first name (usually second word, ends with а/я)
                    for i, part in enumerate(parts[1:], 1):
                        if part.endswith(('а', 'я', 'я')) and not part.endswith(('вна', 'вич', 'ська', 'цька')):
                            first_name = self.grammar.to_dative(part)
                            last_name = parts[0].upper()
                            rector_name = f"{first_name} {last_name}"
                            break
            elif len(parts) == 2:
                # "Ім'я ПРІЗВИЩЕ" or "ПРІЗВИЩЕ Ім'я"
                if parts[0].endswith(('а', 'я', 'я')):
                    first_name = self.grammar.to_dative(parts[0])
                    last_name = parts[1].upper()
                else:
                    first_name = self.grammar.to_dative(parts[1])
                    last_name = parts[0].upper()
                rector_name = f"{first_name} {last_name}"
            else:
                rector_name = rector_name_nominative

        # Fallback to rector_name_dative if formatting didn't work
        if not rector_name:
            rector_name = SystemSettings.get_value(self.db, 'rector_name_dative', '') or SystemSettings.get_value(self.db, 'rector_name', '')

        # Format dates for display (Ukrainian format like builder)
        months_uk = ["січня", "лютого", "березня", "квітня", "травня", "червня",
                     "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]

        # Handle None dates (for employment documents)
        if document.date_start is None or document.date_end is None:
            formatted_dates = ""
            payment_period = ""
        else:
            start_month = months_uk[document.date_start.month - 1]
            end_month = months_uk[document.date_end.month - 1]

            if document.date_start == document.date_end:
                formatted_dates = f"{document.date_start.day} {start_month} {document.date_start.year} року"
            elif document.date_start.month == document.date_end.month and document.date_start.year == document.date_end.year:
                formatted_dates = f"з {document.date_start.day} по {document.date_end.day} {start_month} {document.date_start.year} року"
            elif document.date_start.year == document.date_end.year:
                formatted_dates = f"з {document.date_start.day} {start_month} по {document.date_end.day} {end_month} {document.date_start.year} року"
            else:
                formatted_dates = f"{document.date_start.strftime('%d.%m.%Y')} - {document.date_end.strftime('%d.%m.%Y')}"

            # Payment period - Ukrainian format
            payment_month = months_uk[document.date_start.month - 1]
            payment_year = document.date_start.year
            payment_half = "першій" if document.date_start.day <= 15 else "другій"
            payment_period = f"у {payment_half} половині {payment_month} {payment_year} року"

        # Staff name in genitive case for document header (same as builder)
        # "Дмитренко Вікторія Іванівна" → "Дмитренко Вікторії Іванівни"
        pib_nom = staff_data.get('pib_nom', '')
        staff_name_genitive = pib_nom  # Default to nominative
        if pib_nom:
            try:
                parts = pib_nom.split()
                if len(parts) >= 3:
                    # Surname stays the same, first name and middle name to genitive
                    surname = parts[0]
                    first_name = self.grammar.to_genitive(parts[1])
                    middle_name = self.grammar.to_genitive(parts[2])
                    staff_name_genitive = f"{surname} {first_name} {middle_name}"
                elif len(parts) == 2:
                    surname = parts[0]
                    first_name = self.grammar.to_genitive(parts[1])
                    staff_name_genitive = f"{surname} {first_name}"
            except Exception:
                staff_name_genitive = pib_nom

        staff_name_nom = pib_nom  # Nominative

        # Employment type note (same as builder tab)
        # Note is only added for совмісники, not for main position
        employment_type_note = ""
        emp_type = staff_data.get('employment_type', '')

        # Only add note for external/internal (совмісники), not for main
        if emp_type == 'external':
            employment_type_note = "(зовнішній сумісник)"
        elif emp_type == 'internal':
            employment_type_note = "(внутрішнє сумісництво)"
        # For 'main': no note (matching builder behavior)

        # Build full position with department (like builder tab)
        # Get department from SystemSettings (same as builder tab)
        dept_name_raw = SystemSettings.get_value(self.db, "dept_name", "")
        dept_abbr_raw = SystemSettings.get_value(self.db, "dept_abbr", "")

        staff_position = staff_data.get('position', '')
        # Capitalize first letter for document
        staff_position_capitalized = staff_position[0].upper() + staff_position[1:] if staff_position else ''
        staff_position_nom = staff_position_capitalized  # Default to capitalized position

        # Use abbreviation if available, otherwise full name
        dept_for_position = dept_abbr_raw if dept_abbr_raw else dept_name_raw

        if dept_for_position and staff_position:
            # Build full position if needed
            position_lower = staff_position.lower()
            if "кафедри" not in position_lower and "кафедру" not in position_lower and "кафедр" not in position_lower:
                if any(x in position_lower for x in ["професор", "доцент", "асистент", "викладач", "старший викладач", "фахівець"]):
                    staff_position_nom = f"{staff_position_capitalized} кафедри {dept_for_position}"

        # Auto-calculate multiline for signatories based on text length
        processed_signatories = []
        for sig in (signatories or []):
            pos = sig.get('position', '')
            pos_multiline_provided = sig.get('position_multiline', '')

            # If position_multiline is already set and contains a line break, use it as-is
            if '\n' in pos_multiline_provided:
                pos_multiline = pos_multiline_provided
            # Auto-split if too long (more than 25 chars) and no multiline provided
            elif len(pos) > 25 and '\n' not in pos:
                # Try to split at natural break point
                if 'завідувача' in pos:
                    pos_multiline = pos.replace('завідувача ', 'завідувача\n', 1)
                elif ' директор' in pos:
                    pos_multiline = pos.replace(' директор', '\nдиректор', 1)
                elif ' голова' in pos:
                    pos_multiline = pos.replace(' голова', '\nголова', 1)
                else:
                    # Find middle space
                    mid = len(pos) // 2
                    space_pos = pos.rfind(' ', 0, mid)
                    if space_pos > 0:
                        pos_multiline = pos[:space_pos] + '\n' + pos[space_pos+1:]
                    else:
                        pos_multiline = pos
            else:
                pos_multiline = pos_multiline_provided if pos_multiline_provided else pos

            processed_signatories.append({
                'position': pos,
                'position_multiline': pos_multiline,
                'name': sig.get('name', '')
            })

        # Format days count with correct Ukrainian grammar
        days = document.days_count
        if days == 1:
            days_formatted = "1 календарний день"
        elif days in (2, 3, 4):
            days_formatted = f"{days} календарні дні"
        else:
            days_formatted = f"{days} календарних днів"

        # Render template with real settings data
        raw_html = template.render({
            'university_name': university_name or 'Університет',
            'rector_name': rector_name or 'Ректору',
            'staff_position_nom': staff_position_nom,
            'staff_name_nom': staff_name_nom,
            'staff_name_gen': staff_name_genitive,  # For document header (genitive case)
            'employment_type_note': employment_type_note,
            'days_count': days_formatted,
            'formatted_dates': formatted_dates,
            'payment_period': payment_period,
            'staff_position': staff_position_nom,
            'staff_name_nom': staff_name_nom,
            'signatories': processed_signatories,
        })

        # Wrap for PDF
        html_content = self._wrap_html_for_pdf(raw_html)

        # Save HTML to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            html_path = f.name

        try:
            # Get output path
            output_path = self._get_output_path(document, bulk_mode=bulk_mode)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate PDF
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

            document.file_docx_path = str(output_path)
            self.db.commit()

            # Save debug HTML copy before cleanup
            debug_html_path = Path(output_path).parent / f"{Path(output_path).stem}_debug.html"
            try:
                shutil.copy(html_path, debug_html_path)
            except Exception:
                pass

            return output_path

        except Exception as e:
            self.db.rollback()
            raise DocumentGenerationError(f"Помилка генерації документа з шаблону: {e}") from e
        finally:
            # Clean up temp HTML file (debug copy already saved above)
            try:
                if 'html_path' in dir() and os.path.exists(html_path):
                    os.unlink(html_path)
            except:
                pass

    def _render_html_to_pdf(self, html_content: str, document: Document, creation_date: date = None) -> Path:
        """
        Convert HTML content to PDF and save.

        Args:
            html_content: Rendered HTML template
            document: Document object for path determination
            creation_date: Date of document creation (for folder naming)

        Returns:
            Path to generated PDF
        """
        # Wrap HTML for PDF
        wrapped_html = self._wrap_html_for_pdf(html_content)

        # Save HTML to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(wrapped_html)
            html_path = f.name

        try:
            # Get output path using creation date for folder naming
            output_path = self._get_output_path(document, creation_date)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate PDF
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

            document.file_docx_path = str(output_path)
            self.db.commit()

            return output_path

        except Exception as e:
            self.db.rollback()
            raise DocumentGenerationError(f"Помилка генерації PDF: {e}") from e
        finally:
            # Clean up temp HTML file
            try:
                os.unlink(html_path)
            except:
                pass

    def _get_output_path(self, document: Document, creation_date: date = None, bulk_mode: bool = False) -> Path:
        """Генерує шлях для збереження файлу.

        Args:
            document: Об'єкт документа
            creation_date: Дата створення (для назви папки). Якщо None, використовується поточна дата.
            bulk_mode: Якщо True, зберігає в підпапку "bulk"
        """
        # Use creation date for folder naming (current date by default)
        if creation_date is None:
            creation_date = date.today()

        year = creation_date.year
        month_ua = _get_ukrainian_month(creation_date, creation_date)
        status_folder = UKRAINIAN_STATUS.get(document.status, "чернетки")

        # Add bulk subfolder if in bulk mode
        bulk_subfolder = "bulk" if bulk_mode else ""

        # Форматуємо ім'я файлу
        # For employment documents, use new_employee_data instead of staff
        is_employment = document.doc_type.value.startswith("employment_")
        if is_employment and document.new_employee_data:
            employee_data = document.new_employee_data
            initials = _format_surname_initials(employee_data.get("pib_nom", ""))
            doc_type_label = _get_employment_doc_type_label(document.doc_type)
            # For employment, use contract dates for folder naming
            if document.date_start:
                emp_year = document.date_start.year
                month_ua = _get_ukrainian_month(document.date_start, document.date_start)
            else:
                emp_year = year
                month_ua = ""
            filename = f"{initials} {doc_type_label} {month_ua}.pdf"
            if bulk_mode:
                return self.storage_dir / str(emp_year) / "прийом" / status_folder / bulk_subfolder / filename
            return self.storage_dir / str(emp_year) / "прийом" / status_folder / filename

        # Regular staff documents
        initials = _format_surname_initials(document.staff.pib_nom)
        days = document.days_count

        if document.doc_type == DocumentType.TERM_EXTENSION:
            # Для продовження: year/продовження/status/bulk/filename.pdf
            filename = f"{initials} продовження {days} днів.pdf"
            if bulk_mode:
                return self.storage_dir / str(year) / "продовження" / status_folder / bulk_subfolder / filename
            return self.storage_dir / str(year) / "продовження" / status_folder / filename
        else:
            # Для відпусток: year/month/status/bulk/filename.pdf
            doc_type = "відпустка" if document.doc_type == DocumentType.VACATION_PAID else "відпустка_без_зарплати"
            filename = f"{initials} {doc_type} {month_ua} {days} днів.pdf"
            if bulk_mode:
                return self.storage_dir / str(year) / month_ua / status_folder / bulk_subfolder / filename
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
            if document.status != DocumentStatus.SIGNED_RECTOR:
                raise DocumentGenerationError("Документ має бути підписаним для обробки")

            # Skip vacation balance update for non-vacation documents
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
            document.processed_at = datetime.datetime.now()
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise DocumentGenerationError(f"Помилка обробки документа: {e}") from e

    def set_applicant_signed(self, document: Document, comment: str | None = None) -> None:
        """Заявник підписав документ - переводимо на підпис."""
        document.applicant_signed_at = datetime.datetime.now()
        document.applicant_signed_comment = comment
        
        # Move file from draft folder to signed_by_applicant folder
        if document.file_docx_path:
            old_path = Path(document.file_docx_path)
            if old_path.exists():
                new_path = self._get_output_path(document)
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_path))
                document.file_docx_path = str(new_path)

        document.update_status_from_workflow()
        self.db.commit()

    def set_approval(self, document: Document, comment: str | None = None) -> None:
        """Диспетчерська перевірила документ (Перевірено диспетчерською)."""
        document.approval_at = datetime.datetime.now()
        document.approval_comment = comment
        document.update_status_from_workflow()
        self.db.commit()

    def set_department_head_signed(self, document: Document, comment: str | None = None) -> None:
        """Завідувач кафедри підписав документ."""
        document.department_head_at = datetime.datetime.now()
        document.department_head_comment = comment
        document.update_status_from_workflow()
        self.db.commit()

    def set_approval_order(self, document: Document, comment: str | None = None) -> None:
        """Підписано наказом."""
        document.approval_order_at = datetime.datetime.now()
        document.approval_order_comment = comment
        document.update_status_from_workflow()
        self.db.commit()

    def set_rector_signed(self, document: Document, comment: str | None = None) -> None:
        """Ректор підписав документ."""
        document.rector_at = datetime.datetime.now()
        document.rector_comment = comment

        # Перевіряємо, чи місяць документа вже затверджено
        from backend.services.tabel_approval_service import TabelApprovalService

        doc_month = document.date_start.month
        doc_year = document.date_start.year

        approval_service = TabelApprovalService(self.db)
        is_month_locked = approval_service.is_month_locked(doc_month, doc_year)

        if is_month_locked:
            # Якщо місяць вже затверджено, додаємо до корегуючого табелю
            # Це означає, що документ з'явиться в корекції
            document.tabel_added_at = None  # Не додаємо до основного табелю
            document.tabel_added_comment = f"Місяць {doc_month}.{doc_year} вже затверджено. Додано до корегуючого табелю."

            # Отримуємо наступний номер послідовності корекції
            correction_sequence = approval_service.get_or_create_correction_sequence(doc_month, doc_year)

            # Встановлюємо корекційні поля документа
            document.is_correction = True
            document.correction_month = doc_month
            document.correction_year = doc_year
            document.correction_sequence = correction_sequence

            # Створюємо запис у attendance з кодом відпустки для корекції
            self._create_correction_attendance(document, correction_sequence)
        # Note: Do NOT auto-add to tabel here - user must upload scan first,
        # then document will be processed and added to tabel separately

        # Оновлюємо статус (має стати SIGNED_RECTOR, НЕ PROCESSED)
        document.update_status_from_workflow()
        self.db.commit()

    def _create_correction_attendance(self, document: Document, correction_sequence: int = 1) -> None:
        """Створює запис відвідуваності для корегуючого табелю."""
        from backend.models import Attendance
        from backend.models.document import DocumentType
        from backend.services.attendance_service import AttendanceService

        # Визначаємо код відпустки
        if document.doc_type == DocumentType.VACATION_PAID:
            code = "В"
        elif document.doc_type == DocumentType.VACATION_UNPAID:
            code = "НА"
        # Для продовження контракту - код "Р" (присутність на роботі)
        elif document.doc_type in (
            DocumentType.TERM_EXTENSION,
            DocumentType.TERM_EXTENSION_CONTRACT,
            DocumentType.TERM_EXTENSION_COMPETITION,
            DocumentType.TERM_EXTENSION_PDF,
        ):
            code = "Р"
        else:
            return  # Не відпустка - нічого не робимо

        # Використовуємо AttendanceService для консистентності
        att_service = AttendanceService(self.db)

        # Створюємо запис для кожного дня відпустки
        current = document.date_start
        while current <= document.date_end:
            # Перевіряємо, чи вже є запис для цього дня з тією ж послідовністю
            existing = self.db.query(Attendance).filter(
                Attendance.staff_id == document.staff_id,
                Attendance.date == current,
                Attendance.is_correction == True,
                Attendance.correction_month == document.date_start.month,
                Attendance.correction_year == document.date_start.year,
                Attendance.correction_sequence == correction_sequence,
            ).first()

            if not existing:
                try:
                    att_service.create_attendance(
                        staff_id=document.staff_id,
                        attendance_date=current,
                        code=code,
                        hours=Decimal("8.0"),
                        notes=f"Корекція: документ №{document.id}",
                        is_correction=True,
                        correction_month=document.date_start.month,
                        correction_year=document.date_start.year,
                        correction_sequence=correction_sequence,
                    )
                except (AttendanceConflictError, AttendanceLockedError):
                    # Якщо вже є запис або заблоковано, ігноруємо
                    pass

            current += datetime.timedelta(days=1)

    def set_scanned(self, document: Document, file_path: str = None, comment: str | None = None) -> None:
        """Документ відскановано (вхідний скан)."""
        document.scanned_at = datetime.datetime.now()
        document.scanned_comment = comment
        
        if file_path:
            scan_path = Path(file_path)
            if scan_path.exists():
                output_dir = self._get_output_path(document).parent / "scans"
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy file with standardized name
                new_filename = f"scan_{document.id}_{scan_path.name}"
                new_path = output_dir / new_filename
                
                shutil.copy2(str(scan_path), str(new_path))
                document.file_scan_path = str(new_path)
        
        # Create archive snapshot with staff/approver data
        try:
            archive_path = save_document_archive(document, self.db)
            document.archive_metadata_path = str(archive_path)
        except Exception as e:
            # Log but don't fail - archive is optional
            import logging
            logging.warning(f"Failed to create document archive: {e}")
        
        document.update_status_from_workflow()
        self.db.commit()

        # Handle side effects: New Employee Creation and Term Extension
        try:
            from backend.services.staff_service import StaffService
            from backend.models.document import DocumentType
            
            staff_service = StaffService(self.db, changed_by="DOCUMENT_SCAN")
            
            # 1. New Employee Creation
            is_employment = document.doc_type.value.startswith("employment_")
            if is_employment and document.new_employee_data:
                staff_service.create_staff_from_document(document)
                
            # 2. Term Extension
            is_extension = document.doc_type.value.startswith("term_extension") or document.doc_type == DocumentType.TERM_EXTENSION
            if is_extension:
                staff_service.process_term_extension(document)
                
        except Exception as e:
            import logging
            logging.error(f"Failed to process side effects for document {document.id}: {e}")

    def set_tabel_added(self, document: Document, comment: str | None = None) -> None:
        """Додано до табелю."""
        document.tabel_added_at = datetime.datetime.now()
        document.tabel_added_comment = comment
        self.db.commit()

    def clear_workflow_step(self, document: Document, step: str) -> None:
        """Очищає етап підписання."""
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
        
        document.update_status_from_workflow()
        self.db.commit()


# ============================================================================
# Document Archive Functions (standalone, outside DocumentService class)
# ============================================================================

def save_document_archive(document: Document, db: Session) -> Path:
    """
    Зберігає архів документа у JSON форматі при скануванні.
    
    Архів містить знімок усіх даних, потрібних для відтворення документа:
    - Дані співробітника (ПІБ, посада, ступінь)
    - Погоджувачи (посади та імена)
    - Налаштування установи
    - Відрендерений HTML (для pixel-perfect відтворення)
    
    Args:
        document: Об'єкт документа
        db: Сесія бази даних
        
    Returns:
        Path: Шлях до збереженого архіву
    """
    from backend.models.settings import Approvers, SystemSettings
    from backend.services.document_renderer import get_signatories_from_db, _format_signatory_name
    
    # Get storage directory - same location as scan files
    storage_dir = settings.storage_dir / "scans"
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    # Snapshot staff data
    staff = document.staff
    staff_snapshot = {
        "id": staff.id,
        "pib_nom": staff.pib_nom,
        "position": staff.position,
        "degree": staff.degree or "",
        "employment_type": staff.employment_type or "main",
    }
    
    # Snapshot approvers from database
    approvers_snapshot = []
    approvers = db.query(Approvers).order_by(Approvers.order_index).all()
    for approver in approvers:
        display_name = _format_signatory_name(approver.full_name_nom or approver.full_name_dav)
        approvers_snapshot.append({
            "position": approver.position_name,
            "name": display_name,
            "order_index": approver.order_index,
        })
    
    # Also get signatories as they would appear on document (filtered)
    signatories_snapshot = get_signatories_from_db(db, staff)
    
    # Snapshot settings
    settings_snapshot = {
        "university_name": SystemSettings.get_value(db, "university_name", ""),
        "rector_name_nominative": SystemSettings.get_value(db, "rector_name_nominative", ""),
        "rector_name_dative": SystemSettings.get_value(db, "rector_name_dative", ""),
        "department_name": SystemSettings.get_value(db, "dept_name", ""),
        "department_abbr": SystemSettings.get_value(db, "dept_abbr", ""),
        "dept_head_id": SystemSettings.get_value(db, "dept_head_id", None),
    }
    
    # Get rendered HTML if available
    rendered_html = document.rendered_html or ""
    
    # Build archive data
    archive_data = {
        "version": "1.0",
        "archived_at": datetime.datetime.utcnow().isoformat(),
        "document_id": document.id,
        "document_type": document.doc_type.value,
        "staff": staff_snapshot,
        "approvers": approvers_snapshot,
        "signatories": signatories_snapshot,
        "settings": settings_snapshot,
        "rendered_html": rendered_html,
        "dates": {
            "start": document.date_start.isoformat(),
            "end": document.date_end.isoformat(),
            "days_count": document.days_count,
        },
        "workflow": {
            "applicant_signed_at": document.applicant_signed_at.isoformat() if document.applicant_signed_at else None,
            "department_head_at": document.department_head_at.isoformat() if document.department_head_at else None,
            "approval_order_at": document.approval_order_at.isoformat() if document.approval_order_at else None,
            "rector_at": document.rector_at.isoformat() if document.rector_at else None,
            "scanned_at": document.scanned_at.isoformat() if document.scanned_at else None,
        },
        "files": {
            "docx_path": document.file_docx_path,
            "scan_path": document.file_scan_path,
        }
    }
    
    # Generate filename based on document
    surname = staff.pib_nom.split()[0] if staff.pib_nom else "unknown"
    filename = f"doc_{document.id}_{surname}_archive.json"
    filepath = storage_dir / filename
    
    # Save archive
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(archive_data, f, ensure_ascii=False, indent=2)
    
    return filepath


def reconstruct_document_from_archive(archive_path: Path) -> dict:
    """
    Відновлює дані документа з архіву.
    
    Args:
        archive_path: Шлях до JSON архіву
        
    Returns:
        dict: Словник з усіма даними для відтворення документа
    """
    with open(archive_path, 'r', encoding='utf-8') as f:
        archive_data = json.load(f)
    
    return archive_data


def get_document_context_for_display(document: Document, db: Session) -> dict:
    """
    Отримує контекст для відображення документа.
    
    Якщо документ має архів (archive_metadata_path) - завантажує з архіву.
    Інакше - завантажує з бази даних (для чернеток та документів в процесі).
    
    Args:
        document: Об'єкт документа
        db: Сесія бази даних
        
    Returns:
        dict: Контекст для відображення документа з полями:
            - staff: Дані співробітника
            - signatories: Список погоджувачів
            - settings: Налаштування установи
            - rendered_html: Відрендерений HTML (якщо є)
            - from_archive: True якщо завантажено з архіву
    """
    from backend.models.settings import SystemSettings
    from backend.services.document_renderer import get_signatories_from_db, _format_signatory_name
    
    # Check if archive exists
    if document.archive_metadata_path:
        archive_path = Path(document.archive_metadata_path)
        if archive_path.exists():
            archive_data = reconstruct_document_from_archive(archive_path)
            return {
                "staff": archive_data.get("staff", {}),
                "signatories": archive_data.get("signatories", []),
                "settings": archive_data.get("settings", {}),
                "rendered_html": archive_data.get("rendered_html", ""),
                "dates": archive_data.get("dates", {}),
                "from_archive": True,
            }
    
    # Load from database (for drafts or documents without archive)
    staff = document.staff
    staff_data = {
        "id": staff.id,
        "pib_nom": staff.pib_nom,
        "position": staff.position,
        "degree": staff.degree or "",
        "employment_type": staff.employment_type or "main",
    }
    
    signatories = get_signatories_from_db(db, staff)
    
    settings_data = {
        "university_name": SystemSettings.get_value(db, "university_name", ""),
        "rector_name_nominative": SystemSettings.get_value(db, "rector_name_nominative", ""),
        "department_name": SystemSettings.get_value(db, "dept_name", ""),
        "department_abbr": SystemSettings.get_value(db, "dept_abbr", ""),
    }
    
    return {
        "staff": staff_data,
        "signatories": signatories,
        "settings": settings_data,
        "rendered_html": document.rendered_html or "",
        "dates": {
            "start": document.date_start.isoformat() if document.date_start else None,
            "end": document.date_end.isoformat() if document.date_end else None,
            "days_count": document.days_count,
        },
        "from_archive": False,
    }
