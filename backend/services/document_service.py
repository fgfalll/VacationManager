"""Сервіс генерації документів з Word шаблонів."""

import datetime
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.models.document import Document
from backend.models.settings import Approvers, SystemSettings
from backend.models.staff import Staff
from backend.services.grammar_service import GrammarService
from shared.enums import DocumentStatus, DocumentType
from shared.exceptions import DocumentGenerationError

settings = get_settings()


class DocumentService:
    """
    Сервіс для генерації Word документів з шаблонів.

    Використовує docxtpl для заповнення Word шаблонів даними
    про співробітника та відпустку.

    Example:
        >>> service = DocumentService(db, grammar_service)
        >>> path = service.generate_document(document)
        >>> print(path)
        Path("storage/2025/07_july/draft/ivanov_42.docx")
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
        self.templates_dir = settings.templates_dir
        self.storage_dir = settings.storage_dir

    def generate_document(self, document: Document) -> Path:
        """
        Генерує .docx файл на основі шаблону та даних документа.

        Args:
            document: Об'єкт документа

        Returns:
            Path до створеного файлу

        Raises:
            DocumentGenerationError: Якщо не вдалося згенерувати документ
        """
        try:
            # Вибір шаблону
            template_path = self._get_template_path(document.doc_type)
            if not template_path.exists():
                raise DocumentGenerationError(
                    f"Шаблон не знайдено: {template_path}"
                )

            doc_template = DocxTemplate(template_path)

            # Підготовка контексту
            context = self._build_context(document)

            # Рендер
            doc_template.render(context)

            # Збереження
            output_path = self._get_output_path(document)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc_template.save(output_path)

            # Оновлення документа
            document.file_docx_path = str(output_path)
            document.status = DocumentStatus.ON_SIGNATURE
            self.db.commit()

            return output_path

        except Exception as e:
            self.db.rollback()
            raise DocumentGenerationError(f"Помилка генерації документа: {e}") from e

    def _build_context(self, document: Document) -> dict[str, Any]:
        """
        Збирає контекст для шаблону.

        Args:
            document: Об'єкт документа

        Returns:
            Словник з даними для шаблону
        """
        staff = document.staff
        settings_data = self._load_settings()

        # Базові дані
        context = {
            # Університет
            "university_name": settings_data.get("university_name", "Національного університету"),
            # Ректор
            "rector_name_dav": settings_data.get("rector_name_dative", ""),
            "rector_title": settings_data.get("rector_title", ""),
            # Кафедра/підрозділ
            "dept_name": settings_data.get("dept_name", ""),
            # Заявник - ПІБ в різних відмінках
            "applicant_name": self.grammar.format_for_document(
                staff.pib_nom, document.doc_type
            ),
            "applicant_full_name_nom": staff.pib_nom,  # Називний
            "applicant_full_name_gen": self.grammar.to_genitive(staff.pib_nom),  # Родовий
            # Посада в різних відмінках
            "applicant_position_nom": staff.position,  # Називний
            "applicant_position_gen": self.grammar.to_genitive(staff.position),  # Родовий
            "applicant_position_short": self._get_short_position(staff.position),  # Скорочена
            # Відпустка
            "date_start": document.date_start.strftime("%d.%m"),
            "date_end": document.date_end.strftime("%d.%m"),
            "date_end_year": document.date_end.year,
            "days_count": document.days_count,
            # Оплата
            "payment_period": document.payment_period or self._get_payment_period(document),
            "payment_period_text": self._get_payment_period_text(document),
            # Кастомний текст (якщо є)
            "custom_text": document.custom_text or "",
        }

        # Вчений ступінь (якщо є)
        if staff.degree:
            context["applicant_degree"] = staff.degree

        # Блок підпису завідувача кафедри (якщо заявник не є завідувачем)
        dept_head_id = settings_data.get("dept_head_id")
        if dept_head_id and staff.id != dept_head_id:
            context["show_dept_head_signature"] = True
            head = self.db.query(Staff).filter(Staff.id == dept_head_id).first()
            if head:
                context["dept_head_name"] = head.pib_nom
                # Скорочена назва посади для підпису
                context["dept_head_position"] = self._get_short_position(head.position)
                # Перевіряємо чи в.о.
                dept_head_is_acting = settings_data.get("dept_head_is_acting", False)
                if dept_head_is_acting:
                    context["dept_head_position"] = "В.о. " + context["dept_head_position"]
        else:
            context["show_dept_head_signature"] = False

        # Блок погоджувачів
        context["approvers"] = self._get_approvers()

        # Тип документа для умовної логіки в шаблоні
        context["is_vacation_paid"] = document.doc_type == DocumentType.VACATION_PAID
        context["is_vacation_unpaid"] = document.doc_type == DocumentType.VACATION_UNPAID
        context["is_term_extension"] = document.doc_type == DocumentType.TERM_EXTENSION

        return context

    def _get_short_position(self, position: str) -> str:
        """
        Отримує скорочену назву посади.

        Args:
            position: Повна назва посади

        Returns:
            Скорочена назва
        """
        # Словник скорочень
        abbreviations = {
            "кафедри": "каф.",
            "кафедра": "каф.",
            "професора": "проф.",
            "доцента": "доц.",
            "старшого викладача": "ст. викл.",
            "асистента": "ас.",
            "доктора": "д-ра",
        }

        result = position
        for full, short in abbreviations.items():
            result = result.replace(full, short)
        return result

    def _get_template_path(self, doc_type: DocumentType) -> Path:
        """
        Повертає шлях до шаблону для типу документа.

        Args:
            doc_type: Тип документа

        Returns:
            Path до файлу шаблону
        """
        template_map = {
            DocumentType.VACATION_PAID: "vacation_paid.docx",
            DocumentType.VACATION_UNPAID: "vacation_unpaid.docx",
            DocumentType.TERM_EXTENSION: "term_extension.docx",
        }
        return self.templates_dir / template_map[doc_type]

    def _get_output_path(self, document: Document) -> Path:
        """
        Генерує шлях для збереження файлу.

        Структура: storage/{year}/{month}/{status}/{filename}

        Args:
            document: Об'єкт документа

        Returns:
            Path для збереження файлу
        """
        year = document.date_start.year
        month = document.date_start.strftime("%m_%B").lower()
        status = document.status.value

        # Формуємо ім'я файлу
        surname = document.staff.pib_nom.split()[0] if document.staff.pib_nom.split() else "unknown"
        filename = f"{surname}_{document.id}.docx"

        return self.storage_dir / str(year) / month / status / filename

    def _load_settings(self) -> dict[str, Any]:
        """
        Завантажує налаштування з бази даних.

        Returns:
            Словник з налаштуваннями
        """
        return {
            "university_name": SystemSettings.get_value(
                self.db, "university_name", "Національного університету"
            ),
            "rector_name_dative": SystemSettings.get_value(
                self.db, "rector_name_dative", ""
            ),
            "rector_title": SystemSettings.get_value(
                self.db, "rector_title", ""
            ),
            "dept_name": SystemSettings.get_value(
                self.db, "dept_name", ""
            ),
            "dept_head_id": SystemSettings.get_value(
                self.db, "dept_head_id", None
            ),
            "dept_head_is_acting": SystemSettings.get_value(
                self.db, "dept_head_is_acting", False
            ),
        }

    def _get_approvers(self) -> list[dict[str, str]]:
        """
        Отримує список погоджувачів.

        Returns:
            Список словників з даними погоджувачів
        """
        approvers = self.db.query(Approvers).order_by(Approvers.order_index).all()
        return [
            {
                "position": a.position_name,
                "name": a.full_name_dav,
            }
            for a in approvers
        ]

    def _get_payment_period(self, document: Document) -> str:
        """
        Форматує період оплати.

        Args:
            document: Об'єкт документа

        Returns:
            Текст періоду оплати
        """
        start = document.date_start
        # Якщо дата в першій половині місяця
        if start.day <= 15:
            return self.grammar.format_payment_period(start.year, start.month, True)
        else:
            return self.grammar.format_payment_period(start.year, start.month, False)

    def _get_payment_period_text(self, document: Document) -> str:
        """
        Форматує текст періоду оплати для заяви.

        Args:
            document: Об'єкт документа

        Returns:
            Текст періоду оплати у форматі "за першу половину грудня 2025 року"
        """
        start = document.date_start
        months_uk = [
            "січня", "лютого", "березня", "квітня", "травня", "червня",
            "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
        ]
        month_name = months_uk[start.month - 1]

        # Якщо дата в першій половині місяця
        if start.day <= 15:
            return f"за першу половину {month_name} {start.year} року"
        else:
            return f"за другу половину {month_name} {start.year} року"

    def _get_basis_text(self, staff: Staff) -> str:
        """
        Формує текст підстави для відпустки.

        Args:
            staff: Співробітник

        Returns:
            Текст підстави
        """
        work_basis_map = {
            "contract": "контракту",
            "competitive": "конкурсної основи",
            "statement": "заяви",
        }
        basis = work_basis_map.get(staff.work_basis.value, "контракту")
        return f"на підставі {basis}"

    def rollback_to_draft(self, document: Document) -> None:
        """
        Повертає документ у статус Draft, видаляє старі файли.

        Args:
            document: Об'єкт документа

        Raises:
            DocumentGenerationError: Якщо не вдалося виконати відкат
        """
        try:
            # Видалення .docx
            if document.file_docx_path:
                docx_path = Path(document.file_docx_path)
                if docx_path.exists():
                    docx_path.unlink()

            # Переміщення скану в obsolete
            if document.file_scan_path:
                scan_path = Path(document.file_scan_path)
                obsolete_dir = self.storage_dir / "obsolete"
                obsolete_dir.mkdir(exist_ok=True)
                obsolete_path = obsolete_dir / scan_path.name

                # Перейменовуємо з timestamp щоб уникнути колізій
                import time
                timestamp = int(time.time())
                new_name = f"{scan_path.stem}_{timestamp}{scan_path.suffix}"
                obsolete_path = obsolete_dir / new_name

                if scan_path.exists():
                    shutil.move(str(scan_path), str(obsolete_path))

            # Скидання полів
            document.status = DocumentStatus.DRAFT
            document.file_docx_path = None
            document.file_scan_path = None
            document.signed_at = None
            document.processed_at = None

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise DocumentGenerationError(f"Помилка відкату документа: {e}") from e

    def process_document(self, document: Document) -> None:
        """
        Обробляє підписаний документ (списує дні відпустки, продовжує контракт).

        Args:
            document: Об'єкт документа

        Raises:
            DocumentGenerationError: Якщо не вдалося обробити документ
        """
        try:
            if document.status != DocumentStatus.SIGNED:
                raise DocumentGenerationError(
                    "Документ має бути підписаним для обробки"
                )

            # Списуємо дні (тільки для оплачуваної відпустки)
            if document.doc_type in (
                DocumentType.VACATION_PAID,
            ):
                document.staff.vacation_balance -= document.days_count

            # Автоматично продовжуємо контракт для заяв про продовження
            if document.doc_type == DocumentType.TERM_EXTENSION:
                # Оновлюємо дату закінчення контракту
                document.staff.term_end = document.date_end
                # Це може бути новий термін (наприклад +5 років)
                # або дата вказана в документі

            # Зберігаємо файл в processed
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
