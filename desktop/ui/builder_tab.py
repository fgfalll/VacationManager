"""Вкладка конструктора заяв з WYSIWYG редактором."""

import json
import logging
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QComboBox,
    QDateEdit,
    QSpinBox,
    QTextEdit,
    QPushButton,
    QLabel,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QSizePolicy,
    QSplitter,
    QMessageBox,
    QProgressDialog,
    QToolBar,
    QStyle,
    QLineEdit,
    QCalendarWidget,
    QTableView,
    QScrollArea,
    QCheckBox,
    QTabWidget,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QDate
from PyQt6.QtGui import QColor, QTextCharFormat, QBrush
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import joinedload

from shared.enums import DocumentType, DocumentStatus, get_position_label
from backend.core.database import get_db_context
from backend.models.settings import SystemSettings
from desktop.ui.wysiwyg_bridge import WysiwygBridge, WysiwygEditorState

logger = logging.getLogger(__name__)


def _date_range_iter(start: date, end: date):
    """Generator that yields all dates in a range (inclusive)."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _format_date_ukrainian(d: date, include_year: bool = True) -> str:
    """Format date in Ukrainian: '10 січня 2026 року' or '10 січня'."""
    month_names_genitive = {
        1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
        5: "травня", 6: "червня", 7: "липня", 8: "серпня",
        9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
    }
    month = month_names_genitive.get(d.month, "")
    if include_year:
        return f"{d.day} {month} {d.year} року"
    return f"{d.day} {month}"


def _format_date_range_ukrainian(start: date, end: date) -> str:
    """Format date range in Ukrainian."""
    month_names_genitive = {
        1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
        5: "травня", 6: "червня", 7: "липня", 8: "серпня",
        9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
    }

    # Single date
    if start == end:
        return _format_date_ukrainian(start)

    # Same month and year
    if start.month == end.month and start.year == end.year:
        return f"з {start.day} по {end.day} {month_names_genitive[start.month]} {start.year} року"

    # Different months, same year
    if start.year == end.year:
        return f"з {start.day} {month_names_genitive[start.month]} по {end.day} {month_names_genitive[end.month]} {start.year} року"

    # Different years
    return f"з {start.day} {month_names_genitive[start.month]} {start.year} по {end.day} {month_names_genitive[end.month]} {end.year} року"


def _format_dates_for_document(dates: list[date]) -> str:
    """
    Format dates for document display.

    Rules:
    - Single date: "10 січня 2026 року"
    - Consecutive range within same month: "з 12 по 16 січня 2026 року"
    - Multi-month range: "з 12 по 16 січня 2026 року та з 4 по 11 лютого 2026 року"
    - Many single dates same month (after ranges): "10, 27 січня"
    - Many single dates different months (after ranges): "10, 27 січня. 4, 21 лютого 2026 року"
    """
    if not dates:
        return ""

    if len(dates) == 1:
        return _format_date_ukrainian(dates[0])

    # Sort dates
    sorted_dates = sorted(dates)

    # Find consecutive ranges
    ranges = []
    single_dates = []

    current_start = sorted_dates[0]
    current_end = sorted_dates[0]

    for d in sorted_dates[1:]:
        if d == current_end + timedelta(days=1):
            # Continue the range
            current_end = d
        else:
            # End current range/start new
            if current_start == current_end:
                single_dates.append(current_start)
            else:
                ranges.append((current_start, current_end))
            current_start = d
            current_end = d

    # Don't forget the last one
    if current_start == current_end:
        single_dates.append(current_start)
    else:
        ranges.append((current_start, current_end))

    # Group single dates by month
    single_by_month = {}
    for d in single_dates:
        key = (d.year, d.month)
        if key not in single_by_month:
            single_by_month[key] = []
        single_by_month[key].append(d)

    month_names_genitive = {
        1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
        5: "травня", 6: "червня", 7: "липня", 8: "серпня",
        9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
    }

    result_parts = []

    # Add single dates grouped by month (FIRST)
    if single_by_month:
        if result_parts:
            result_parts.append(" та ")

        sorted_months = sorted(single_by_month.keys())
        for i, (year, month) in enumerate(sorted_months):
            month_dates = sorted(single_by_month[(year, month)])
            days_str = ", ".join(str(d.day) for d in month_dates)

            if i > 0:
                if i == len(sorted_months) - 1:
                    result_parts.append(". ")
                else:
                    result_parts.append("; ")

            if len(month_dates) == 1:
                # Single day in month - use full format
                result_parts.append(_format_date_ukrainian(month_dates[0], include_year=(year != sorted_dates[0].year)))
            else:
                # Multiple days in same month
                include_year = (year != sorted_dates[0].year)
                if include_year:
                    result_parts.append(f"{days_str} {month_names_genitive[month]} {year} року")
                else:
                    result_parts.append(f"{days_str} {month_names_genitive[month]}")

    # Add ranges AFTER single dates
    for i, (r_start, r_end) in enumerate(ranges):
        if result_parts:
            result_parts.append(" та ")
        result_parts.append(_format_date_range_ukrainian(r_start, r_end))

    return "".join(result_parts)


class BuilderTab(QWidget):
    """
    Вкладка для створення заяв на відпустку з WYSIWYG редактором.

    Містить форму введення даних та інтерактивний редактор документа.
    """

    document_created = pyqtSignal()
    document_updated = pyqtSignal(int)  # document_id
    task_completed = pyqtSignal() # Emitted when an ephemeral task is done (print/generate)

    # Статичний змінний для передачі даних реактивації з EmployeeCardDialog
    _reactivation_data: dict | None = None

    def __init__(self, is_ephemeral: bool = False):
        """
        Ініалізує вкладку конструктора.
        
        Args:
            is_ephemeral: Якщо True, вкладка призначена для одноразової дії
                          і повинна сигналізувати про завершення.
        """
        super().__init__()
        self.is_ephemeral = is_ephemeral
        self._current_document_id: int | None = None
        self._current_status = DocumentStatus.DRAFT
        self._editor_state = WysiwygEditorState()
        self._parsed_dates: list[date] = []  # Список розпізнаних дат
        self._last_staff_count = 0  # Track staff count for dynamic updates
        self._staff_by_pib: dict[str, list] = {}  # Group staff by ПІБ
        self.booked_dates: set[date] = set()  # Заблоковані дати відпусток
        self.locked_info: list[dict] = []  # Інформація про заблоковані відпустки
        self._is_new_employee_mode: bool = False  # New employee mode flag
        self._is_subposition_mode: bool = False  # Subposition mode flag
        self._new_employee_data: dict | None = None  # Store new employee data
        self._setup_ui()
        self._setup_focus_handlers()

    def _on_js_console_message(self, level: int, message: str, line_number: int, source_id: str):
        """Handle JavaScript console messages."""
        # Map QWebEnginePage.JavaScriptConsoleMessageLevel to logging levels
        # 0: Info, 1: Warning, 2: Error
        log_level = logging.INFO
        prefix = "JS:INFO"
        
        if level == 0:
            log_level = logging.INFO
            prefix = "JS:INFO"
        elif level == 1:
            log_level = logging.WARNING
            prefix = "JS:WARN"
        elif level == 2:
            log_level = logging.ERROR
            prefix = "JS:ERROR"
            
        logger.log(log_level, f"{prefix} [{source_id}:{line_number}] {message}")
        
        # Also print to stdout for immediate debugging
        if log_level >= logging.WARNING:
            print(f"{prefix} [{source_id}:{line_number}] {message}")

    def showEvent(self, event):
        """Оновлює прев'ю при відображенні вкладки."""
        super().showEvent(event)
        # Update preview only if we have staff selected and no document loaded
        if not self._current_document_id and self.staff_input.count() > 0:
            self._update_preview()

    def new_document(self, staff_id: int):
        """
        Створює новий документ для співробітника.

        Args:
            staff_id: ID співробітника
        """
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        self._current_document_id = None
        self._clear_form()
        
        # Safety reset
        self._is_subposition_mode = False

        # Reset mode for standard form always when creating a document for existing staff
        self._is_new_employee_mode = False
        self._discover_document_templates()
        self._toggle_employment_mode()

        # Перевіряємо, чи це реактивація (співробітник може бути неактивним)
        is_reactivation = False
        reactivation_data = None
        if self._reactivation_data and self._reactivation_data.get('staff_id') == staff_id:
            is_reactivation = True
            reactivation_data = self._reactivation_data

        # Для реактивації завантажуємо неактивних співробітників
        if is_reactivation:
            with get_db_context() as db:
                staff = db.query(Staff).filter(Staff.id == staff_id).first()
                if staff:
                    # Додаємо неактивного співробітника до словника
                    pib = staff.pib_nom
                    if pib not in self._staff_by_pib:
                        self._staff_by_pib[pib] = []
                    if staff not in self._staff_by_pib[pib]:
                        self._staff_by_pib[pib].append(staff)

                    # Зберігаємо поточний вибір
                    current_pib = self.staff_input.currentData()

                    # Повністю оновлюємо dropdown
                    self.staff_input.clear()
                    for pib_name in sorted(self._staff_by_pib.keys()):
                        self.staff_input.addItem(pib_name, pib_name)

                    # Знаходимо та вибираємо потрібного співробітника
                    for i in range(self.staff_input.count()):
                        if self.staff_input.itemData(i) == pib:
                            self.staff_input.setCurrentIndex(i)
                            break

                    # Тепер вибираємо правильну позицію (конкретний staff_id)
                    if self.position_input.isVisible():
                        for i in range(self.position_input.count()):
                            if self.position_input.itemData(i) == staff_id:
                                self.position_input.setCurrentIndex(i)
                                break

        # Для звичайних документів або якщо реактивація не знайшла staff
        if not is_reactivation or not reactivation_data:
            self.select_staff_by_id(staff_id)

        # Встановлюємо правильний тип документа для реактивації
        if is_reactivation and reactivation_data:
            work_basis = reactivation_data.get('work_basis', '')

            # Встановлюємо тип документа на основі work_basis
            doc_type_map = {
                "contract": "Продовження (контракт)",
                "competitive": "Продовження (конкурс)",
                "statement": "Продовження (сумісництво)",
            }

            target_doc_type = doc_type_map.get(work_basis, "Продовження (контракт)")

            for i in range(self.doc_type_combo.count()):
                if target_doc_type in self.doc_type_combo.itemText(i):
                    self.doc_type_combo.setCurrentIndex(i)
                    break

            # Очищаємо дані реактивації після використання
            self._reactivation_data = None

        self._update_preview()

    def start_subposition_mode_for_staff(self, staff_id: int):
        """
        Активує режим сумісництва для вказаного співробітника.
        
        Args:
            staff_id: ID співробітника
        """
        # Optimize switch: avoid full new_document logic which triggers heavy DB calls
        self._current_document_id = None
        self._clear_form()
        
        # Select staff silently to avoid _on_staff_selected -> _load_locked_dates (DB hit)
        self.select_staff_by_id(staff_id, block_signals=True)
        
        # Enter subposition mode directly
        self._enter_subposition_mode()

    def set_vacation_dates(self, start_date: date, end_date: date):
        """
        Встановлює дати відпустки з графіку.

        Args:
            start_date: Початок відпустки
            end_date: Кінець відпустки
        """
        self._date_ranges = [(start_date, end_date)]
        self._parsed_dates = list(_date_range_iter(start_date, end_date))
        self._update_ranges_list()
        self._update_dates_info()
        self._update_preview()

    def load_document(self, document_id: int, staff_id: int):
        """
        Завантажує існуючий документ для редагування.

        Args:
            document_id: ID документа
            staff_id: ID співробітника
        """
        from backend.core.database import get_db_context
        from backend.models.document import Document
        from datetime import date

        self._current_document_id = document_id

        with get_db_context() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                return

            # Select staff
            self.select_staff_by_id(staff_id)

            # Load document type
            doc_type = doc.doc_type
            type_mapping = {
                "vacation_paid": "Оплачувана відпустка",
                "vacation_unpaid": "Відпустка без збереження",
                "term_extension": "Продовження контракту",
            }
            type_name = type_mapping.get(doc_type.value, "Оплачувана відпустка")

            # Find and set the combo box index
            for i in range(self.doc_type_combo.count()):
                if type_name in self.doc_type_combo.itemText(i):
                    self.doc_type_combo.setCurrentIndex(i)
                    break

            # Load date ranges from the document
            self._date_ranges = []
            self._parsed_dates = []

            if doc.date_start and doc.date_end:
                # Add the date range from the document
                self._date_ranges.append((doc.date_start, doc.date_end))
                self._parsed_dates.append(doc.date_start)
                if doc.date_end != doc.date_start:
                    # Add all dates in between
                    current = doc.date_start + timedelta(days=1)
                    while current <= doc.date_end:
                        self._parsed_dates.append(current)
                        current += timedelta(days=1)

            self._update_ranges_list()
            self._update_dates_info()

            # Load editor content if available
            if doc.editor_content:
                self._editor_state.blocks = json.loads(doc.editor_content).get('blocks', {})
                self._editor_state.custom_fields = json.loads(doc.editor_content).get('custom_fields', {})
                self._editor_state.formatting = json.loads(doc.editor_content).get('formatting', {})

            # Update preview
            self._update_preview()

    def _clear_form(self):
        """Очищує форму для нового документа."""
        self._date_ranges = []
        self._parsed_dates = []
        self._update_ranges_list()
        self._update_dates_info()

        # Clear editor state
        self._editor_state = WysiwygEditorState()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Toolbar для швидких дій
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Splitter для форми та прев'ю
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Ліва панель - форма
        form_panel = self._create_form_panel()
        splitter.addWidget(form_panel)

        # Права панель - WYSIWYG редактор
        preview_panel = self._create_wysiwyg_panel()
        splitter.addWidget(preview_panel)

        # Встановлюємо пропорції (30% форма, 70% редактор)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)

        layout.addWidget(splitter)

    def _create_toolbar(self) -> QToolBar:
        """Створює панель інструментів."""
        toolbar = QToolBar("Інструменти")
        toolbar.setMovable(False)

        # Зберегти чернетку (зберігає редаговане в базу)
        save_draft_btn = QPushButton("💾 Зберегти в базу")
        save_draft_btn.clicked.connect(self._save_draft)
        save_draft_btn.setToolTip("Зберігає поточний стан редактора в базу даних")
        toolbar.addWidget(save_draft_btn)

        toolbar.addSeparator()

        # Оновити прев'ю (перезавантажує з бази)
        refresh_btn = QPushButton("🔄 Оновити з бази")
        refresh_btn.clicked.connect(self._update_preview)
        refresh_btn.setToolTip("Перезавантажує документ з бази даних")
        toolbar.addWidget(refresh_btn)

        # Скинути зміни
        reset_btn = QPushButton("↶ Відновити оригінал")
        reset_btn.clicked.connect(self._reset_changes)
        reset_btn.setToolTip("Відновлює оригінальний стан документа")
        toolbar.addWidget(reset_btn)

        toolbar.addSeparator()

        # Друкувати
        print_btn = QPushButton("🖨 Друк")
        print_btn.clicked.connect(self._print_document)
        print_btn.setToolTip("Надіслати документ на принтер")
        toolbar.addWidget(print_btn)

        toolbar.addSeparator()

        # Головна кнопка - Створити/Оновити заяву
        self.generate_btn = QPushButton("📄 Створити заяву")
        self.generate_btn.clicked.connect(self._generate_document)
        self.generate_btn.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; font-weight: bold; padding: 8px 16px; }"
        )
        self.generate_btn.setToolTip("Створює або оновлює документ у базі та генерує DOCX файл")
        toolbar.addWidget(self.generate_btn)

        # Відкликати (тільки для існуючих документів)
        self.rollback_btn = QPushButton("↩ Відкликати")
        self.rollback_btn.clicked.connect(self._rollback_document)
        self.rollback_btn.setToolTip("Повернути документ в статус чернетки")
        self.rollback_btn.setVisible(False)
        toolbar.addWidget(self.rollback_btn)

        toolbar.addSeparator()

        # Статус документа
        self.status_label = QLabel("Статус: Чернетка")
        self.status_label.setStyleSheet("font-weight: bold; color: #3B82F6;")
        toolbar.addWidget(self.status_label)

        return toolbar

    def _create_form_panel(self) -> QWidget:
        """Створює панель форми."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Вибір співробітника
        self.staff_group = QGroupBox("👤 Співробітник")
        staff_layout = QFormLayout()

        self.staff_input = QComboBox()
        self.staff_input.currentIndexChanged.connect(self._on_staff_selected)
        staff_layout.addRow("ПІБ:", self.staff_input)

        # Position row - contains both plain text label (single position) and dropdown (multiple positions)
        self.position_label_text = QLabel()
        self.position_label_text.setVisible(False)
        staff_layout.addRow("Посада:", self.position_label_text)

        # Position selector (hidden by default, shown when employee has multiple positions)
        self.position_input = QComboBox()
        self.position_input.currentIndexChanged.connect(self._on_position_selected)
        self.position_input.setVisible(False)
        staff_layout.addRow("", self.position_input)  # Empty label since we have label above

        self.staff_info_label = QLabel()
        self.staff_info_label.setWordWrap(True)
        staff_layout.addRow(self.staff_info_label)

        self.subposition_btn = QPushButton("➕ Додати сумісництво")
        self.subposition_btn.clicked.connect(self._enter_subposition_mode)
        self.subposition_btn.setToolTip("Створити документ для сумісництва поточного співробітника")
        staff_layout.addRow(self.subposition_btn)

        # Load staff after creating the label
        self._load_staff()

        self.staff_group.setLayout(staff_layout)
        layout.addWidget(self.staff_group)

        # Новий співробітник (приховане за замовчуванням)
        self.new_employee_group = QGroupBox("Новий співробітник")
        new_employee_layout = QFormLayout()

        self.new_employee_pib = QLineEdit()
        self.new_employee_pib.setPlaceholderText("Прізвище Ім'я По батькові")
        new_employee_layout.addRow("ПІБ:", self.new_employee_pib)

        self.new_employee_position = QComboBox()
        # Store positions and their enum values
        self._position_values = [
            ("Професор", "professor"),
            ("Доцент", "associate_professor"),
            ("Старший викладач", "senior_lecturer"),
            ("Асистент", "lecturer"),
            ("Фахівець", "specialist"),
        ]
        # Store positions and their enum values
        self._all_position_values = [
            ("Професор", "professor"),
            ("Доцент", "associate_professor"),
            ("Старший викладач", "senior_lecturer"),
            ("Асистент", "lecturer"),
            ("Фахівець", "specialist"),
        ]
        self._position_values = list(self._all_position_values)
        for display, value in self._position_values:
            self.new_employee_position.addItem(display)
        self.new_employee_position.setCurrentIndex(3)  # Default to lecturer
        new_employee_layout.addRow("Посада:", self.new_employee_position)

        self.new_employee_rate = QComboBox()
        self.new_employee_rate.addItems(["0.25", "0.5", "0.75", "1.0"])
        self.new_employee_rate.setCurrentIndex(3)  # Default to 1.0
        new_employee_layout.addRow("Ставка:", self.new_employee_rate)

        self.emp_type_stack = QStackedWidget()
        
        self.new_employee_employment_type = QComboBox()
        self._all_employment_type_values = [
            ("Основне місце роботи", "main"),
            ("Зовнішній сумісник", "external"),
            ("Внутрішній сумісник", "internal"),
        ]
        self._employment_type_values = [] # Current active values
        for display, value in self._all_employment_type_values:
            self.new_employee_employment_type.addItem(display)
            self._employment_type_values.append(value)
        self.new_employee_employment_type.setCurrentIndex(0)  # Default to main
        
        self.emp_type_label = QLabel("Внутрішній сумісник")
        self.emp_type_label.setStyleSheet("font-weight: bold;")
        
        self.emp_type_stack.addWidget(self.new_employee_employment_type)
        self.emp_type_stack.addWidget(self.emp_type_label)
        
        new_employee_layout.addRow("Тип працевлаштування:", self.emp_type_stack)

        self.work_basis_stack = QStackedWidget()

        self.new_employee_work_basis = QComboBox()
        self._all_work_basis_values = [
            ("Контракт", "contract"),
            ("Конкурс", "competitive"),
            ("Заява", "statement"),
        ]
        self._work_basis_values = [] # Current active values
        for display, value in self._all_work_basis_values:
            self.new_employee_work_basis.addItem(display)
            self._work_basis_values.append(value)
            
        self.new_employee_work_basis.setCurrentIndex(0)  # Default to contract
        
        self.work_basis_label = QLabel("Заява")
        self.work_basis_label.setStyleSheet("font-weight: bold;")
        
        self.work_basis_stack.addWidget(self.new_employee_work_basis)
        self.work_basis_stack.addWidget(self.work_basis_label)
        
        new_employee_layout.addRow("Основа:", self.work_basis_stack)

        self.new_employee_term_start = QDateEdit()
        self.new_employee_term_start.setCalendarPopup(True)
        self.new_employee_term_start.setDate(QDate.currentDate())
        new_employee_layout.addRow("Дата початку:", self.new_employee_term_start)

        self.new_employee_term_end = QDateEdit()
        self.new_employee_term_end.setCalendarPopup(True)
        self.new_employee_term_end.setDate(QDate.currentDate().addMonths(12))
        new_employee_layout.addRow("Дата закінчення:", self.new_employee_term_end)

        self.new_employee_email = QLineEdit()
        self.new_employee_email.setPlaceholderText("email@example.com")
        new_employee_layout.addRow("Email:", self.new_employee_email)

        self.new_employee_phone = QLineEdit()
        self.new_employee_phone.setPlaceholderText("+380XXXXXXXXX")
        new_employee_layout.addRow("Телефон:", self.new_employee_phone)

        # Validation status label
        self.validation_status_label = QLabel("")
        self.validation_status_label.setStyleSheet("font-weight: bold; padding: 10px;")
        new_employee_layout.addRow("", self.validation_status_label)

        self.cancel_subposition_btn = QPushButton("❌ Скасувати сумісництво")
        self.cancel_subposition_btn.clicked.connect(self._exit_subposition_mode)
        self.cancel_subposition_btn.setVisible(False)
        new_employee_layout.addRow(self.cancel_subposition_btn)

        # Connect new employee form signals to update preview
        self.new_employee_pib.textChanged.connect(self._on_field_changed)
        self.new_employee_position.currentIndexChanged.connect(self._on_field_changed)
        self.new_employee_rate.currentIndexChanged.connect(self._on_field_changed)
        self.new_employee_employment_type.currentIndexChanged.connect(self._on_field_changed)
        self.new_employee_work_basis.currentIndexChanged.connect(self._on_field_changed)
        self.new_employee_term_start.dateChanged.connect(self._on_field_changed)
        self.new_employee_term_end.dateChanged.connect(self._on_field_changed)
        self.new_employee_email.textChanged.connect(self._on_field_changed)
        self.new_employee_phone.textChanged.connect(self._on_field_changed)

        self.new_employee_group.setLayout(new_employee_layout)
        self.new_employee_group.setVisible(False)
        layout.addWidget(self.new_employee_group)

        # Тип документа
        # ... (rest of the code)


        # Тип документа
        doc_group = QGroupBox("📋 Тип документа")
        doc_layout = QVBoxLayout()

        self.doc_type_combo = QComboBox()
        self.doc_type_combo.setStyleSheet("padding: 8px; font-size: 14px;")
        self._discover_document_templates()
        self.doc_type_combo.currentIndexChanged.connect(self._on_field_changed)

        doc_layout.addWidget(self.doc_type_combo)

        # Кнопка масової генерації
        self.bulk_mode_btn = QPushButton("📋 Масова генерація")
        self.bulk_mode_btn.setToolTip("Створити документи для кількох співробітників одночасно")
        self.bulk_mode_btn.clicked.connect(self._open_bulk_generator)
        doc_layout.addWidget(self.bulk_mode_btn)

        doc_group.setLayout(doc_layout)
        layout.addWidget(doc_group)

        # Дати - кнопка для відкриття діалогу вибору дати
        self.date_group = QGroupBox("📅 Вибір дат")
        date_layout = QVBoxLayout()

        # Інформація про вибрані дати
        self.dates_info_label = QLabel("Не вибрано")
        self.dates_info_label.setStyleSheet("color: #666; font-size: 12px; padding: 10px;")
        date_layout.addWidget(self.dates_info_label)

        # Поля для продовження контракту
        self.extension_dates_widget = QWidget()
        extension_dates_layout = QVBoxLayout(self.extension_dates_widget)
        extension_dates_layout.setContentsMargins(0, 10, 0, 10)

        # Попередження про період продовження
        self.extension_warning_label = QLabel()
        self.extension_warning_label.setStyleSheet("""
            background-color: #DBEAFE;
            color: #1E40AF;
            padding: 10px;
            border-radius: 6px;
            font-size: 12px;
        """)
        self.extension_warning_label.setWordWrap(True)
        self.extension_warning_label.setVisible(False)
        extension_dates_layout.addWidget(self.extension_warning_label)

        # Поле для дати закінчення попереднього контракту
        old_contract_layout = QHBoxLayout()
        old_contract_label = QLabel("Дата закінчення попереднього контракту:")
        old_contract_label.setFixedWidth(220)
        self.old_contract_date_edit = QDateEdit()
        self.old_contract_date_edit.setCalendarPopup(True)
        self.old_contract_date_edit.setDate(QDate.currentDate())
        self.old_contract_date_edit.dateChanged.connect(self._on_field_changed)
        old_contract_layout.addWidget(old_contract_label)
        old_contract_layout.addWidget(self.old_contract_date_edit)
        extension_dates_layout.addLayout(old_contract_layout)

        self.extension_dates_widget.setVisible(False)
        date_layout.addWidget(self.extension_dates_widget)

        # Попередження про 2-тижневий термін подання заяви
        self.timing_warning_label = QLabel()
        self.timing_warning_label.setStyleSheet("""
            background-color: #DBEAFE;
            color: #1E40AF;
            padding: 10px;
            border-radius: 6px;
            font-size: 12px;
        """)
        self.timing_warning_label.setWordWrap(True)
        self.timing_warning_label.setVisible(False)
        date_layout.addWidget(self.timing_warning_label)

        # Попередження про баланс відпустки
        self.balance_warning_label = QLabel()
        self.balance_warning_label.setStyleSheet("""
            background-color: #FEF3C7;
            color: #92400E;
            padding: 10px;
            border-radius: 6px;
            font-size: 12px;
        """)
        self.balance_warning_label.setWordWrap(True)
        self.balance_warning_label.setVisible(False)
        date_layout.addWidget(self.balance_warning_label)

        # Попередження про заблоковані дати відпусток
        self.locked_dates_warning_label = QLabel()
        self.locked_dates_warning_label.setStyleSheet("""
            background-color: #FEE2E2;
            color: #991B1B;
            padding: 10px;
            border-radius: 6px;
            font-size: 12px;
        """)
        self.locked_dates_warning_label.setWordWrap(True)
        self.locked_dates_warning_label.setTextFormat(Qt.TextFormat.RichText)
        self.locked_dates_warning_label.setVisible(False)
        date_layout.addWidget(self.locked_dates_warning_label)

        # Admin override для балансу (більш видимий)
        self.admin_override_group = QGroupBox("⚠️ Admin Override")
        self.admin_override_group.setStyleSheet("""
            QGroupBox {
                background-color: #FEF3C7;
                border: 2px solid #F59E0B;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }
        """)
        self.admin_override_group.setVisible(False)
        admin_override_layout = QVBoxLayout()
        self.admin_override_group.setLayout(admin_override_layout)

        self.admin_override_checkbox = QCheckBox("Дозволити створення відпустки (ігнорувати баланс)")
        self.admin_override_checkbox.setStyleSheet("font-size: 13px; color: #92400E;")
        admin_override_layout.addWidget(self.admin_override_checkbox)

        date_layout.addWidget(self.admin_override_group)

        # Попередження про додаткові позиції
        self.additional_position_widget = QWidget()
        self.additional_position_layout = QVBoxLayout(self.additional_position_widget)
        self.additional_position_layout.setContentsMargins(0, 5, 0, 5)

        self.additional_position_label = QLabel()
        self.additional_position_label.setStyleSheet("""
            background-color: #DBEAFE;
            color: #1E40AF;
            padding: 10px;
            border-radius: 6px;
            font-size: 12px;
        """)
        self.additional_position_label.setWordWrap(True)
        self.additional_position_layout.addWidget(self.additional_position_label)

        self.additional_position_btn = QPushButton("Автоматично створити для додаткової позиції")
        self.additional_position_btn.setStyleSheet("padding: 8px; font-size: 12px;")
        self.additional_position_btn.clicked.connect(self._generate_for_additional_position)
        self.additional_position_layout.addWidget(self.additional_position_btn)

        self.additional_position_widget.setVisible(False)
        date_layout.addWidget(self.additional_position_widget)

        # Список діапазонів
        self._date_ranges: list[tuple[date, date]] = []
        self._ranges_scroll = QScrollArea()
        self._ranges_scroll.setWidgetResizable(True)
        self._ranges_scroll.setMaximumHeight(150)
        self._ranges_widget = QWidget()
        self._ranges_layout = QVBoxLayout(self._ranges_widget)
        self._ranges_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._ranges_scroll.setWidget(self._ranges_widget)
        date_layout.addWidget(self._ranges_scroll)

        # Кнопки
        buttons_layout = QHBoxLayout()
        self.add_range_btn = QPushButton("Додати діапазон")
        self.add_range_btn.clicked.connect(self._add_date_range)
        buttons_layout.addWidget(self.add_range_btn)

        self.auto_range_btn = QPushButton("Автоматично")
        self.auto_range_btn.clicked.connect(self._open_auto_date_dialog)
        buttons_layout.addWidget(self.auto_range_btn)

        self.clear_ranges_btn = QPushButton("Очистити все")
        self.clear_ranges_btn.clicked.connect(self._clear_all_ranges)
        buttons_layout.addWidget(self.clear_ranges_btn)

        date_layout.addLayout(buttons_layout)

        self.date_group.setLayout(date_layout)
        layout.addWidget(self.date_group)

        # Оплата - завжди автоматична (приховано)
        self._payment_is_automatic = True

        layout.addStretch()

        return panel

    def _create_wysiwyg_panel(self) -> QWidget:
        """Створює панель WYSIWYG редактора з підтримкою вкладок."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Заголовок
        header = QLabel("📝 Візуальний редактор документа")
        header.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(header)

        # Tab widget for multiple documents
        self.preview_tabs = QTabWidget()
        self.preview_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                background: white;
            }
            QTabBar::tab {
                padding: 8px 16px;
                background: #f0f0f0;
                border: 1px solid #ccc;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: white;
                font-weight: bold;
            }
        """)

        # Create main web view (first tab)
        self.web_view = QWebEngineView()
        self.web_view.setMinimumSize(500, 400)
        self.web_view.setSizePolicy(
            self.web_view.sizePolicy().Policy.Expanding,
            self.web_view.sizePolicy().Policy.Expanding
        )

        # Налаштування WebChannel для взаємодії з JavaScript
        self.web_channel = QWebChannel()
        self.wysiwyg_bridge = WysiwygBridge(self)

        # Підключаємо сигнали
        self.wysiwyg_bridge.content_changed.connect(self._on_editor_content_changed)
        self.wysiwyg_bridge.signatories_changed.connect(self._on_signatories_changed)

        # Реєструємо міст в каналі
        self.web_channel.registerObject("pybridge", self.wysiwyg_bridge)
        self.web_view.page().setWebChannel(self.web_channel)
        
        # Connect console logging
        self.web_view.page().javaScriptConsoleMessage = self._on_js_console_message

        # Inject QWebChannel initialization script
        channel_init_script = """
            (function() {
                if (typeof QWebChannel !== 'undefined') {
                    new QWebChannel(window.qt.webChannelTransport, function(channel) {
                        window.pybridge = channel.objects.pybridge;
                        window.qwebchannelReady = true;
                        console.log('QWebChannel initialized from Python');
                    });
                }
            })();
        """
        self.web_view.page().runJavaScript(channel_init_script)

        # Add main tab
        self.preview_tabs.addTab(self.web_view, "Основна позиція")

        # Storage for additional document previews
        self._additional_previews: dict[int, tuple[QWebEngineView, QWebChannel, WysiwygBridge]] = {}

        layout.addWidget(self.preview_tabs)

        # Інструкція
        help_label = QLabel(
            "💡 Підказка: Клікніть на будь-який блок тексту для редагування. "
            "Використовуйте панель інструментів для форматування."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        layout.addWidget(help_label)

        return panel

    def _create_preview_tab(self, staff_name: str, position: str, is_internal: bool = False) -> tuple[QWebEngineView, WysiwygBridge]:
        """Створює нову вкладку для попереднього перегляду додаткової позиції."""
        # Create web view
        web_view = QWebEngineView()
        web_view.setMinimumSize(500, 400)
        web_view.setSizePolicy(
            web_view.sizePolicy().Policy.Expanding,
            web_view.sizePolicy().Policy.Expanding
        )

        # Create bridge
        web_channel = QWebChannel()
        bridge = WysiwygBridge(self)

        # Connect signals
        bridge.content_changed.connect(self._on_editor_content_changed)
        bridge.signatories_changed.connect(self._on_signatories_changed)

        # Register bridge
        web_channel.registerObject("pybridge", bridge)
        web_view.page().setWebChannel(web_channel)

        # Connect console logging
        web_view.page().javaScriptConsoleMessage = self._on_js_console_message

        # Create tab name (translate position enum to Ukrainian label)
        position_label = get_position_label(position)
        tab_name = f"{position_label}"
        if is_internal:
            tab_name = f"внутрішній сумісник ({position})"

        # Add tab
        index = self.preview_tabs.addTab(web_view, tab_name)
        self.preview_tabs.setCurrentIndex(index)

        return web_view, bridge

    def _remove_additional_preview(self, staff_id: int):
        """Видаляє вкладку попереднього перегляду для додаткової позиції."""
        if staff_id in self._additional_previews:
            web_view, channel, bridge = self._additional_previews[staff_id]
            index = self.preview_tabs.indexOf(web_view)
            if index > 0:  # Don't remove the first tab
                self.preview_tabs.removeTab(index)
            del self._additional_previews[staff_id]

    def _load_staff(self):
        """Завантажує список співробітників (унікальні ПІБ з усіма позиціями)."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            staff_list = (
                db.query(Staff)
                .filter(Staff.is_active == True)
                .order_by(Staff.pib_nom, Staff.rate.desc())
                .all()
            )

            # Group staff by ПІБ and collect all positions
            self._staff_by_pib = {}  # pib -> list of staff records
            for staff in staff_list:
                if staff.pib_nom not in self._staff_by_pib:
                    self._staff_by_pib[staff.pib_nom] = []
                self._staff_by_pib[staff.pib_nom].append(staff)

            # Populate dropdown with unique ПІБ
            self.staff_input.clear()
            for pib in sorted(self._staff_by_pib.keys()):
                self.staff_input.addItem(pib, pib)  # Store ПІБ as data

        # Update staff count for dynamic change detection
        self._last_staff_count = len(staff_list)

        # Select first staff if available and no current selection
        if self.staff_input.count() > 0 and self.staff_input.currentIndex() == -1:
            self.staff_input.setCurrentIndex(0)

    def _on_staff_selected(self, index: int):
        """Обробляє вибір співробітника."""
        pib = self.staff_input.currentData()
        if not pib or not hasattr(self, '_staff_by_pib') or pib not in self._staff_by_pib:
            return

        positions = self._staff_by_pib[pib]

        # Populate position selector
        self.position_input.clear()

        # Sort by rate descending (main position first)
        positions_sorted = sorted(positions, key=lambda s: float(s.rate), reverse=True)

        for staff in positions_sorted:
            # Format: "Посада (Ставка)" - use Ukrainian label
            position_label = get_position_label(staff.position)
            display_text = f"{position_label} ({staff.rate})"
            self.position_input.addItem(display_text, staff.id)

        # Show position selector if multiple positions, otherwise show plain text
        if len(positions_sorted) > 1:
            # Multiple positions: show dropdown, hide plain text
            self.position_input.setVisible(True)
            self.position_label_text.setVisible(False)
            # Default to main position (1.0) or first in list
            for i, staff in enumerate(positions_sorted):
                if staff.rate == Decimal("1.00"):
                    self.position_input.setCurrentIndex(i)
                    break
        else:
            # Single position: show plain text, hide dropdown
            self.position_input.setVisible(False)
            self.position_label_text.setVisible(True)
            # Show position as plain text
            single_staff = positions_sorted[0]
            position_label = get_position_label(single_staff.position)
            self.position_label_text.setText(f"{position_label} ({single_staff.rate})")

        self._on_field_changed()
        self._update_staff_info()
        self._load_locked_dates()

    def _on_position_selected(self, index: int):
        """Обробляє вибір позиції."""
        self._on_field_changed()
        self._update_staff_info()
        self._load_locked_dates()

    def _get_selected_staff(self):
        """Повертає обраного співробітника або None."""
        pib = self.staff_input.currentData()
        if not pib:
            return None

        if pib not in self._staff_by_pib:
            return None

        positions = self._staff_by_pib[pib]

        # If only one position, return it
        if len(positions) == 1:
            return positions[0]

        # Multiple positions - check if selector is visible and has selection
        if not self.position_input.isVisible():
            # Return main position (1.0) or first
            for staff in positions:
                if staff.rate == Decimal("1.00"):
                    return staff
            return positions[0]

        # Get selected position ID
        position_id = self.position_input.currentData()
        if position_id < 0:
            # No valid selection, return main position
            for staff in positions:
                if staff.rate == Decimal("1.00"):
                    return staff
            return positions[0]

        # Find staff by ID
        for staff in positions:
            if staff.id == position_id:
                return staff

        return positions[0]

    def _setup_focus_handlers(self):
        """Налаштовує обробники фокусу для динамічного оновлення."""
        from PyQt6.QtCore import QTimer
        # Check for staff changes when widget gains focus
        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(1000)  # Check every second when visible
        self._focus_timer.timeout.connect(self._check_staff_changes)
        self._focus_timer.start()

    def _check_staff_changes(self):
        """Перевіряє зміни в списку співробітників і оновлює якщо потрібно."""
        if not self.isVisible():
            return

        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            current_count = db.query(Staff).filter(Staff.is_active == True).count()
            if current_count != self._last_staff_count:
                self._load_staff()

    def refresh_staff(self):
        """Оновлює список співробітників (публічний метод для виклику ззовні)."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            self._last_staff_count = db.query(Staff).filter(Staff.is_active == True).count()
        self._load_staff()

    def select_staff_by_id(self, staff_id: int, block_signals: bool = False):
        """
        Вибирає співробітника за ID у випадаючому списку.

        Args:
            staff_id: ID співробітника
            block_signals: Чи блокувати сигнали (для оптимізації)
        """
        if not hasattr(self, 'staff_input'):
            return

        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff:
                return

            # Find ПІБ in dropdown
            pib = staff.pib_nom
            
            if block_signals:
                self.staff_input.blockSignals(True)
                
            for i in range(self.staff_input.count()):
                if self.staff_input.itemData(i) == pib:
                    self.staff_input.setCurrentIndex(i)
                    break
            
            if block_signals:
                self.staff_input.blockSignals(False)
                # Skip position selection and info update if signals were blocked
                return

            # Select the correct position
            if self.position_input.isVisible():
                for i in range(self.position_input.count()):
                    if self.position_input.itemData(i) == staff_id:
                        self.position_input.setCurrentIndex(i)
                        break

        self._update_staff_info()

    def _update_staff_info(self):
        """Оновлює інформацію про співробітника."""
        if not hasattr(self, 'staff_input') or not hasattr(self, 'staff_info_label'):
            return

        staff = self._get_selected_staff()
        if staff:
            # Перевіряємо термін контракту
            from datetime import timedelta
            days_until_expiry = (staff.term_end - date.today()).days

            # Check if employee has multiple positions
            pib = self.staff_input.currentData()
            positions_count = len(self._staff_by_pib.get(pib, [])) if pib else 1
            position_info = f" ({positions_count} посад)" if positions_count > 1 else ""

            info_text = (
                f"Ставка: {staff.rate}{position_info}\n"
                f"Баланс: {staff.vacation_balance} днів\n"
                f"Тип: {self._get_employment_type_label(staff.employment_type.value)}\n"
                f"Контракт до: {staff.term_end.strftime('%d.%m.%Y')}"
            )

            # Додаємо попередження про закінчення контракту
            if days_until_expiry <= 30:
                info_text += f"\n⚠️ Контракт закінчується через {days_until_expiry} днів!"

            self.staff_info_label.setText(info_text)

            # Оновлюємо попередження про контракт у секції дат
            self._check_vacation_dates_against_contract()

    def _load_locked_dates(self):
        """Завантажує заблоковані дати відпусток для обраного співробітника."""
        staff = self._get_selected_staff()
        if not staff:
            self.booked_dates = set()
            self.locked_info = []
            return

        from backend.models.document import Document
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        booked_dates = set()
        locked_info = []

        with get_db_context() as db:
            # Reload staff with documents relationship
            staff = db.query(Staff).filter(Staff.id == staff.id).first()
            if staff:
                for doc in staff.documents:
                    # Блокуємо всі активні статуси крім чернетки
                    active_statuses = (
                        'signed_by_applicant', 'approved_by_dispatcher', 'signed_dep_head',
                        'agreed', 'signed_rector', 'scanned', 'processed'
                    )
                    if doc.status in active_statuses:
                        current = doc.date_start
                        while current <= doc.date_end:
                            booked_dates.add(current)
                            current += timedelta(days=1)
                        # Формуємо статус для відображення
                        status_map = {
                            'signed_by_applicant': ('підписав заявник', '✍️'),
                            'approved_by_dispatcher': ('погоджено диспетчером', '👨‍💼'),
                            'signed_dep_head': ('підписано зав. кафедри', '📋'),
                            'agreed': ('погоджено', '🤝'),
                            'signed_rector': ('підписано ректором', '🎓'),
                            'scanned': ('відскановано', '📷'),
                            'processed': ('в табелі', '📁'),
                        }
                        status_text, status_icon = status_map.get(doc.status, ('оброблено', '📋'))
                        locked_info.append({
                            'dates': f"{doc.date_start.strftime('%d.%m')} - {doc.date_end.strftime('%d.%m')}",
                            'status_text': status_text,
                            'status_icon': status_icon,
                            'doc_id': doc.id
                        })

        self.booked_dates = booked_dates
        self.locked_info = locked_info

    def _get_employment_type_label(self, value: str) -> str:
        """Повертає українську назву типу працевлаштування."""
        labels = {
            "main": "Основне місце роботи",
            "internal": "Внутрішній сумісник",
            "external": "Зовнішній сумісник",
        }
        return labels.get(value, value)

    def _discover_document_templates(self):
        """
        Discover document templates from the templates/documents directory.

        Populates the document type combo box with available templates.
        Templates are identified by filename (without .html extension).
        """
        self.doc_type_combo.clear()
        self._doc_type_map = {}  # Maps display text to doc type value

        base_path = Path(__file__).parent.parent.parent
        templates_dir = base_path / "desktop" / "templates" / "documents"

        if not templates_dir.exists():
            print(f"WARNING: Templates directory not found: {templates_dir}")
            return

        # Get current staff rate to conditionally show templates
        staff = self._get_selected_staff()
        staff_rate = float(staff.rate) if staff and staff.rate else 0
        is_external = staff_rate <= 1.0  # Internal совместитель has rate > 1.0

        # Template display name mappings
        template_names = {
            "vacation_paid": "Відпустка оплачувана",
            "vacation_unpaid": "Відпустка без збереження",
            "term_extension": "Продовження контракту",
            # Оплачувані відпустки
            "vacation_main": "Основна відпустка (В)",
            "vacation_additional": "Додаткова відпустка (Д)",
            "vacation_chornobyl": "Відпустка чорнобильцям (Ч)",
            "vacation_creative": "Творча відпустка (ТВ)",
            "vacation_study": "Навчальна відпустка (Н)",
            "vacation_children": "Відпустка з дітьми (ДО)",
            "vacation_maternity": "Вагітність/пологи (ВП)",
            "vacation_childcare": "Догляд за дитиною (ДД)",
            # Відпустки без збереження зарплати
            "vacation_unpaid_study": "Навчальна без збереження (НБ)",
            "vacation_unpaid_mandatory": "Обов'язкова без збереження (ДБ)",
            "vacation_unpaid_agreement": "За згодою сторін (НА)",
            "vacation_unpaid_other": "Інша без збереження (БЗ)",
            # Продовження контракту
            "term_extension_contract": "Продовження (контракт)",
            "term_extension_competition": "Продовження (конкурс)",
            "term_extension_pdf": "Продовження (сумісництво)",
            # Прийом на роботу
            "employment_contract": "Прийом (контракт)",
            "employment_competition": "Прийом (конкурс)",
            "employment_pdf": "Прийом (PDF)",
        }



        # Templates that require rate > 1.0 (external совместительство)
        requires_external = {"term_extension_pdf"}

        # Find all HTML templates
        for template_file in sorted(templates_dir.glob("*.html")):
            template_name = template_file.stem  # filename without extension

            # Skip non-document templates (like wysiwyg_editor.html)
            if template_name in ["wysiwyg_editor"]:
                continue
            
            # -----------------------------------------------------------
            # SUBPOSITION MODE: Strict filtering
            # -----------------------------------------------------------
            if getattr(self, '_is_subposition_mode', False):
                # In subposition mode, ONLY allow employment_pdf
                if template_name != "employment_pdf":
                    continue
            # -----------------------------------------------------------

            # Skip templates that require rate > 1.0 for internal employees
            if template_name in requires_external and not is_external:
                continue

            # Skip templates that require rate > 1.0 for internal employees
            if template_name in requires_external and not is_external:
                continue

            # Skip employment templates if NOT in new employee mode (default mode)
            is_employment_template = template_name.startswith("employment_")
            if not self._is_new_employee_mode and is_employment_template:
                continue

            # Skip NON-employment templates if IN new employee mode
            if self._is_new_employee_mode and not is_employment_template:
                continue

            # Get display name
            display_name = template_names.get(template_name, template_name.replace("_", " ").title())

            self.doc_type_combo.addItem(display_name)
            self._doc_type_map[display_name] = template_name

        # Set default selection to "Відпустка оплачувана" (paid vacation)
        for i in range(self.doc_type_combo.count()):
            if "оплачувана" in self.doc_type_combo.itemText(i).lower():
                self.doc_type_combo.setCurrentIndex(i)
                break
        else:
            # Fallback to first item if not found
            if self.doc_type_combo.count() > 0:
                self.doc_type_combo.setCurrentIndex(0)

    def _get_doc_type(self) -> DocumentType:
        """Повертає обраний тип документа."""
        if not hasattr(self, 'doc_type_combo') or self.doc_type_combo.count() == 0:
            return DocumentType.VACATION_PAID

        current_text = self.doc_type_combo.currentText()
        template_name = self._doc_type_map.get(current_text, "")

        # Map template name to DocumentType
        type_mapping = {
            "vacation_paid": DocumentType.VACATION_PAID,
            "vacation_unpaid": DocumentType.VACATION_UNPAID,
            "term_extension": DocumentType.TERM_EXTENSION,
            # Оплачувані відпустки
            "vacation_main": DocumentType.VACATION_MAIN,
            "vacation_additional": DocumentType.VACATION_ADDITIONAL,
            "vacation_chornobyl": DocumentType.VACATION_CHORNOBYL,
            "vacation_creative": DocumentType.VACATION_CREATIVE,
            "vacation_study": DocumentType.VACATION_STUDY,
            "vacation_children": DocumentType.VACATION_CHILDREN,
            "vacation_maternity": DocumentType.VACATION_MATERNITY,
            "vacation_childcare": DocumentType.VACATION_CHILDCARE,
            # Відпустки без збереження зарплати
            "vacation_unpaid_study": DocumentType.VACATION_UNPAID_STUDY,
            "vacation_unpaid_mandatory": DocumentType.VACATION_UNPAID_MANDATORY,
            "vacation_unpaid_agreement": DocumentType.VACATION_UNPAID_AGREEMENT,
            "vacation_unpaid_other": DocumentType.VACATION_UNPAID_OTHER,
            # Продовження контракту
            "term_extension_contract": DocumentType.TERM_EXTENSION_CONTRACT,
            "term_extension_competition": DocumentType.TERM_EXTENSION_COMPETITION,
            "term_extension_pdf": DocumentType.TERM_EXTENSION_PDF,
            # Прийом на роботу
            "employment_contract": DocumentType.EMPLOYMENT_CONTRACT,
            "employment_competition": DocumentType.EMPLOYMENT_COMPETITION,
            "employment_pdf": DocumentType.EMPLOYMENT_PDF,
        }

        return type_mapping.get(template_name, DocumentType.VACATION_PAID)

    def _is_employment_doc_type(self) -> bool:
        """Перевіряє, чи обраний тип документа є прийомом на роботу."""
        doc_type = self._get_doc_type()
        return doc_type.value.startswith("employment_")

    def _get_new_employee_data(self) -> dict | None:
        """Отримує дані нового співробітника з форми."""
        # Always try to get data from form, regardless of mode
        pib = self.new_employee_pib.text().strip()

        # Get position value from the mapped list
        position_index = self.new_employee_position.currentIndex()
        if hasattr(self, '_position_values') and 0 <= position_index < len(self._position_values):
            # _position_values contains tuples (Display Label, Enum Value)
            # We want the Enum Value at index 1
            position_value = self._position_values[position_index][1]
        else:
            position_value = "lecturer"

        # Get employment type value
        employment_type_index = self.new_employee_employment_type.currentIndex()
        employment_type_value = self._employment_type_values[employment_type_index] if hasattr(self, '_employment_type_values') else "main"

        # Get work basis value
        work_basis_index = self.new_employee_work_basis.currentIndex()
        work_basis_value = self._work_basis_values[work_basis_index] if hasattr(self, '_work_basis_values') else "contract"

        # Get formatted date strings
        term_start = self.new_employee_term_start.date().toPyDate()
        term_end = self.new_employee_term_end.date().toPyDate()

        return {
            "pib_nom": pib,
            "position": position_value,
            "position_label": self.new_employee_position.currentText(),
            "rate": float(self.new_employee_rate.currentText()),
            "employment_type": employment_type_value,
            "work_basis": work_basis_value,
            "term_start": term_start.strftime("%d.%m.%Y"),
            "term_end": term_end.strftime("%d.%m.%Y"),
            "email": self.new_employee_email.text().strip() or None,
            "phone": self.new_employee_phone.text().strip() or None,
        }

    def _on_field_changed(self):
        """Обробляє зміну будь-якого поля."""
        import re

        # Check if document type changed and handle dates accordingly
        if hasattr(self, '_last_doc_type'):
            current_doc_type = self._get_doc_type()
            if self._last_doc_type != current_doc_type:
                # Document type changed - clear dates if switching from term extension
                if self._last_doc_type == DocumentType.TERM_EXTENSION:
                    self._date_ranges = []
                    self._parsed_dates = []

                # Toggle between staff selector and new employee form
                self._toggle_employment_mode()
            self._last_doc_type = current_doc_type
        else:
            # First time - initialize
            self._last_doc_type = self._get_doc_type()
            # Check initial employment mode
            self._toggle_employment_mode()

        # Update ranges list and dates info FIRST (before any checks that depend on dates)
        if hasattr(self, '_ranges_layout'):
            self._update_ranges_list()
            self._update_dates_info()

        if hasattr(self, 'staff_info_label'):
            self._update_staff_info()

        # Validate new employee fields if in employment mode
        is_employment = self._is_employment_doc_type()
        if is_employment and hasattr(self, 'validation_status_label'):
            employee_data = self._get_new_employee_data()
            pib = employee_data.get("pib_nom", "").strip()
            validation_errors = []

            # PIB validation (same as StaffDialog)
            if not pib:
                validation_errors.append("Введіть ПІБ співробітника")
            else:
                pib_parts = pib.split()
                if len(pib_parts) != 3:
                    validation_errors.append("ПІБ має бути у форматі: Прізвище Ім'я По батькові")
                else:
                    # Check each part starts with uppercase Ukrainian letter
                    ukrainian_pattern = r"^[А-ЩЬЮЯЇІЄҐ][а-щьюяїієҐ\-]+$"
                    for part in pib_parts:
                        if not re.match(ukrainian_pattern, part):
                            validation_errors.append(f"Некоректна частина ПІБ: {part}")
                            break

            # Date validation
            if employee_data.get("term_end") <= employee_data.get("term_start"):
                validation_errors.append("Дата закінчення контракту має бути пізніше за дату початку")

            # Show validation status
            if validation_errors:
                self.validation_status_label.setText("⚠️ " + "; ".join(validation_errors))
                self.validation_status_label.setStyleSheet("color: #B91C1C; font-weight: bold;")
            else:
                self.validation_status_label.setText("✓ Дані заповнено коректно")
                self.validation_status_label.setStyleSheet("color: #10B981; font-weight: bold;")

        # Оновлюємо прев'ю при зміні
        if hasattr(self, 'web_view'):
            self._update_preview()
        # Перевіряємо дотримання термінів подання заяви
        if hasattr(self, 'timing_warning_label'):
            self._check_application_timing()

    def _toggle_employment_mode(self):
        """Перемикає між режимом вибору співробітника та режимом нового співробітника."""
        if not hasattr(self, 'new_employee_group'):
            return

        is_employment = self._is_employment_doc_type()
        
        # In subposition mode, force employment UI
        if self._is_subposition_mode:
            is_employment = True
            
        self._is_new_employee_mode = is_employment

        # Show/hide appropriate groups
        if hasattr(self, 'staff_group'):
            self.staff_group.setVisible(not is_employment)
        self.new_employee_group.setVisible(is_employment)

        # Update date group visibility for employment documents
        if hasattr(self, 'date_group'):
            self.date_group.setVisible(not is_employment)

        # Hide extension dates widget for employment documents
        if hasattr(self, 'extension_dates_widget'):
            self.extension_dates_widget.setVisible(False)

        # Hide admin override for employment documents
        if hasattr(self, 'admin_override_group'):
            self.admin_override_group.setVisible(False)

        # Update preview
        if hasattr(self, 'web_view'):
            self._update_preview()

    def _enter_subposition_mode(self, *args):
        """Входить в режим створення сумісництва для поточного співробітника."""
        self._is_subposition_mode = True
        self._is_new_employee_mode = True

        # Prepopulate data from current staff selection
        current_staff_name = self.staff_input.currentText().strip()
        self.new_employee_pib.setText(current_staff_name)

        # Update position list (exclude specialist)
        self.new_employee_position.clear()
        self._position_values = [
            p for p in self._all_position_values
            if p[1] != "specialist"
        ]
        for display, value in self._position_values:
            self.new_employee_position.addItem(display)
        
        # Set default position (Lecturer/Assistant)
        target_default = "lecturer"
        for i, (display, value) in enumerate(self._position_values):
            if value == target_default:
                self.new_employee_position.setCurrentIndex(i)
                break

        # Enable custom rate input
        self.new_employee_rate.setEditable(True)
        self.new_employee_rate.setEditText("0.5")

        # Restrict Employment Type to Internal Subposition
        self.new_employee_employment_type.clear()
        self._employment_type_values = [
            ("Внутрішній сумісник", "internal")
        ]
        # We need to flatten this to just values for internal logic usage if needed, but currently UI uses index.
        # However, new_employee_flow uses self._employment_type_values[index]
        # So we must update self._employment_type_values to be a list of keys matching the combo box items.
        temp_values = []
        for display, value in self._employment_type_values:
            self.new_employee_employment_type.addItem(display)
            temp_values.append(value)
        self._employment_type_values = temp_values
        self.new_employee_employment_type.setCurrentIndex(0)
        
        # Switch to Label View
        self.emp_type_stack.setCurrentIndex(1)

        # Restrict Work Basis to Statement
        self.new_employee_work_basis.clear()
        self._work_basis_values_tuple = [ # distinct name to avoid confusion
            ("Заява", "statement")
        ]
        temp_basis_values = []
        for display, value in self._work_basis_values_tuple:
            self.new_employee_work_basis.addItem(display)
            temp_basis_values.append(value)
        self._work_basis_values = temp_basis_values
        self.new_employee_work_basis.setCurrentIndex(0)
        
        # Switch to Label View
        self.work_basis_stack.setCurrentIndex(1)
        
        # Rediscover templates to strictly filter for employment_pdf
        self._discover_document_templates()
        
        # Force select the only available item (should be employment_pdf)
        if self.doc_type_combo.count() > 0:
            self.doc_type_combo.setCurrentIndex(0)
        
        self.doc_type_combo.setVisible(True) # Show it, but it will only have 1 option
        self.cancel_subposition_btn.setVisible(True)

        self._toggle_employment_mode()

    def _exit_subposition_mode(self):
        """Виходить з режиму створення сумісництва."""
        self._is_subposition_mode = False
        # Let toggle logic handle _is_new_employee_mode based on doc selection
        
        # Restore positions
        self.new_employee_position.clear()
        self._position_values = list(self._all_position_values)
        for display, value in self._position_values:
            self.new_employee_position.addItem(display)
        
        # Restore default index
        self.new_employee_position.setCurrentIndex(3)

        # Disable rate editing
        self.new_employee_rate.setEditable(False)
        self.new_employee_rate.setCurrentIndex(3) # Default 1.0

        # Restore Employment Type
        self.new_employee_employment_type.clear()
        self._employment_type_values = []
        for display, value in self._all_employment_type_values:
            self.new_employee_employment_type.addItem(display)
            self._employment_type_values.append(value)
        self.new_employee_employment_type.setCurrentIndex(0)
        self.emp_type_stack.setCurrentIndex(0) # Switch to Combo View

        # Restore Work Basis
        self.new_employee_work_basis.clear()
        self._work_basis_values = []
        for display, value in self._all_work_basis_values:
            self.new_employee_work_basis.addItem(display)
            self._work_basis_values.append(value)
        self.new_employee_work_basis.setCurrentIndex(0)
        self.work_basis_stack.setCurrentIndex(0) # Switch to Combo View

        # Restore templates
        self._discover_document_templates()

        # Show doc selector
        self.doc_type_combo.setVisible(True)
        # Reset doc type to default (Vacation Paid usually 0)
        self.doc_type_combo.setCurrentIndex(0)
        
        self.cancel_subposition_btn.setVisible(False)
        self._toggle_employment_mode()

    def _update_payment_period(self):
        """Період оплати завжди автоматичний (застарілий метод)."""
        # Оплата завжди автоматична - більше не потрібно
        pass

    def _get_document_template_path(self, doc_type: DocumentType) -> Path:
        """
        Повертає шлях до шаблону документа для WYSIWYG редактора.

        Args:
            doc_type: Тип документа

        Returns:
            Path до файлу шаблону
        """
        base_path = Path(__file__).parent.parent.parent
        templates_dir = base_path / "desktop" / "templates"
        document_template = templates_dir / "documents" / f"{doc_type.value}.html"

        if not document_template.exists():
            # Log available templates for debugging
            documents_dir = templates_dir / "documents"
            if documents_dir.exists():
                available = list(documents_dir.glob("*.html"))
                available_names = [f.stem for f in available]
            else:
                available_names = []

            raise FileNotFoundError(
                f"Template not found for document type '{doc_type.value}'. "
                f"Expected: {document_template}\n"
                f"Available templates: {available_names}"
            )

        return document_template

    def _update_preview(self):
        """Оновлює прев'ю документа."""
        try:
            # Отримуємо дані форми
            context = self._get_context()

            # Використовуємо абсолютний шлях до шаблонів
            base_path = Path(__file__).parent.parent.parent
            templates_dir = base_path / "desktop" / "templates"

            # Set up Jinja2 environment with both template directories
            env = Environment(
                loader=FileSystemLoader([
                    str(templates_dir),                    # For wysiwyg_editor.html
                    str(templates_dir / "documents")       # For document templates
                ]),
                auto_reload=True  # Always reload templates from disk
            )

            # Load document-specific template
            doc_type = self._get_doc_type()
            document_template = env.get_template(f"documents/{doc_type.value}.html")
            document_content = document_template.render(**context)

            # Add document content to context
            context["document_content"] = document_content

            # Load main editor shell
            editor_template = env.get_template("wysiwyg_editor.html")
            html = editor_template.render(**context)

            # Встановлюємо HTML з базовим URL для завантаження CSS/JS
            base_url = QUrl.fromLocalFile(str(templates_dir) + "/")
            self.web_view.setHtml(html, base_url)

            # Встановлюємо статус з затримкою, щоб JavaScript встиг завантажитися
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self.wysiwyg_bridge.set_document_status(
                self.web_view,
                self._current_status.value,
                self._get_status_label()
            ))

            # Оновлюємо auto-fields (formatted_dates, days_count)
            if context.get("formatted_dates"):
                QTimer.singleShot(600, lambda: self.wysiwyg_bridge.update_field(
                    self.web_view, "formatted_dates", context["formatted_dates"]
                ))
            if context.get("days_count"):
                QTimer.singleShot(600, lambda: self.wysiwyg_bridge.update_field(
                    self.web_view, "days_count", context["days_count"]
                ))

            # Встановлюємо попередньо визначених погоджувачів (для кнопки + Погоджувач)
            if context.get("signatories"):
                QTimer.singleShot(700, lambda: self.wysiwyg_bridge.set_predefined_signatories(
                    self.web_view,
                    context["signatories"]
                ))

            # Експортуємо початковий контент
            QTimer.singleShot(1200, lambda: self.wysiwyg_bridge.export_content(self.web_view))

        except Exception as e:
            print(f"Error updating preview: {e}")
            QMessageBox.warning(self, "Помилка", f"Не вдалося оновити прев'ю: {e}")

    def _format_signatory_name(self, name: str) -> str:
        """
        Форматує ім'я підписанта для розділу "Погоджено".

        Формат: "Ім'я ПРІЗВИЩЕ" (тільки ім'я та прізвище, без по батькові)
        Приклад: "Василь САВИК", "Сергій ГАВРИК"

        Args:
            name: ПІБ у називному відмінку (наприклад, "Савик Василь Миколайович")

        Returns:
            Відформатоване ПІБ для підпису
        """
        parts = name.split()
        if len(parts) >= 3:
            # "Савик Василь Миколайович" - Surname First Middle
            # Return only "Василь САВИК" (first name + last name, skip middle)
            first_name = parts[1]
            last_name = parts[0].upper()
            return f"{first_name} {last_name}"
        elif len(parts) == 2:
            # "Василь Савик" - First Surname (no middle name)
            first_name = parts[0]
            last_name = parts[1].upper()
            return f"{first_name} {last_name}"
        else:
            # Just one part - return as is
            return name

    def _get_context(self) -> dict[str, Any]:
        """Збирає контекст для шаблону."""
        staff = self._get_selected_staff()
        from backend.models.settings import SystemSettings, Approvers
        from backend.models.staff import Staff
        from backend.core.database import get_db_context
        from backend.services.grammar_service import GrammarService

        grammar = GrammarService()
        staff_name = ""
        staff_position = ""
        staff_name_nom = ""  # Nominative case for header
        staff_position_nom = ""  # Nominative case for header
        rector_name = ""
        university_name = ""
        dept_name = ""
        signatories = []

        # Always fetch system settings (needed for both staff and new employee documents)
        with get_db_context() as db:
            rector_name_dative = SystemSettings.get_value(db, "rector_name_dative", "")
            rector_name_nominative = SystemSettings.get_value(db, "rector_name_nominative", "")
            dept_name_raw = SystemSettings.get_value(db, "dept_name", "")
            dept_abbr_raw = SystemSettings.get_value(db, "dept_abbr", "")
            university_name_raw = SystemSettings.get_value(db, "university_name", "")

            # Format rector name
            if rector_name_nominative:
                parts = rector_name_nominative.split()
                if len(parts) == 2:
                    first_name = grammar.to_dative(parts[0])
                    last_name = parts[1].upper()
                    rector_name = f"{first_name} {last_name}"
                elif len(parts) >= 3:
                    if parts[0].endswith(('а', 'я', 'я')):
                        first_name = grammar.to_dative(parts[0])
                        last_name = parts[-1].upper()
                        rector_name = f"{first_name} {last_name}"
                    else:
                        for i, part in enumerate(parts[1:], 1):
                            if part.endswith(('а', 'я', 'я')) and not part.endswith(('вна', 'вич', 'ська', 'цька')):
                                first_name = grammar.to_dative(part)
                                last_name = parts[0].upper()
                                rector_name = f"{first_name} {last_name}"
                                break
                        else:
                            rector_name = rector_name_dative
            else:
                rector_name = rector_name_dative

            university_name = university_name_raw
            dept_name = dept_name_raw

            # Get approvers (department head is NOT in Approvers table - added separately)
            approvers = (
                db.query(Approvers)
                .order_by(Approvers.order_index)
                .all()
            )

            for approver in approvers:
                display_name = self._format_signatory_name(approver.full_name_nom or approver.full_name_dav)
                position = approver.position_name
                position_multiline = ""
                signatories.append({
                    "position": position,
                    "position_multiline": position_multiline,
                    "name": display_name
                })
            # Add department head for all documents (ensuring no duplicates)
            dept_head_id_raw = SystemSettings.get_value(db, "dept_head_id", None)

            # Handle various "null" representations
            dept_head_id = None
            if dept_head_id_raw not in (None, "", "None", "null"):
                try:
                    dept_head_id = int(dept_head_id_raw)
                except (ValueError, TypeError):
                    pass

            if dept_head_id:
                head = db.query(Staff).filter(Staff.id == dept_head_id).first()
                if head:
                    head_name_formatted = self._format_signatory_name(head.pib_nom)
                    already_exists = any(s.get("name") == head_name_formatted for s in signatories)
                    if not already_exists:
                        position = get_position_label(head.position)
                        position_multiline = ""
                        if dept_abbr_raw and dept_abbr_raw.lower() not in position.lower():
                            position_multiline = dept_abbr_raw
                        signatories.insert(0, {
                            "position": position,
                            "position_multiline": position_multiline,
                            "name": head_name_formatted
                        })

        # Handle staff-specific logic (name formatting and removing staff from signatories)
        if staff:
            staff_name = staff.pib_nom  # Will be formatted to genitive below
            staff_position = get_position_label(staff.position)  # Ukrainian label for genitive
            staff_name_nom = staff.pib_nom  # Keep nominative for header
            staff_position_nom = get_position_label(staff.position)  # Ukrainian label for nominative

            with get_db_context() as db:
                # Check if current staff IS the department head (compare by ПІБ, not ID)
                # This handles cases where staff has multiple positions
                dept_head_id_raw = SystemSettings.get_value(db, "dept_head_id", None)
                dept_head_id = None
                if dept_head_id_raw not in (None, "", "None", "null"):
                    try:
                        dept_head_id = int(dept_head_id_raw)
                    except (ValueError, TypeError):
                        pass

                if dept_head_id:
                    head = db.query(Staff).filter(Staff.id == dept_head_id).first()
                    if head and staff.pib_nom == head.pib_nom:
                        # Remove department head from signatories if current staff is the head
                        head_name_formatted = self._format_signatory_name(head.pib_nom)
                        signatories = [s for s in signatories if s.get("name") != head_name_formatted]
                    else:
                        # Remove staff from signatories if they are in the list
                        staff_name_formatted = self._format_signatory_name(staff.pib_nom)
                        signatories = [s for s in signatories if s.get("name") != staff_name_formatted]
                else:
                    # No department head set, just remove staff
                    staff_name_formatted = self._format_signatory_name(staff.pib_nom)
                    signatories = [s for s in signatories if s.get("name") != staff_name_formatted]


        # Форматуємо дані заявника (давальний/родовий відмінок)
        # Для прикладу "Професора кафедри нафтогазової інженерії та технологій" + "Цвєтковіча Браніміра"

        # Очищаємо назву кафедри від "кафедри"/"кафедра" якщо вона там є
        dept_clean = dept_name
        if dept_name:
            # Видаляємо всі варіанти "кафедра"/"кафедри" на початку (case-insensitive)
            dept_lower = dept_name.lower().strip()
            if dept_lower.startswith("кафедри "):
                dept_clean = dept_name[8:]  # Remove "кафедри " (8 chars including space)
            elif dept_lower.startswith("кафедра "):
                dept_clean = dept_name[8:]  # Remove "кафедра " (8 chars including space)
            elif dept_lower.startswith("кафедри"):
                dept_clean = dept_name[7:]  # Remove "кафедри"
            elif dept_lower.startswith("кафедра"):
                dept_clean = dept_name[7:]  # Remove "кафедра"

        # Additional safety - strip any remaining leading/trailing whitespace
        if dept_clean:
            dept_clean = dept_clean.strip()


        # Determine which department name to use - prefer abbreviation
        dept_for_position = dept_abbr_raw if dept_abbr_raw else dept_clean

        # Спочатку об'єднуємо посаду з назвою кафедри ( якщо потрібно )
        if staff_position and dept_clean:
            position_lower = staff_position.lower()

            # Якщо посаду вже містить "кафедри", "кафедру" (завідувача кафедри), просто додаємо назву кафедри без повторення
            if "кафедри" in position_lower or "кафедру" in position_lower or "кафедр" in position_lower:
                # Видаляємо зайві пробіли та додаємо назву кафедри
                staff_position_full = f"{position_lower} {dept_for_position}"
            # Якщо це професор/доцент/фахівець без згадки кафедри, додаємо "кафедри"
            elif any(x in position_lower for x in ["професор", "доцент", "асистент", "викладач", "старший викладач", "фахівець"]):
                staff_position_full = f"{position_lower} кафедри {dept_for_position}"
            else:
                staff_position_full = position_lower

            # Capitalize first letter
            if staff_position_full:
                staff_position_full = staff_position_full[0].upper() + staff_position_full[1:]
        elif staff_position:
            staff_position_full = staff_position
        else:
            staff_position_full = ""


        # Also create nominative version with department for header (lowercase)
        if staff_position and dept_clean:
            position_lower = staff_position.lower()

            if "кафедри" in position_lower or "кафедру" in position_lower or "кафедр" in position_lower:
                staff_position_nom_full = f"{position_lower} {dept_for_position}"
                staff_position_nom_capitalized = f"{position_lower} {dept_for_position}"
            elif any(x in position_lower for x in ["професор", "доцент", "асистент", "викладач", "старший викладач", "фахівець"]):
                staff_position_nom_full = f"{position_lower} кафедри {dept_for_position}"
                staff_position_nom_capitalized = f"{position_lower} кафедри {dept_for_position}"
            else:
                staff_position_nom_full = position_lower
                staff_position_nom_capitalized = position_lower

            # Capitalize for signature block
            if staff_position_nom_capitalized:
                staff_position_nom_capitalized = staff_position_nom_capitalized[0].upper() + staff_position_nom_capitalized[1:]
        else:
            staff_position_nom_full = staff_position.lower() if staff_position else ""
            staff_position_nom_capitalized = staff_position[0].upper() + staff_position[1:] if staff_position else ""

        # Тепер перетворюємо в родовий відмінок (GrammarService тепер обробляє це коректно)
        if staff_position_full:
            try:
                # Очищаємо кеш перед використанням, щоб отримати свіжі результати
                grammar.clear_cache()
                staff_position_gen = grammar.to_genitive(staff_position_full)
                staff_position_display = staff_position_gen
            except Exception as e:
                staff_position_display = staff_position_full
        else:
            staff_position_display = ""

        # Ім'я заявника в родовому відмінку - формат: "Прізвище Ім'я По-батькові"
        # Приклад: "Дмитренко Вікторії Іванівни" (прізвище без змін, ім'я + по-батькові в родовому)
        if staff_name:
            try:
                parts = staff_name.split()
                if len(parts) >= 3:
                    # "Дмитренко Вікторія Іванівна" - Surname First Middle
                    # Прізвище залишається без змін, тільки ім'я та по-батькові в родовому
                    surname = parts[0]  # Без змін
                    first_name = grammar.to_genitive(parts[1])  # Вікторія → Вікторії
                    middle_name = grammar.to_genitive(parts[2])  # Іванівна → Іванівни
                    staff_name_display = f"{surname} {first_name} {middle_name}"
                elif len(parts) == 2:
                    # "Прізвище Ім'я"
                    surname = parts[0]  # Без змін
                    first_name = grammar.to_genitive(parts[1])
                    staff_name_display = f"{surname} {first_name}"
                else:
                    # Just one part
                    staff_name_display = staff_name
            except Exception as e:
                    staff_name_display = staff_name
        else:
            staff_name_display = staff_name

        # Форматуємо дати для контексту
        date_start = ""
        date_end = ""
        days_count = 0
        days_count_text = "0 днів"
        martial_law = False

        if self._parsed_dates:
            date_start = self._parsed_dates[0].strftime("%d.%m.%Y")
            date_end = self._parsed_dates[-1].strftime("%d.%m.%Y")
            # Кількість днів - рахуємо кількість обраних дат
            days_count = len(self._parsed_dates)
            # Перевіряємо режим воєнного стану для правильного відмінка
            from backend.core.database import get_db_context
            from backend.services.validation_service import ValidationService

            with get_db_context() as db:
                martial_law = ValidationService.is_martial_law_enabled(db)

            # Формуємо текст залежно від режиму
            if martial_law:
                # Під час воєнного стану - календарні дні
                if days_count == 1:
                    days_count_text = f"{days_count} календарний день"
                elif days_count % 10 == 1 and days_count % 100 != 11:
                    days_count_text = f"{days_count} календарний день"
                elif 2 <= days_count % 10 <= 4 and not (12 <= days_count % 100 <= 14):
                    days_count_text = f"{days_count} календарні дні"
                else:
                    days_count_text = f"{days_count} календарних днів"
            else:
                # В звичайному режимі - робочі дні
                if days_count == 1:
                    days_count_text = f"{days_count} робочий день"
                elif days_count % 10 == 1 and days_count % 100 != 11:
                    days_count_text = f"{days_count} робочий день"
                elif 2 <= days_count % 10 <= 4 and not (12 <= days_count % 100 <= 14):
                    days_count_text = f"{days_count} робочі дні"
                else:
                    days_count_text = f"{days_count} робочих днів"

        # Оплата - завжди автоматично
        payment_period = "у першій половині серпеня 2025 року"
        if self._parsed_dates:
            start = self._parsed_dates[0]
            month_names = {
                1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
                5: "травня", 6: "червня", 7: "липеня", 8: "серпеня",
                9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
            }
            month_name = month_names.get(start.month, "місяця")
            half = "першій" if start.day <= 15 else "другій"
            payment_period = f"у {half} половині {month_name} {start.year} року"

        # Format dates for document display
        formatted_dates = _format_dates_for_document(self._parsed_dates)

        # Add employment type note if internal or external concurrent
        employment_type_note = ""
        if staff and staff.employment_type:
            if staff.employment_type.value == "internal":
                employment_type_note = "(внутрішнє сумісництво)"
            elif staff.employment_type.value == "external":
                employment_type_note = "(зовнішнє сумісництво)"

        return {
            "doc_type": self._get_doc_type().value,
            "staff_name": staff_name_display,  # Genitive case for signature
            "staff_name_nom": staff_name_nom,  # Nominative case for header
            "staff_name_gen": staff_name_display,  # Genitive case for header (same as signature)
            "staff_position": staff_position_nom_capitalized,  # Capitalized nominative for signature
            "staff_position_nom": staff_position_nom_full,  # Lowercase nominative for header
            "date_start": date_start,
            "date_end": date_end,
            "days_count": days_count_text,
            "formatted_dates": formatted_dates,  # Human-readable date format
            "payment_period": payment_period,
            "custom_text": "",  # Custom text can be added later
            # Для шаблону
            "rector_name": rector_name,
            "university_name": university_name,
            "dept_name": dept_name,
            "signatories": signatories,
            "employment_type_note": employment_type_note,
            # Для term_extension_contract
            "rate": str(staff.rate) if staff and staff.rate else "",
            "department": dept_name,
            # Department in dative case for competition template
            "department_dative": grammar.to_dative(dept_clean) if dept_clean else "",
            # Для продовження контракту
            "old_contract_end_date": self.old_contract_date_edit.date().toPyDate().strftime("%d.%m.%Y") if hasattr(self, 'old_contract_date_edit') else "",
            # Для прийому на роботу - нові дані співробітника
            "is_new_employee": self._is_new_employee_mode,
            "new_employee_data": self._get_new_employee_data(),
        }

    def _get_status_label(self) -> str:
        """Повертає текстову мітку статусу."""
        status_labels = {
            DocumentStatus.DRAFT: "Чернетка",
            DocumentStatus.SIGNED_BY_APPLICANT: "Підписав заявник",
            DocumentStatus.APPROVED_BY_DISPATCHER: "Погоджено диспетчером",
            DocumentStatus.SIGNED_DEP_HEAD: "Підписано зав. кафедри",
            DocumentStatus.AGREED: "Погоджено",
            DocumentStatus.SIGNED_RECTOR: "Підписано ректором",
            DocumentStatus.SCANNED: "Відскановано",
            DocumentStatus.PROCESSED: "В табелі",
        }
        return status_labels.get(self._current_status, self._current_status.value)

    def _on_editor_content_changed(self, content_json: str, has_changes: bool):
        """Обробляє зміну контенту в редакторі."""
        try:
            content = json.loads(content_json)
            self._editor_state.from_dict({"blocks": content})

            if has_changes:
                # Показуємо індикатор змін
                self.status_label.setText(f"Статус: {self._get_status_label()} *")

        except json.JSONDecodeError:
            pass

    def _on_signatories_changed(self, signatories_json: str):
        """Обробляє зміну списку погоджувачів."""
        try:
            signatories = json.loads(signatories_json)
            self._editor_state.custom_fields["signatories"] = signatories
            # Зберігаємо в базу при потребі
            print(f"Signatories changed: {signatories}")
        except json.JSONDecodeError as e:
            print(f"Error parsing signatories: {e}")

    def _save_draft(self):
        """Зберігає чернетку документа."""
        # Перевіряємо чи є документ
        if not self._current_document_id:
            QMessageBox.warning(self, "Попередження", "Спочатку створіть документ (натисніть 'Створити заяву')")
            return

        # Експортуємо контент з JavaScript
        self.wysiwyg_bridge.export_content(self.web_view)

        # Отримуємо контент з редактора
        content = self._editor_state.to_dict()
        content_json = json.dumps(content, ensure_ascii=False)

        # Зберігаємо в базу
        from backend.core.database import get_db_context
        from backend.models.document import Document

        try:
            with get_db_context() as db:
                document = db.query(Document).filter(Document.id == self._current_document_id).first()
                if document:
                    document.editor_content = content_json
                    db.commit()
                    QMessageBox.information(
                        self,
                        "Успіх",
                        f"Чернетку документа #{document.id} збережено."
                    )
                else:
                    QMessageBox.warning(self, "Помилка", "Документ не знайдено в базі")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти чернетку: {e}")

    def _reset_changes(self):
        """Скидає всі зміни в редакторі."""
        reply = QMessageBox.question(
            self,
            "Підтвердження",
            "Скинути всі зміни в редакторі до початкового стану?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.wysiwyg_bridge.reset_to_original(self.web_view)
            self._editor_state.clear()
            self.status_label.setText(f"Статус: {self._get_status_label()}")

    def _print_document(self):
        """Друкує документ - спочатку генерує, потім друкує."""
        import os
        from PyQt6.QtWidgets import QMessageBox
        from backend.services.document_service import DocumentService
        from backend.services.grammar_service import GrammarService
        from backend.services.validation_service import ValidationService
        from backend.models.document import Document
        from backend.core.database import get_db_context
        from PyQt6.QtCore import Qt
        from datetime import timedelta
        from pathlib import Path

        # Валідація (така сама як в _generate_document)
        is_employment = self._is_employment_doc_type()

        if not is_employment:
            staff = self._get_selected_staff()
            if not staff:
                QMessageBox.warning(self, "Помилка", "Не обрано співробітника")
                return

            if not self._parsed_dates:
                QMessageBox.warning(self, "Помилка", "Не введено дати відпустки")
                return

            doc_type = self._get_doc_type()

            # Check contract validity for paid vacation
            if doc_type == DocumentType.VACATION_PAID:
                if not self._can_create_vacation():
                    reply = QMessageBox.question(
                        self,
                        "Контракт закінчується",
                        "Дати відпустки виходять за межі контракту (менш ніж 2 тижні до закінчення).\n"
                        "Спочатку оформіть продовження контракту.\n\n"
                        "Продовжити все одно?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return

            start = self._parsed_dates[0]
            end = self._parsed_dates[-1]
            days_count = len(self._parsed_dates)
        else:
            start = None
            end = None
            days_count = 0

        with get_db_context() as db:
            from backend.models.staff import Staff as StaffModel
            if not is_employment:
                staff_db = db.query(StaffModel).filter(StaffModel.id == staff.id).first()
                if not staff_db:
                    QMessageBox.warning(self, "Помилка", "Співробітника не знайдено")
                    return

            # For term extension, validate that new date is after current contract end
            is_term_extension = doc_type in (
                DocumentType.TERM_EXTENSION,
                DocumentType.TERM_EXTENSION_CONTRACT,
                DocumentType.TERM_EXTENSION_COMPETITION,
                DocumentType.TERM_EXTENSION_PDF,
            )
            if is_term_extension:
                if end <= staff.term_end:
                    QMessageBox.warning(
                        self,
                        "Помилка",
                        f"Дата продовження контракту має бути пізніше за поточну дату закінчення ({staff.term_end.strftime('%d.%m.%Y')})."
                    )
                    return

            # Перевіряємо баланс та ліміти воєнного стану
            if doc_type == DocumentType.VACATION_PAID:
                admin_override = self.admin_override_checkbox.isChecked()
                if not admin_override:
                    valid, error_msg = ValidationService.validate_vacation_against_balance(
                        start, end, staff, db
                    )
                    if not valid:
                        QMessageBox.warning(self, "Помилка", error_msg)
                        return

            # Валідація дат
            from backend.services.date_parser import DateParser
            parser = DateParser()
            is_valid, errors = parser.validate_date_range(self._parsed_dates)

            if not is_valid:
                error_msg = "\n".join(errors)
                reply = QMessageBox.question(
                    self,
                    "Попередження валідації",
                    f"Знайдено проблеми з датами:\n{error_msg}\n\nПродовжити?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            try:
                # Створення або оновлення документа
                if self._current_document_id:
                    # Оновлюємо існуючий документ
                    document = db.query(Document).filter(
                        Document.id == self._current_document_id
                    ).first()
                    if document:
                        if is_employment:
                            # For employment documents, update from employee_data
                            from datetime import datetime
                            term_start_date = datetime.strptime(employee_data["term_start"], "%d.%m.%Y").date()
                            term_end_date = datetime.strptime(employee_data["term_end"], "%d.%m.%Y").date()
                            document.date_start = term_start_date
                            document.date_end = term_end_date
                            document.new_employee_data = employee_data
                        else:
                            # Update dates for non-employment documents
                            document.date_start = start
                            document.date_end = end
                            document.days_count = days_count
                            # Оплата - завжди автоматично
                            if start and start.day > 15:
                                document.payment_period = "У другій половині місяця"
                            else:
                                document.payment_period = "У першій половині місяця"
                else:
                    # For employment documents, calculate dates from employee_data
                    if is_employment:
                        from datetime import datetime
                        term_start_date = datetime.strptime(employee_data["term_start"], "%d.%m.%Y").date()
                        term_end_date = datetime.strptime(employee_data["term_end"], "%d.%m.%Y").date()
                        date_start_for_doc = term_start_date
                        date_end_for_doc = term_end_date
                        payment_period = "У першій половині місяця"
                        if term_start_date.day > 15:
                            payment_period = "У другій половині місяця"
                    else:
                        date_start_for_doc = start
                        date_end_for_doc = end
                        # Оплата - завжди автоматично
                        payment_period = "У першій половині місяця"
                        if start and start.day > 15:
                            payment_period = "У другій половині місяця"

                    # For employment documents, use specialist (or department head if specialist not available)
                    if is_employment:
                        # Get specialist or department head for employment documents
                        specialist_id_raw = SystemSettings.get_value(db, "dept_specialist_id", None)
                        staff_id_for_doc = None
                        if specialist_id_raw and str(specialist_id_raw) not in ("None", "none", ""):
                            staff_id_for_doc = int(specialist_id_raw)
                        else:
                            # Fallback to department head
                            dept_head_id_raw = SystemSettings.get_value(db, "dept_head_id", None)
                            if dept_head_id_raw and str(dept_head_id_raw) not in ("None", "none", ""):
                                staff_id_for_doc = int(dept_head_id_raw)
                    else:
                        staff_id_for_doc = staff.id

                    document = Document(
                        staff_id=staff_id_for_doc,
                        doc_type=doc_type,
                        date_start=date_start_for_doc,
                        date_end=date_end_for_doc,
                        days_count=days_count,
                        payment_period=payment_period,
                        new_employee_data=employee_data if is_employment else None,
                    )
                    db.add(document)

                db.commit()
                db.refresh(document)

                # Зберігаємо стан редактора
                self._save_editor_state(db, document)

                # Отримуємо HTML з веб-в'ю для точного відображення
                from PyQt6.QtCore import QEventLoop, QTimer

                raw_html = None
                loop = QEventLoop()

                def on_html_ready(html):
                    nonlocal raw_html
                    raw_html = html
                    loop.quit()

                self.wysiwyg_bridge.get_document_html_for_pdf(self.web_view, on_html_ready)

                # Чекаємо на відповідь (максимум 5 секунд)
                timeout = QTimer()
                timeout.setSingleShot(True)
                timeout.timeout.connect(loop.quit)
                timeout.start(5000)

                loop.exec()
                timeout.stop()

                # Генерація PDF
                grammar = GrammarService()
                doc_service = DocumentService(db, grammar)

                file_path = doc_service.generate_document(document, raw_html)

                # Оновлюємо статус
                self._current_document_id = document.id
                self._current_status = document.status
                self._update_ui_status()

                # Тепер друкуємо PDF через Windows
                pdf_path = Path(file_path)
                if pdf_path.exists():
                    # Використовуємо print verb для Windows
                    os.startfile(str(pdf_path), "print")

                    QMessageBox.information(
                        self,
                        "Друк",
                        f"Документ згенеровано та відправлено на друк:\n{file_path}"
                    )
                    
                    if self.is_ephemeral:
                        self.task_completed.emit()
                else:
                    QMessageBox.warning(self, "Помилка", f"PDF файл не знайдено:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося підготувати документ до друку:\n{str(e)}")

    def _on_print_result(self, success: bool):
        """Обробляє результат друку."""
        from PyQt6.QtWidgets import QMessageBox
        if success:
            QMessageBox.information(self, "Успіх", "Документ надіслано на друк")
        else:
            QMessageBox.warning(self, "Помилка", "Не вдалося надрукувати документ")

    def _generate_document(self):
        """Генерує документ."""
        from backend.services.document_service import DocumentService
        from backend.services.grammar_service import GrammarService
        from backend.services.validation_service import ValidationService
        from backend.models.document import Document
        from backend.core.database import get_db_context
        from shared.exceptions import ValidationError
        from PyQt6.QtCore import Qt

        doc_type = self._get_doc_type()
        is_employment = self._is_employment_doc_type()

        # Валідація для документів прийому на роботу
        if is_employment:
            employee_data = self._get_new_employee_data()
            if not employee_data:
                QMessageBox.warning(self, "Помилка", "Заповніть дані нового співробітника")
                return

            if not employee_data.get("pib_nom"):
                QMessageBox.warning(self, "Помилка", "Введіть ПІБ співробітника")
                return

            if employee_data.get("term_end") <= employee_data.get("term_start"):
                QMessageBox.warning(self, "Помилка", "Дата закінчення контракту має бути пізніше за дату початку")
                return
        else:
            # Валідація для звичайних документів
            staff = self._get_selected_staff()
            if not staff:
                QMessageBox.warning(self, "Помилка", "Не обрано співробітника")
                return

            if not self._parsed_dates:
                QMessageBox.warning(self, "Помилка", "Не введено дати відпустки")
                return

        # Check contract validity for paid vacation
        if doc_type == DocumentType.VACATION_PAID:
            if not self._can_create_vacation():
                reply = QMessageBox.question(
                    self,
                    "Контракт закінчується",
                    "Дати відпустки виходять за межі контракту (менш ніж 2 тижні до закінчення).\n"
                    "Спочатку оформіть продовження контракту.\n\n"
                    "Продовжити все одно?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

        # For employment documents, we don't use _parsed_dates
        if is_employment:
            start = None
            end = None
            days_count = 0
        else:
            start = self._parsed_dates[0]
            end = self._parsed_dates[-1]
            days_count = len(self._parsed_dates)

        with get_db_context() as db:
            from backend.models.staff import Staff as StaffModel
            # For employment documents, skip staff lookup
            if not is_employment:
                staff_db = db.query(StaffModel).filter(StaffModel.id == staff.id).first()
                if not staff_db:
                    QMessageBox.warning(self, "Помилка", "Співробітника не знайдено")
                    return

            from backend.services.validation_service import ValidationService

            # For term extension, validate that new date is after current contract end
            is_term_extension = doc_type in (
                DocumentType.TERM_EXTENSION,
                DocumentType.TERM_EXTENSION_CONTRACT,
                DocumentType.TERM_EXTENSION_COMPETITION,
                DocumentType.TERM_EXTENSION_PDF,
            )
            if is_term_extension:
                if end <= staff.term_end:
                    QMessageBox.warning(
                        self,
                        "Помилка",
                        f"Дата продовження контракту має бути пізніше за поточну дату закінчення ({staff.term_end.strftime('%d.%m.%Y')})."
                    )
                    return

            # Skip validation for employment documents (they don't use staff dates)
            if not is_employment:
                # Перевіряємо ліміти документів (макс 1 продовження, макс 3 відпустки на підписі)
                valid, error_msg = ValidationService.validate_document_limits(
                    staff.id,
                    doc_type.value,
                    self._current_document_id,  # При редагуванні - виключаємо поточний документ
                    db
                )
                if not valid:
                    QMessageBox.warning(self, "Обмеження документів", error_msg)
                    return

                # Перевіряємо баланс та ліміти воєнного стану
                if doc_type == DocumentType.VACATION_PAID:
                    # Для оплачуваної відпустки - перевіряємо баланс та ліміти
                    admin_override = self.admin_override_checkbox.isChecked()

                    if admin_override:
                        # Admin override - ПРОПУСКАЄМО ВСІ ПЕРЕВІРКИ
                        # Дозволяємо створення відпустки незалежно від балансу та лімітів
                        pass
                    else:
                        # Стандартна валідація з лімітами
                        valid, error_msg = ValidationService.validate_vacation_against_balance(
                            start, end, staff, db
                        )
                        if not valid:
                            QMessageBox.warning(self, "Помилка", error_msg)
                            return
                elif doc_type == DocumentType.VACATION_UNPAID:
                    # Для відпустки без збереження - не перевіряємо баланс
                    # Тільки попередження
                    pass

                # Валідація дат
                from backend.services.date_parser import DateParser
                parser = DateParser()
                is_valid, errors = parser.validate_date_range(self._parsed_dates)

                if not is_valid:
                    error_msg = "\n".join(errors)
                    reply = QMessageBox.question(
                        self,
                        "Попередження валідації",
                        f"Знайдено проблеми з датами:\n{error_msg}\n\nПродовжити?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return

            # Прогрес-діалог
            progress = QProgressDialog("Генерація документа...", "Скасувати", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                # Створення або оновлення документа

                if self._current_document_id:
                    # Оновлюємо існуючий документ
                    document = db.query(Document).filter(
                        Document.id == self._current_document_id
                    ).first()
                    if not document:
                        raise Exception("Документ не знайдено")

                    # Перевіряємо чи документ вже відскановано
                    if document.status in (DocumentStatus.SCANNED, DocumentStatus.PROCESSED):
                        QMessageBox.warning(
                            self,
                            "Помилка",
                            "Неможливо редагувати документ, який вже відскановано."
                        )
                        return

                    # Handle employment documents
                    if is_employment:
                        employee_data = self._get_new_employee_data()
                        from datetime import datetime
                        term_start_date = datetime.strptime(employee_data["term_start"], "%d.%m.%Y").date()
                        term_end_date = datetime.strptime(employee_data["term_end"], "%d.%m.%Y").date()
                        document.date_start = term_start_date
                        document.date_end = term_end_date
                        document.new_employee_data = employee_data
                    else:
                        document.date_start = start
                        document.date_end = end
                        document.days_count = days_count
                        # Оплата - завжди автоматично
                        if start:
                            payment_period = "У першій половині місяця"
                            if start.day > 15:
                                payment_period = "У другій половині місяця"
                            document.payment_period = payment_period

                    # Зберігаємо old_contract_end_date для продовження контракту
                    if is_term_extension:
                        document.old_contract_end_date = self.old_contract_date_edit.date().toPyDate()

                    # Скидаємо етапи підписання при редагуванні
                    document.reset_workflow()
                else:
                    # Створюємо новий документ
                    # Зберігаємо old_contract_end_date для продовження контракту
                    old_contract_end = None
                    if is_term_extension:
                        old_contract_end = self.old_contract_date_edit.date().toPyDate()

                    if is_employment:
                        # Для документів прийому на роботу - staff_id буде призначено після скану
                        employee_data = self._get_new_employee_data()
                        # Convert string dates to date objects
                        from datetime import datetime
                        term_start_date = datetime.strptime(employee_data["term_start"], "%d.%m.%Y").date()
                        term_end_date = datetime.strptime(employee_data["term_end"], "%d.%m.%Y").date()
                        # Оплата - визначаємо з term_start
                        payment_period = "У першій половині місяця"
                        if term_start_date.day > 15:
                            payment_period = "У другій половині місяця"
                        # Get specialist or department head for employment documents
                        specialist_id_raw = SystemSettings.get_value(db, "dept_specialist_id", None)
                        staff_id_for_employment = None
                        if specialist_id_raw and str(specialist_id_raw) not in ("None", "none", ""):
                            staff_id_for_employment = int(specialist_id_raw)
                        else:
                            dept_head_id_raw = SystemSettings.get_value(db, "dept_head_id", None)
                            if dept_head_id_raw and str(dept_head_id_raw) not in ("None", "none", ""):
                                staff_id_for_employment = int(dept_head_id_raw)
                        document = Document(
                            staff_id=staff_id_for_employment,
                            doc_type=doc_type,
                            date_start=term_start_date,
                            date_end=term_end_date,
                            days_count=0,  # Не використовується для прийому
                            payment_period=payment_period,
                            old_contract_end_date=old_contract_end,
                            new_employee_data=employee_data,
                        )
                    else:
                        # Оплата - завжди автоматично
                        payment_period = "У першій половині місяця"
                        if start and start.day > 15:
                            payment_period = "У другій половині місяця"
                        document = Document(
                            staff_id=staff.id,
                            doc_type=doc_type,
                            date_start=start,
                            date_end=end,
                            days_count=days_count,
                            payment_period=payment_period,
                            old_contract_end_date=old_contract_end,
                        )
                    db.add(document)

                db.commit()
                db.refresh(document)

                progress.setValue(50)

                # Зберігаємо стан редактора
                self._save_editor_state(db, document)

                # Отримуємо HTML з веб-в'ю для точного відображення
                from PyQt6.QtCore import QEventLoop, QTimer

                raw_html = None
                loop = QEventLoop()

                def on_html_ready(html):
                    nonlocal raw_html
                    raw_html = html
                    loop.quit()

                self.wysiwyg_bridge.get_document_html_for_pdf(self.web_view, on_html_ready)

                # Чекаємо на відповідь (максимум 5 секунд)
                timeout = QTimer()
                timeout.setSingleShot(True)
                timeout.timeout.connect(loop.quit)
                timeout.start(5000)

                loop.exec()
                timeout.stop()

                # Генерація PDF
                grammar = GrammarService()
                doc_service = DocumentService(db, grammar)

                file_path = doc_service.generate_document(document, raw_html)
                progress.setValue(100)

                # Оновлюємо статус
                self._current_document_id = document.id
                self._current_status = document.status
                self._update_ui_status()

                QMessageBox.information(
                    self,
                    "Успішно",
                    f"Документ згенеровано:\n{file_path}",
                )

                self.document_created.emit()
                if self._current_document_id:
                    self.document_updated.emit(self._current_document_id)

                if self.is_ephemeral:
                    self.task_completed.emit()

            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося згенерувати документ:\n{str(e)}")
            finally:
                progress.close()

    def _save_editor_state(self, db, document: "Document") -> None:
        """
        Зберігає стан WYSIWYG редактора в документ.

        Args:
            db: Сесія бази даних
            document: Об'єкт документа
        """
        from PyQt6.QtCore import QEventLoop, QTimer

        # Спробуємо отримати контент з JavaScript
        self.wysiwyg_bridge.export_content(self.web_view)

        # Чекаємо на відповідь від JavaScript (максимум 5 секунди)
        loop = QEventLoop()
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)

        def on_content():
            timeout.stop()
            loop.quit()

        self.wysiwyg_bridge.content_changed.connect(on_content)
        try:
            timeout.start(5000)
            loop.exec()
        finally:
            self.wysiwyg_bridge.content_changed.disconnect(on_content)

        # Якщо JavaScript не повернув контент, видобуваємо з HTML веб-в'ю
        if not self._editor_state.blocks:
            blocks = self._extract_blocks_from_webview()
            if blocks:
                self._editor_state.blocks = blocks

        # Зберігаємо стан редактора в базу
        content = self._editor_state.to_dict()
        content_json = json.dumps(content, ensure_ascii=False)
        document.editor_content = content_json

    def _extract_blocks_from_webview(self) -> dict:
        """Видобуває блоки безпосередньо з HTML веб-в'ю."""
        import re
        from PyQt6.QtCore import QEventLoop, QTimer

        blocks = {}

        try:
            # Отримуємо HTML з веб-в'ю
            def get_html(result):
                return result

            self.web_view.page().toHtml(get_html)

            # Чекаємо на результат
            loop = QEventLoop()
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)

            html_content = [None]

            def capture_html(html):
                html_content[0] = html
                loop.quit()

            self.web_view.page().toHtml(capture_html)
            timer.start(2000)
            loop.exec()

            if html_content[0]:
                html = html_content[0]

                # Знаходимо всі елементи з data-block
                # Шукаємо <div data-block="xxx" ... >...</div>
                pattern = r'<div[^>]*data-block="([^"]+)"[^>]*>(.*?)</div>'
                matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

                for block_name, block_content in matches:
                    # Очищаємо контент від зайвих атрибутів
                    block_content = re.sub(r'\s*contenteditable="[^"]*"', '', block_content)
                    block_content = re.sub(r'\s*data-(block|field|signatory-id)="[^"]*"', '', block_content)
                    if block_content.strip():
                        blocks[block_name] = block_content.strip()

        except Exception:
            pass

        return blocks

    def _update_ui_status(self):
        """Оновлює UI відповідно до статусу документа."""
        self.status_label.setText(f"Статус: {self._get_status_label()}")

        # Оновлюємо колір статусу
        colors = {
            DocumentStatus.DRAFT: "#8c8c8f",
            DocumentStatus.SIGNED_BY_APPLICANT: "#1890ff",
            DocumentStatus.APPROVED_BY_DISPATCHER: "#13c2c2",
            DocumentStatus.SIGNED_DEP_HEAD: "#52c41a",
            DocumentStatus.AGREED: "#faad14",
            DocumentStatus.SIGNED_RECTOR: "#722ed1",
            DocumentStatus.SCANNED: "#eb2f96",
            DocumentStatus.PROCESSED: "#006d75",
        }
        self.status_label.setStyleSheet(
            f"font-weight: bold; color: {colors.get(self._current_status, '#666')};"
        )

        # Показуємо/ховаємо кнопку відкликання
        # Доступно для статусів від signed_by_applicant до signed_rector
        rollback_statuses = (
            DocumentStatus.SIGNED_BY_APPLICANT,
            DocumentStatus.APPROVED_BY_DISPATCHER,
            DocumentStatus.SIGNED_DEP_HEAD,
            DocumentStatus.AGREED,
            DocumentStatus.SIGNED_RECTOR,
        )
        self.rollback_btn.setVisible(
            self._current_document_id is not None and
            self._current_status in rollback_statuses
        )

        # Оновлюємо статус в редакторі (з затримкою для завантаження JS)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.wysiwyg_bridge.set_document_status(
            self.web_view,
            self._current_status.value,
            self._get_status_label()
        ))

    def _rollback_document(self):
        """Відкликає документ в статус чернетки."""
        if not self._current_document_id:
            return

        reply = QMessageBox.question(
            self,
            "Підтвердження відкликання",
            "Повернути документ в статус чернетки?\n\n"
            "Файли будуть переміщені в obsolete, документ знову стане доступний для редагування.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            from backend.services.document_service import DocumentService
            from backend.services.grammar_service import GrammarService
            from backend.models.document import Document
            from backend.core.database import get_db_context

            with get_db_context() as db:
                document = db.query(Document).filter(
                    Document.id == self._current_document_id
                ).first()

                if document:
                    grammar = GrammarService()
                    doc_service = DocumentService(db, grammar)

                    try:
                        doc_service.rollback_to_draft(document)
                        self._current_status = DocumentStatus.DRAFT
                        self._update_ui_status()

                        QMessageBox.information(
                            self,
                            "Успішно",
                            "Документ відкликано в статус чернетки."
                        )

                    except Exception as e:
                        QMessageBox.critical(self, "Помилка", f"Не вдалося відкликати документ:\n{str(e)}")

    def update_staff_contract_from_extension(self, document_id: int):
        """
        Оновлює дату закінчення контракту співробітника після підписання
        документа про продовження контракту.

        Args:
            document_id: ID документа про продовження контракту
        """
        from backend.models.document import Document
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            document = db.query(Document).filter(Document.id == document_id).first()

            if not document:
                return False

            if document.doc_type != DocumentType.TERM_EXTENSION:
                return False

            if document.status != DocumentStatus.SIGNED_RECTOR:
                return False

            staff = db.query(Staff).filter(Staff.id == document.staff_id).first()
            if not staff:
                return False

            # Оновлюємо дату закінчення контракту
            old_term_end = staff.term_end
            staff.term_end = document.date_end

            db.commit()

            return True

    def clear_form(self):
        """Очищає форму для створення нового документа."""
        self._current_document_id = None
        self._current_status = DocumentStatus.DRAFT
        self._editor_state.clear()
        self._parsed_dates = []

        # Скидаємо поля форми
        if self.staff_input.count() > 0:
            self.staff_input.setCurrentIndex(0)

        # Скидаємо тип документа на "оплачувана відпустка"
        for i in range(self.doc_type_combo.count()):
            if "оплачувана" in self.doc_type_combo.itemText(i).lower():
                self.doc_type_combo.setCurrentIndex(i)
                break
        else:
            if self.doc_type_combo.count() > 0:
                self.doc_type_combo.setCurrentIndex(0)

        # Очищаємо дати
        self._date_ranges = []
        self._update_ranges_list()
        self.dates_info_label.setText("Не вибрано")

        self._update_ui_status()
        self._update_preview()

    def refresh(self):
        """Оновлює дані вкладки (перезавантажує список співробітників)."""
        # Перезавантажуємо список співробітників
        current_pib = self.staff_input.currentData()
        self._load_staff()
        if current_pib:
            index = self.staff_input.findData(current_pib)
            if index >= 0:
                self.staff_input.setCurrentIndex(index)
            else:
                # Staff might have been removed, trigger position selector update
                self._on_staff_selected(self.staff_input.currentIndex())

    def start_subposition_document(self):
        """Починає процес створення документа продовження сумісництва."""
        # First ensure UI is loaded and staff is selected
        if not hasattr(self, 'doc_type_combo') or self.doc_type_combo.count() == 0:
            # UI not ready, trigger staff load first
            self._on_staff_selected(self.staff_input.currentIndex() if hasattr(self, 'staff_input') else 0)

        # Select "Продовження (сумісництво)" document type
        if hasattr(self, 'doc_type_combo'):
            for i in range(self.doc_type_combo.count()):
                if "сумісництво" in self.doc_type_combo.itemText(i).lower():
                    self.doc_type_combo.setCurrentIndex(i)
                    break

        # Show dialog to select staff with main position (rate 1.0)
        self._on_staff_selected(self.staff_input.currentIndex() if hasattr(self, 'staff_input') else 0)

    def start_new_employee_document(self):
        """
        Починає процес створення документа для нового співробітника.
        Вмикає відповідний режим і фільтрує список документів.
        """
        self._current_document_id = None
        self._clear_form()
        
        # Enable new employee mode
        self._is_new_employee_mode = True
        
        # Refresh templates list (will only show employment docs)
        self._discover_document_templates()
        
        # Auto-select the first available template (usually Employment Contract)
        if self.doc_type_combo.count() > 0:
            self.doc_type_combo.setCurrentIndex(0)
            
        # Ensure UI is in correct state
        self._toggle_employment_mode()

    def _add_date_range(self):
        """Відкриває popup для додавання діапазону дат."""
        # For term extension, only allow one range
        doc_type = self._get_doc_type()
        is_term_extension = doc_type in (
            DocumentType.TERM_EXTENSION,
            DocumentType.TERM_EXTENSION_CONTRACT,
            DocumentType.TERM_EXTENSION_COMPETITION,
            DocumentType.TERM_EXTENSION_PDF,
        )
        if is_term_extension:
            self._date_ranges = []  # Clear existing ranges
            self._parsed_dates = []  # Clear parsed dates
            self._update_ranges_list()
            self._update_dates_info()  # Also update the info label

        # Get current staff for locked dates
        staff = self._get_selected_staff()
        staff_id = staff.id if staff else None

        popup = DateRangePickerPopup(self, staff_id=staff_id)
        popup.selection_complete.connect(self._on_popup_selection_complete)
        popup.show_popup()

        # Зберігаємо посилання на popup щоб він не був видалений
        self._current_popup = popup

    def _open_auto_date_dialog(self):
        """Відкриває діалог автоматичного підбору дат."""
        staff = self._get_selected_staff()
        if not staff:
            QMessageBox.warning(self, "Попередження", "Спочатку оберіть співробітника!")
            return

        doc_type = self._get_doc_type()
        is_term_extension = doc_type in (
            DocumentType.TERM_EXTENSION,
            DocumentType.TERM_EXTENSION_CONTRACT,
            DocumentType.TERM_EXTENSION_COMPETITION,
            DocumentType.TERM_EXTENSION_PDF,
        )
        if is_term_extension:
            QMessageBox.warning(
                self,
                "Попередження",
                "Для продовження контракту дати підбираються вручну."
            )
            return

        dialog = AutoDateRangeDialog(staff.id, self)
        dialog.selection_complete.connect(self._on_auto_date_complete)
        dialog.exec()

    def _on_auto_date_complete(self, ranges: list[tuple]):
        """Обробляє результат автоматичного підбору дат."""
        if not ranges:
            return

        doc_type = self._get_doc_type()
        if doc_type == DocumentType.TERM_EXTENSION:
            self._date_ranges = []
        else:
            # Перевіряємо накладення з існуючими діапазонами
            for start, end in ranges:
                for ex_start, ex_end in self._date_ranges:
                    # Перевіряємо перекриття
                    if not (end < ex_start or start > ex_end):
                        QMessageBox.warning(
                            self,
                            "Попередження",
                            "Обрані дати перекриваються з вже обраними!"
                        )
                        return

        # Додаємо нові діапазони
        for start, end in ranges:
            self._date_ranges.append((start, end))

        self._update_ranges_list()
        self._update_dates_info()
        self._update_preview()

    def _on_popup_selection_complete(self, dates: list[date]):
        """Обробляє завершення вибору в popup."""
        doc_type = self._get_doc_type()
        is_term_extension = doc_type in (
            DocumentType.TERM_EXTENSION,
            DocumentType.TERM_EXTENSION_CONTRACT,
            DocumentType.TERM_EXTENSION_COMPETITION,
            DocumentType.TERM_EXTENSION_PDF,
        )

        if dates:
            start = dates[0]
            end = dates[-1]

            # Check for duplicates within the new selection
            new_dates_set = set(dates)
            if len(new_dates_set) != len(dates):
                QMessageBox.warning(
                    self,
                    "Помилка",
                    "Обраний діапазон містить дублікати дат."
                )
                self._current_popup = None
                return

            # For term extension, clear old ranges first (single range only)
            if is_term_extension:
                self._date_ranges = []

            # Check for overlaps with existing ranges (only for non-term-extension)
            if not is_term_extension:
                new_dates_ordinals = set(d.toordinal() for d in dates)
                for existing_start, existing_end in self._date_ranges:
                    existing_dates_ordinals = set(
                        d.toordinal() for d in _date_range_iter(existing_start, existing_end)
                    )
                    # Check for overlap
                    if existing_dates_ordinals & new_dates_ordinals:
                        QMessageBox.warning(
                            self,
                            "Помилка",
                            "Обраний діапазон перетинається з вже обраними датами."
                        )
                        self._current_popup = None
                        return

            self._date_ranges.append((start, end))
            self._update_ranges_list()
            self._update_dates_info()
            self._update_preview()
        else:
            # User cancelled - for term extension, dates are already cleared
            # Update UI to reflect empty state
            if is_term_extension:
                self._update_ranges_list()
                self._update_dates_info()
        # Очищаємо посилання на popup
        self._current_popup = None

    def _clear_all_ranges(self):
        """Очищає всі діапазони."""
        # For term extension, don't allow clearing all
        doc_type = self._get_doc_type()
        is_term_extension = doc_type in (
            DocumentType.TERM_EXTENSION,
            DocumentType.TERM_EXTENSION_CONTRACT,
            DocumentType.TERM_EXTENSION_COMPETITION,
            DocumentType.TERM_EXTENSION_PDF,
        )
        if is_term_extension:
            return

        self._date_ranges = []
        self._update_ranges_list()
        self._update_dates_info()
        self._update_preview()

    def _remove_range(self, index: int):
        """Видаляє діапазон за індексом."""
        # For term extension, don't allow removing
        doc_type = self._get_doc_type()
        is_term_extension = doc_type in (
            DocumentType.TERM_EXTENSION,
            DocumentType.TERM_EXTENSION_CONTRACT,
            DocumentType.TERM_EXTENSION_COMPETITION,
            DocumentType.TERM_EXTENSION_PDF,
        )
        if is_term_extension:
            return

        if 0 <= index < len(self._date_ranges):
            del self._date_ranges[index]
            self._update_ranges_list()
            self._update_dates_info()
            self._update_preview()

    def _update_ranges_list(self):
        """Оновлює список діапазонів в UI."""
        # Очищаємо layout
        while self._ranges_layout.count():
            child = self._ranges_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Check if term extension (single range only)
        doc_type = self._get_doc_type()
        is_term_extension = doc_type == DocumentType.TERM_EXTENSION

        # For term extension, update button text and visibility
        if hasattr(self, 'add_range_btn') and self.add_range_btn:
            if is_term_extension:
                self.add_range_btn.setText("Змінити період")
                self.add_range_btn.setToolTip("Натисніть, щоб обрати інший період продовження")
            else:
                self.add_range_btn.setText("Додати діапазон")
                self.add_range_btn.setToolTip("")

        if hasattr(self, 'clear_ranges_btn') and self.clear_ranges_btn:
            self.clear_ranges_btn.setVisible(not is_term_extension)

        # Додаємо діапазони
        for i, (start, end) in enumerate(self._date_ranges):
            range_widget = QWidget()
            range_layout = QHBoxLayout(range_widget)
            range_layout.setContentsMargins(0, 2, 0, 2)

            # Текст діапазону
            if start == end:
                range_text = start.strftime("%d.%m.%Y")
            else:
                range_text = f"{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}"
            label = QLabel(range_text)
            range_layout.addWidget(label)

            range_layout.addStretch()

            # Кнопка видалення (only show for non-term-extension)
            if not is_term_extension:
                remove_btn = QPushButton("✕")
                remove_btn.setFixedSize(24, 24)
                remove_btn.setStyleSheet("QPushButton { color: #dc3545; font-weight: bold; }")
                remove_btn.clicked.connect(lambda checked, idx=i: self._remove_range(idx))
                range_layout.addWidget(remove_btn)

            self._ranges_layout.addWidget(range_widget)

    def _update_dates_info(self):
        """Оновлює інформацію про вибрані дати."""
        # Update group box title based on document type
        doc_type = self._get_doc_type()
        is_term_extension = doc_type in (
            DocumentType.TERM_EXTENSION,
            DocumentType.TERM_EXTENSION_CONTRACT,
            DocumentType.TERM_EXTENSION_COMPETITION,
            DocumentType.TERM_EXTENSION_PDF,
        )
        if is_term_extension:
            self.date_group.setTitle("📅 Період продовження контракту")
            self.extension_dates_widget.setVisible(True)
            self.extension_warning_label.setText(
                "Оберіть період нового контракту. Після підпису ректора дні продовження "
                "будуть автоматично додані до табелю."
            )
            self.extension_warning_label.setVisible(True)
        else:
            self.date_group.setTitle("📅 Вибір дат відпустки")
            self.extension_dates_widget.setVisible(False)

        if not self._date_ranges:
            self.dates_info_label.setText("Не вибрано")
            self.balance_warning_label.setVisible(False)
            self.admin_override_group.setVisible(False)
            self.timing_warning_label.setVisible(False)
            self.locked_dates_warning_label.setVisible(False)
            self.additional_position_widget.setVisible(False)
            self.extension_warning_label.setVisible(False)
            self._parsed_dates = []
            return

        # Генеруємо всі дати з діапазонів
        all_dates = []
        for start, end in self._date_ranges:
            current = start
            while current <= end:
                all_dates.append(current)
                current += timedelta(days=1)

        # Сортуємо і видаляємо дублікати
        all_dates = sorted(set(all_dates))
        self._parsed_dates = all_dates

        # Для відпустки рахуємо з урахуванням воєнного стану, для продовження контракту - календарні
        # Рахуємо кількість обраних днів
        days_count = len(all_dates)

        range_count = len(self._date_ranges)

        # Different text for term extension vs vacation
        if doc_type == DocumentType.TERM_EXTENSION:
            if days_count == 1:
                self.dates_info_label.setText(f"✓ Вибрано: 1 день")
            elif 2 <= days_count <= 4:
                self.dates_info_label.setText(f"✓ Вибрано: {days_count} дні")
            else:
                self.dates_info_label.setText(f"✓ Вибрано: {days_count} днів")
        else:
            if range_count > 1:
                self.dates_info_label.setText(f"✓ Вибрано: {days_count} днів ({range_count} діапазони)")
            elif days_count == 1:
                self.dates_info_label.setText(f"✓ Вибрано: 1 день")
            elif 2 <= days_count <= 4:
                self.dates_info_label.setText(f"✓ Вибрано: {days_count} дні")
            else:
                self.dates_info_label.setText(f"✓ Вибрано: {days_count} днів")

        # Only check vacation-specific things for non-term-extension docs
        if doc_type != DocumentType.TERM_EXTENSION:
            # Перевіряємо баланс відпустки
            self._check_vacation_balance(days_count)

            # Перевіряємо дати відпустки проти контракту
            self._check_vacation_dates_against_contract()

            # Перевіряємо перетин з заблокованими датами
            self._check_locked_dates()

            # Перевіряємо дотримання 2-тижневого терміну подання заяви
            self._check_application_timing()

            # Перевіряємо додаткові позиції
            self._check_additional_positions()
        else:
            # For term extension, hide vacation-specific widgets
            self.balance_warning_label.setVisible(False)
            self.admin_override_group.setVisible(False)
            self.timing_warning_label.setVisible(False)
            self.locked_dates_warning_label.setVisible(False)
            self.additional_position_widget.setVisible(False)

    def _check_vacation_balance(self, requested_days: int):
        """Перевіряє баланс відпустки та показує попередження при недостатньому балансі."""
        staff = self._get_selected_staff()
        if not staff or requested_days == 0:
            self.balance_warning_label.setVisible(False)
            self.admin_override_group.setVisible(False)
            return

        balance = staff.vacation_balance or 0

        # Перевіряємо баланс
        balance_ok = requested_days <= balance

        # Формуємо повідомлення
        doc_type = self._get_doc_type()
        messages = []
        style = ""
        show_override = False

        if not balance_ok:
            if doc_type == DocumentType.VACATION_PAID:
                messages.append(
                    f"⚠️ Увага! Залишок відпустки: {balance} днів. "
                    f"Ви запросили {requested_days} днів."
                )
                style = """
                    background-color: #FEF3C7;
                    color: #92400E;
                    padding: 10px;
                    border-radius: 6px;
                    font-size: 12px;
                """
                # Показуємо override для балансу
                show_override = True
            else:
                messages.append(
                    f"ℹ️ Залишок відпустки: {balance} днів. "
                    f"Оформлюєте відпустку без збереження ({requested_days} днів)."
                )
                style = """
                    background-color: #DBEAFE;
                    color: #1E40AF;
                    padding: 10px;
                    border-radius: 6px;
                    font-size: 12px;
                """

        if messages:
            self.balance_warning_label.setText("\n".join(messages))
            self.balance_warning_label.setStyleSheet(style)
            self.balance_warning_label.setVisible(True)
        else:
            self.balance_warning_label.setVisible(False)

        # Показуємо override якщо є проблема з балансом
        self.admin_override_group.setVisible(show_override)
        if show_override:
            self.admin_override_checkbox.setChecked(False)

    def _check_locked_dates(self):
        """Перевіряє чи вибрані дати не перетинаються з заблокованими відпустками."""
        # Check if UI is initialized
        if not hasattr(self, 'locked_dates_warning_label'):
            return

        doc_type = self._get_doc_type()
        # Skip for term extension
        if doc_type == DocumentType.TERM_EXTENSION:
            self.locked_dates_warning_label.setVisible(False)
            return

        if not self._parsed_dates:
            self.locked_dates_warning_label.setVisible(False)
            return

        # Перевіряємо перетин з заблокованими датами
        overlapping_dates = set(self._parsed_dates) & self.booked_dates

        if overlapping_dates:
            # Знайшли перетин - показуємо попередження
            sorted_overlaps = sorted(overlapping_dates)
            if len(sorted_overlaps) == 1:
                dates_str = sorted_overlaps[0].strftime('%d.%m.%Y')
            elif len(sorted_overlaps) <= 3:
                dates_str = ", ".join(d.strftime('%d.%m') for d in sorted_overlaps)
            else:
                first = sorted_overlaps[0].strftime('%d.%m')
                last = sorted_overlaps[-1].strftime('%d.%m')
                dates_str = f"{first} - {last} ({len(sorted_overlaps)} днів)"

            # Формуємо інформацію про заблоковані відпустки
            locked_text = "<b>Відпустки з датами:</b><br>"
            for item in self.locked_info:
                locked_text += f"{item['status_icon']} {item['dates']} - {item['status_text']}<br>"

            self.locked_dates_warning_label.setText(
                f"⚠️ Увага! Обрані дати перетинаються з вже оформленими відпустками!<br>"
                f"Перетин: {dates_str}<br><br>{locked_text}"
            )
            self.locked_dates_warning_label.setVisible(True)
        else:
            self.locked_dates_warning_label.setVisible(False)

    def _check_vacation_dates_against_contract(self):
        """Перевіряє чи не виходять дати відпустки за межі контракту."""
        # Check if UI is initialized
        if not hasattr(self, 'contract_warning_label') or not hasattr(self, 'admin_override_checkbox'):
            return

        staff = self._get_selected_staff()
        if not staff or not self._parsed_dates:
            self.contract_warning_label.setVisible(False)
            self.admin_override_group.setVisible(False)
            return

        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        try:
            with get_db_context() as db:
                staff = db.query(Staff).filter(Staff.id == staff_id).first()
                if not staff:
                    self.contract_warning_label.setVisible(False)
                    self.admin_override_group.setVisible(False)
                    return

                # Allow 2 weeks before contract end for vacation
                contract_end = staff.term_end
                warning_date = contract_end - timedelta(days=14)  # 2 weeks before

                # Check if any vacation date is after warning_date
                max_vacation_date = max(self._parsed_dates)

                doc_type = self._get_doc_type()
                is_paid_vacation = doc_type == DocumentType.VACATION_PAID

                if is_paid_vacation and max_vacation_date > warning_date:
                    # Show warning with actual days until contract end
                    days_until_contract = (contract_end - date.today()).days

                    self.contract_warning_label.setText(
                        f"⚠️ Увага! Контракт закінчується {contract_end.strftime('%d.%m.%Y')}. "
                        f"Залишилось {days_until_contract} днів.\n"
                        f"Рекомендація: Спочатку оформіть продовження контракту, "
                        f"а потім відпустку."
                    )
                    self.contract_warning_label.setVisible(True)
                    self.admin_override_group.setVisible(True)
                    self.admin_override_checkbox.setChecked(False)
                else:
                    self.contract_warning_label.setVisible(False)
                    self.admin_override_group.setVisible(False)

        except Exception as e:
            self.contract_warning_label.setVisible(False)
            self.admin_override_group.setVisible(False)

    def _check_application_timing(self):
        """
        Перевіряє чи дотримано 2-тижневий термін подання заяви про відпустку.
        Показує попередження якщо заява подається менш ніж за 2 тижні до початку відпустки.
        """
        # Check if UI is initialized
        if not hasattr(self, 'timing_warning_label'):
            return

        # Check document type first - skip for term extension
        doc_type = self._get_doc_type()
        if doc_type == DocumentType.TERM_EXTENSION:
            self.timing_warning_label.setVisible(False)
            return

        staff = self._get_selected_staff()
        if not staff or not self._parsed_dates:
            # No dates selected - show general advice
            self.timing_warning_label.setText(
                "💡 Рекомендація: Заяву про відпустку бажано подавати не пізніше ніж за 2 тижні до її початку."
            )
            self.timing_warning_label.setVisible(True)
            return

        # Check timing for vacation documents
        min_start_date = min(self._parsed_dates)
        days_until_vacation = (min_start_date - date.today()).days

        if days_until_vacation < 14:
            # Less than 2 weeks - show warning
            if days_until_vacation <= 0:
                # Vacation already started or today
                timing_text = "Відпустка вже розпочалася або починається сьогодні"
            elif days_until_vacation == 1:
                timing_text = "До відпустки залишився 1 день"
            elif 2 <= days_until_vacation <= 4:
                timing_text = f"До відпустки залишилось {days_until_vacation} дні"
            else:
                timing_text = f"До відпустки залишилось {days_until_vacation} днів"

            self.timing_warning_label.setText(
                f"⚠️ {timing_text}. \n"
                f"Згідно з КЗпП, заяву про відпустку бажано подавати за 2 тижні. "
                f"Можливі затримки у погодженні."
            )
            self.timing_warning_label.setStyleSheet("""
                background-color: #FEF3C7;
                color: #92400E;
                padding: 10px;
                border-radius: 6px;
                font-size: 12px;
            """)
            self.timing_warning_label.setVisible(True)
        else:
            # More than 2 weeks - all good
            self.timing_warning_label.setVisible(False)

    def _can_create_vacation(self) -> bool:
        """Перевіряє чи можна створювати відпустку (враховує контракт, ліміт воєнного стану та override)."""
        # Check admin override first
        if not hasattr(self, 'admin_override_checkbox'):
            return True
        if self.admin_override_checkbox.isChecked():
            return True

        # Run contract check
        self._check_vacation_dates_against_contract()

        # If contract warning is visible and no override, cannot create vacation
        if hasattr(self, 'contract_warning_label') and self.contract_warning_label.isVisible():
            return False

        return True

    def _check_additional_positions(self):
        """Перевіряє чи має співробітник додаткові позиції."""
        # Check if UI is initialized
        if not hasattr(self, 'additional_position_widget'):
            return

        self.additional_position_widget.setVisible(False)
        self._additional_staff_id = None
        self._additional_position_name = None

        staff = self._get_selected_staff()
        if not staff or not self._parsed_dates:
            return

        # Only show additional position widget if current position is 1.0
        # If user is already on an additional position (rate < 1.0), hide the widget
        if float(staff.rate) != 1.0:
            return

        # Check if employee has multiple positions (from our grouped data)
        pib = self.staff_input.currentData()
        if pib and pib in self._staff_by_pib:
            positions = self._staff_by_pib[pib]

            # If more than one position, show the selector
            if len(positions) > 1:
                # Get total rate
                total_rate = sum(float(s.rate) for s in positions)

                # Show additional position widget if total rate > 1.0
                if total_rate > 1.0:
                    # Get all positions except the main one (1.0)
                    additional_positions = [s for s in positions if s.rate != Decimal("1.00")]

                    if additional_positions:
                        self._additional_staff_id = staff.id
                        self._additional_position_name = ", ".join(
                            f"{get_position_label(s.position)} ({s.rate})" for s in additional_positions
                        )

                        self.additional_position_widget.setVisible(True)
                        self.additional_position_label.setText(
                            f"Додаткова позиція: {self._additional_position_name}"
                        )

    def _open_bulk_generator(self):
        """Відкриває діалог масової генерації документів."""
        from desktop.ui.bulk_generator_dialog import BulkGeneratorDialog

        dialog = BulkGeneratorDialog(self)
        dialog.setMinimumSize(1000, 700)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh staff documents if any were created
            self._on_field_changed()

    def _generate_for_additional_position(self):
        """Автоматично створює документ відпустки для додаткової позиції."""
        if not self._additional_staff_id or not self._parsed_dates:
            return

        from backend.models.staff import Staff
        from backend.models.document import Document
        from backend.core.database import get_db_context
        from backend.services.document_service import DocumentService
        from backend.services.grammar_service import GrammarService

        try:
            with get_db_context() as db:
                # Get additional staff info
                additional_staff = db.query(Staff).filter(Staff.id == self._additional_staff_id).first()
                if not additional_staff:
                    QMessageBox.warning(self, "Помилка", "Співробітника не знайдено")
                    return

                # Check if document already exists for additional position
                start = self._parsed_dates[0]
                end = self._parsed_dates[-1]
                doc_type = self._get_doc_type()

                existing = db.query(Document).filter(
                    Document.staff_id == self._additional_staff_id,
                    Document.date_start == start,
                    Document.date_end == end,
                    Document.doc_type == doc_type
                ).first()

                if existing:
                    # Prepare staff data and render in current context
                    staff_data = {
                        'pib_nom': additional_staff.pib_nom,
                        'position': additional_staff.position,
                        'employment_type': additional_staff.employment_type.value if additional_staff.employment_type else None,
                    }
                    is_internal = additional_staff.employment_type and \
                                  additional_staff.employment_type.value == "internal"

                    # Get doc_type value
                    existing_doc_type = existing.doc_type.value if hasattr(existing.doc_type, 'value') else str(existing.doc_type)

                    # Render preview with existing document
                    self._render_additional_preview(
                        document_id=existing.id,
                        doc_type=existing_doc_type,
                        date_start=existing.date_start,
                        date_end=existing.date_end,
                        days_count=existing.days_count,
                        staff_data=staff_data,
                        is_internal=is_internal
                    )

                    # Switch to the new tab
                    if existing.id in self._additional_previews:
                        web_view, _, _ = self._additional_previews[existing.id]
                        index = self.preview_tabs.indexOf(web_view)
                        if index >= 0:
                            self.preview_tabs.setCurrentIndex(index)

                    QMessageBox.information(
                        self,
                        "Документ вже існує",
                        f"Документ для додаткової позиції вже створено: {existing.id}"
                    )
                    return

                # Check if this is "внутрішній сумісник"
                is_internal = additional_staff.employment_type and \
                              additional_staff.employment_type.value == "internal"

                # Extract staff data while still in session context
                staff_data = {
                    'pib_nom': additional_staff.pib_nom,
                    'position': additional_staff.position,
                    # Staff model doesn't have department, will be empty
                    'employment_type': additional_staff.employment_type.value if additional_staff.employment_type else None,
                }

                # Create new document for additional position
                # Рахуємо кількість обраних днів
                additional_days_count = len(self._parsed_dates)

                document = Document(
                    staff_id=self._additional_staff_id,
                    doc_type=doc_type,
                    date_start=start,
                    date_end=end,
                    days_count=additional_days_count,
                    payment_period="У першій половині місяця" if start.day <= 15 else "У другій половині місяця",
                )
                db.add(document)
                db.commit()

                # Get the new document ID
                new_doc_id = document.id

                # Create preview tab with extracted data (not session-bound objects)
                self._render_additional_preview(
                    document_id=new_doc_id,
                    doc_type=doc_type.value,
                    date_start=start,
                    date_end=end,
                    days_count=additional_days_count,
                    staff_data=staff_data,
                    is_internal=is_internal
                )

                QMessageBox.information(
                    self,
                    "Успішно",
                    f"Документ для додаткової позиції створено: ID {document.id}"
                )

                # Hide the widget since document is created
                self.additional_position_widget.setVisible(False)

        except Exception as e:
            import traceback
            error_msg = str(e) or "Невідома помилка"
            traceback.print_exc()
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити документ:\n{error_msg}")

    def _render_additional_preview(self, document_id: int, doc_type: str, date_start, date_end, days_count: int, staff_data: dict, is_internal: bool):
        """Відображає попередній перегляд документа для додаткової позиції."""
        # Create preview tab using data from dict
        web_view, bridge = self._create_preview_tab(
            staff_data['pib_nom'],
            staff_data['position'],
            is_internal=is_internal
        )

        # Store reference using staff_id as key (document_id is the key for additional_previews)
        self._additional_previews[document_id] = (web_view, None, bridge)

        # Generate context for the template using staff_data dict
        context = self._get_context_for_staff_data(
            doc_type, date_start, date_end, days_count, staff_data, is_internal
        )

        # Render document
        try:
            base_path = Path(__file__).parent.parent.parent
            templates_dir = base_path / "desktop" / "templates"
            env = Environment(
                loader=FileSystemLoader([
                    str(templates_dir),
                    str(templates_dir / "documents")
                ]),
                auto_reload=True
            )
            template = env.get_template(f"documents/{doc_type}.html")
            html_content = template.render(context)

            # Load content
            bridge.load_content(web_view, html_content)

        except Exception as e:
            import traceback
            print(f"[ERROR] _render_additional_preview: {e}")
            traceback.print_exc()

    def _get_context_for_staff_data(self, doc_type: str, date_start, date_end, days_count: int, staff_data: dict, is_internal: bool = False):
        """Генерує контекст шаблону для конкретного співробітника (з даними, без об'єкта Document)."""
        from backend.core.database import get_db_context
        from backend.models.settings import SystemSettings
        from backend.models.staff import Staff as StaffModel
        from backend.services.grammar_service import GrammarService

        # Format dates
        date_start_str = date_start.strftime("%d.%m.%Y")
        date_end_str = date_end.strftime("%d.%m.%Y")

        # Staff info - use nominative case from dict
        staff_name_nom = staff_data.get('pib_nom', '')

        # Format staff name in genitive case for header
        grammar = GrammarService()
        staff_name_gen = staff_name_nom
        if staff_name_nom:
            try:
                parts = staff_name_nom.split()
                if len(parts) >= 3:
                    # "Дмитренко Вікторія Іванівна" - Surname First Middle
                    surname = parts[0]
                    first_name = grammar.to_genitive(parts[1])
                    middle_name = grammar.to_genitive(parts[2])
                    staff_name_gen = f"{surname} {first_name} {middle_name}"
                elif len(parts) == 2:
                    surname = parts[0]
                    first_name = grammar.to_genitive(parts[1])
                    staff_name_gen = f"{surname} {first_name}"
            except Exception:
                staff_name_gen = staff_name_nom

        # Position with department from dict (use Ukrainian label)
        staff_position = get_position_label(staff_data.get('position', ''))
        staff_position_nom_full = staff_position

        # University name from settings
        university_name_raw = "Національний університет «Полтавська політехніка імені Юрія Кондратюка»"
        rector_name = "Олександра Удови"
        try:
            with get_db_context() as db:
                settings = db.query(SystemSettings).first()
                if settings and settings.university_name:
                    university_name_raw = settings.university_name
                    rector_name = settings.rector_name or rector_name
        except:
            pass

        university_name = university_name_raw
        dept_name = ""
        dept_abbr_raw = ""

        # Clean department name from dict
        department = staff_data.get('department', '')
        if department:
            import re
            dept_raw = department
            dept_clean = re.sub(r'\s*\([^)]*\)\s*', '', dept_raw).strip()
            dept_abbr_match = re.search(r'\(([^)]+)\)', dept_raw)
            if dept_abbr_match:
                dept_abbr_raw = dept_abbr_match.group(1).strip()
            dept_name = dept_clean
        else:
            dept_clean = ""

        # Department abbreviation takes precedence
        dept_for_position = dept_abbr_raw if dept_abbr_raw else dept_clean

        # Build position with department if needed
        if staff_position and dept_for_position:
            position_lower = staff_position.lower()
            if "кафедри" not in position_lower and "кафедру" not in position_lower and "кафедр" not in position_lower:
                if any(x in position_lower for x in ["професор", "доцент", "асистент", "викладач", "старший викладач", "фахівець"]):
                    staff_position_nom_full = f"{staff_position} кафедри {dept_for_position}"
                    staff_position_nom_full = staff_position_nom_full[0].upper() + staff_position_nom_full[1:] if staff_position_nom_full else ""

        # Signatories (for additional position)
        signatories = []
        staff_name_nom_lower = staff_name_nom.lower() if staff_name_nom else ""

        with get_db_context() as db:
            # Get department head
            if dept_clean:
                dept_head = db.query(StaffModel).filter(
                    StaffModel.department.ilike(f"%{dept_clean}%"),
                    StaffModel.position.ilike("%завідувач%"),
                    StaffModel.is_active == True
                ).first()

                if dept_head:
                    # Check if current staff member is the department head
                    # (avoid self-signing for additional positions)
                    head_name_parts = dept_head.pib_nom.lower().split()
                    is_dept_head = any(part in staff_name_nom_lower for part in head_name_parts[:2]) if len(head_name_parts) >= 2 else False

                    if not is_dept_head:
                        # Extract string data while in session context
                        signatories.append({
                            "position": "Завідувач кафедри",
                            "name": dept_head.pib_nom
                        })

            # Get faculty dean if available
            faculty_dean = db.query(StaffModel).filter(
                StaffModel.position.ilike("%декан%"),
                StaffModel.is_active == True
            ).first()

            if faculty_dean:
                # Check if current staff member is the dean
                dean_name_parts = faculty_dean.pib_nom.lower().split()
                is_dean = any(part in staff_name_nom_lower for part in dean_name_parts[:2]) if len(dean_name_parts) >= 2 else False

                if not is_dean:
                    # Extract string data while in session context
                    signatories.append({
                        "position": "Декан",
                        "name": faculty_dean.pib_nom
                    })

        # Format days count text (робочі дні)
        if days_count == 1:
            days_count_text = f"{days_count} робочий день"
        elif 2 <= days_count <= 4:
            days_count_text = f"{days_count} робочі дні"
        else:
            days_count_text = f"{days_count} робочих днів"

        # Payment period
        payment_period = "у першій половині місяця"
        if date_start.day > 15:
            payment_period = "у другій половині місяця"

        # Format dates for document
        formatted_dates = _format_dates_for_document(self._parsed_dates)

        # Add employment type note at the bottom of header
        employment_type_note = ""
        if is_internal:
            employment_type_note = "(внутрішнє сумісництво)"
        elif staff_data.get('employment_type') == 'external':
            employment_type_note = "(зовнішнє сумісництво)"

        return {
            "doc_type": doc_type,
            "staff_name": staff_name_nom,
            "staff_name_nom": staff_name_nom,
            "staff_name_gen": staff_name_gen,  # Genitive case for header
            "staff_position": staff_position_nom_full,
            "staff_position_nom": staff_position_nom_full.lower() if staff_position_nom_full else "",
            "date_start": date_start_str,
            "date_end": date_end_str,
            "days_count": days_count_text,
            "formatted_dates": formatted_dates,
            "payment_period": payment_period,
            "custom_text": "",
            "rector_name": rector_name,
            "university_name": university_name,
            "dept_name": dept_name,
            "signatories": signatories,
            "employment_type_note": employment_type_note,
        }

    def _get_context_for_staff(self, document, staff, is_internal: bool = False):
        """Генерує контекст шаблону для конкретного співробітника."""
        from shared.enums import EmploymentType
        from backend.models.settings import Settings
        from backend.services.grammar_service import GrammarService

        # Format dates
        date_start = document.date_start.strftime("%d.%m.%Y")
        date_end = document.date_end.strftime("%d.%m.%Y")
        days_count = document.days_count

        # Staff info - use nominative case
        staff_name_nom = staff.pib_nom

        # Format staff name in genitive case for header
        grammar = GrammarService()
        staff_name_gen = staff_name_nom
        if staff_name_nom:
            try:
                parts = staff_name_nom.split()
                if len(parts) >= 3:
                    # "Дмитренко Вікторія Іванівна" - Surname First Middle
                    surname = parts[0]
                    first_name = grammar.to_genitive(parts[1])
                    middle_name = grammar.to_genitive(parts[2])
                    staff_name_gen = f"{surname} {first_name} {middle_name}"
                elif len(parts) == 2:
                    surname = parts[0]
                    first_name = grammar.to_genitive(parts[1])
                    staff_name_gen = f"{surname} {first_name}"
            except Exception:
                staff_name_gen = staff_name_nom

        # Position with department (use Ukrainian label)
        staff_position = get_position_label(staff.position)
        staff_position_nom_full = get_position_label(staff.position)

        # University name from settings
        university_name_raw = "Національний університет «Полтавська політехніка імені Юрія Кондратюка»"
        rector_name = "Олександра Удови"
        try:
            with get_db_context() as db:
                settings = db.query(SystemSettings).first()
                if settings and settings.university_name:
                    university_name_raw = settings.university_name
                    rector_name = settings.rector_name or rector_name
        except:
            pass

        university_name = university_name_raw
        dept_name = ""
        dept_abbr_raw = ""

        # Clean department name
        if staff.department:
            import re
            dept_raw = staff.department
            dept_clean = re.sub(r'\s*\([^)]*\)\s*', '', dept_raw).strip()
            dept_abbr_match = re.search(r'\(([^)]+)\)', dept_raw)
            if dept_abbr_match:
                dept_abbr_raw = dept_abbr_match.group(1).strip()
            dept_name = dept_clean

        # Department abbreviation takes precedence
        dept_for_position = dept_abbr_raw if dept_abbr_raw else dept_clean

        # Build position with department if needed
        if staff_position and dept_for_position:
            position_lower = staff_position.lower()
            if "кафедри" not in position_lower and "кафедру" not in position_lower and "кафедр" not in position_lower:
                if any(x in position_lower for x in ["професор", "доцент", "асистент", "викладач", "старший викладач", "фахівець"]):
                    staff_position_nom_full = f"{staff_position} кафедри {dept_for_position}"
                    staff_position_nom_full = staff_position_nom_full[0].upper() + staff_position_nom_full[1:] if staff_position_nom_full else ""

        # Signatories (for additional position, same as main or can be customized)
        signatories = []
        from backend.models.staff import Staff as StaffModel
        from backend.core.database import get_db_context

        with get_db_context() as db:
            # Get department head
            dept_head = db.query(StaffModel).filter(
                StaffModel.department.ilike(f"%{dept_clean}%") if dept_clean else False,
                StaffModel.position.ilike("%завідувач%"),
                StaffModel.is_active == True
            ).first()

            if dept_head and dept_head.id != staff.id:
                signatories.append({
                    "position": "Завідувач кафедри",
                    "name": dept_head.pib_nom
                })

            # Get faculty dean if available
            faculty_dean = db.query(StaffModel).filter(
                StaffModel.position.ilike("%декан%"),
                StaffModel.is_active == True
            ).first()

            if faculty_dean:
                signatories.append({
                    "position": "Декан",
                    "name": faculty_dean.pib_nom
                })

        # Format days count text (робочі дні)
        if days_count == 1:
            days_count_text = f"{days_count} робочий день"
        elif 2 <= days_count <= 4:
            days_count_text = f"{days_count} робочі дні"
        else:
            days_count_text = f"{days_count} робочих днів"

        # Payment period
        payment_period = "у першій половині місяця"
        if document.date_start.day > 15:
            payment_period = "у другій половині місяця"

        # Format dates for document
        formatted_dates = _format_dates_for_document(self._parsed_dates)

        # Add employment type note at the bottom of header
        employment_type_note = ""
        if is_internal:
            employment_type_note = "(внутрішнє сумісництво)"
        elif staff.employment_type and staff.employment_type.value == "external":
            employment_type_note = "(зовнішнє сумісництво)"

        return {
            "doc_type": document.doc_type.value,
            "staff_name": staff.pib_nom,
            "staff_name_nom": staff_name_nom,
            "staff_name_gen": staff_name_gen,  # Genitive case for header
            "staff_position": staff_position_nom_full,
            "staff_position_nom": staff_position_nom_full.lower() if staff_position_nom_full else "",
            "date_start": date_start,
            "date_end": date_end,
            "days_count": days_count_text,
            "formatted_dates": formatted_dates,
            "payment_period": payment_period,
            "custom_text": "",
            "rector_name": rector_name,
            "university_name": university_name,
            "dept_name": dept_name,
            "signatories": signatories,
            "employment_type_note": employment_type_note,
        }

    def _open_date_range_dialog(self):
        """Відкриває діалог для вибору діапазону дат (застарілий метод)."""
        self._add_date_range()

    def _select_date_range(self):
        """Відкриває діалог для вибору діапазону дат (застарілий метод)."""
        self._open_date_range_dialog()

    def _clear_dates(self):
        """Очищає вибір дат (застарілий метод)."""
        self._parsed_dates = []
        self._update_dates_info()
        self._update_preview()


class DateRangePickerPopup(QWidget):
    """
    Простий клас для відображення віджета вибору дат як popup.

    Використовує date_range_popover з підтримкою PyQt6.
    """

    selection_complete = pyqtSignal(list)

    def __init__(self, parent=None, staff_id: int = None):
        super().__init__(parent)
        self._selected_dates: list[date] = []
        self._picker = None
        self._staff_id = staff_id
        self._setup_picker()

    def _setup_picker(self):
        """Створює і налаштовує віджет."""
        from desktop.ui.date_range_popover import DatePickerConfig, DateRangePicker, PickerMode
        from PyQt6.QtCore import QDate

        # min_date: 3 weeks ago, max_date: far future (year 2100)
        min_date = QDate.currentDate().addDays(-21)
        max_date = QDate(2100, 12, 31)

        config = DatePickerConfig(
            mode=PickerMode.CUSTOM_RANGE,
            initial_date=None,
            min_date=min_date,
            max_date=max_date,
        )

        self._picker = DateRangePicker(config=config, staff_id=self._staff_id, parent=self)

        # Підключення сигналів
        self._picker.range_selected.connect(self._on_range_selected)
        self._picker.date_selected.connect(self._on_date_selected)
        self._picker.cancelled.connect(self._on_cancelled)

        # Підключення кнопок підтвердження/скасування
        if hasattr(self._picker, '_confirm_button'):
            self._picker._confirm_button.clicked.connect(self._on_confirmed)
        if hasattr(self._picker, '_cancel_button'):
            self._picker._cancel_button.clicked.connect(self._on_cancelled)

    def show_popup(self):
        """Показує віджет як popup вікно."""
        if self._picker:
            self._picker.show()

    def close_popup(self):
        """Закриває popup."""
        if self._picker:
            self._picker.close()

    def _on_range_selected(self, date_range):
        """Обробляє вибір діапазону в календарі."""
        if date_range and date_range.start_date and date_range.end_date:
            start = date_range.start_date.toPyDate()
            end = date_range.end_date.toPyDate()

            # Генеруємо всі дати в діапазоні
            self._selected_dates = []
            current = start
            while current <= end:
                self._selected_dates.append(current)
                current += timedelta(days=1)

    def _on_date_selected(self, qdate: QDate):
        """Обробляє вибір однієї дати."""
        if qdate.isValid():
            py_date = qdate.toPyDate()
            self._selected_dates = [py_date]

    def _on_confirmed(self):
        """Обробляє підтвердження вибору."""
        self.close_popup()
        self.selection_complete.emit(self._selected_dates.copy())

    def _on_cancelled(self):
        """Обробляє скасування."""
        self._selected_dates = []
        self.close_popup()
        self.selection_complete.emit([])


class AutoDateRangeDialog(QDialog):
    """
    Діалог для автоматичного підбору дат відпустки.

    Дозволяє користувачу вказати кількість днів та побажання,
    і автоматично підбирає відповідні дати з урахуванням обмежень.
    """

    selection_complete = pyqtSignal(list)  # list of (start, end) tuples

    def __init__(self, staff_id: int, parent=None):
        super().__init__(parent)
        self.staff_id = staff_id
        self.setWindowTitle("Автоматичний підбір дат відпустки")
        self.setMinimumSize(500, 400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.locked_info = []  # Ініціалізуємо до завантаження
        self._load_staff_data()
        self._setup_ui()

    def _load_staff_data(self):
        """Завантажує дані співробітника."""
        from backend.core.database import get_db_context
        from backend.models.staff import Staff

        with get_db_context() as db:
            staff = db.query(Staff).options(joinedload(Staff.documents)).filter(Staff.id == self.staff_id).first()
            if not staff:
                self.staff_data = None
                return

            self.staff_data = {
                "pib_nom": staff.pib_nom,
                "term_end": staff.term_end,
                "vacation_balance": staff.vacation_balance,
                "is_active": staff.is_active,
            }

            # Отримуємо вже заброньовані дати
            from backend.models.document import Document
            booked_dates = set()
            locked_info = []  # Інформація про заблоковані дати
            for doc in staff.documents:
                # Блокуємо всі активні статуси крім чернетки
                # Користувач не може отримати новий відпустку на вже зайняті дати
                active_statuses = (
                    'signed_by_applicant', 'approved_by_dispatcher', 'signed_dep_head',
                    'agreed', 'signed_rector', 'scanned', 'processed'
                )
                if doc.status in active_statuses:
                    current = doc.date_start
                    while current <= doc.date_end:
                        booked_dates.add(current)
                        current += timedelta(days=1)
                    # Формуємо статус для відображення
                    status_map = {
                        'signed_by_applicant': ('підписав заявник', '✍️'),
                        'approved_by_dispatcher': ('погоджено диспетчером', '👨‍💼'),
                        'signed_dep_head': ('підписано зав. кафедри', '📋'),
                        'agreed': ('погоджено', '🤝'),
                        'signed_rector': ('підписано ректором', '🎓'),
                        'scanned': ('відскановано', '📷'),
                        'processed': ('в табелі', '📁'),
                    }
                    status_text, status_icon = status_map.get(doc.status, ('оброблено', '📋'))
                    locked_info.append({
                        'dates': f"{doc.date_start.strftime('%d.%m')} - {doc.date_end.strftime('%d.%m')}",
                        'status_text': status_text,
                        'status_icon': status_icon,
                        'doc_id': doc.id
                    })

            # Також додаємо дати з відвідуваності (крім "Р" - присутність на роботі)
            from shared.absence_types import CODE_TO_ABSENCE_NAME
            from backend.models.attendance import Attendance
            atts = db.query(Attendance).filter(
                Attendance.staff_id == self.staff_id,
                Attendance.code != "Р"
            ).all()
            for att in atts:
                att_end = att.date_end or att.date
                current = att.date
                while current <= att_end:
                    if current not in booked_dates:  # Only add if not already booked
                        booked_dates.add(current)
                    current += timedelta(days=1)
                # Get full name for the code
                code_name = CODE_TO_ABSENCE_NAME.get(att.code, att.code)
                # Add to locked_info
                locked_info.append({
                    'dates': f"{att.date.strftime('%d.%m')}" + (f" - {att_end.strftime('%d.%m')}" if att_end != att.date else ""),
                    'status_text': f"{code_name}",
                    'status_icon': "🏷️",
                    'doc_id': att.id
                })

            self.booked_dates = booked_dates
            self.locked_info = locked_info

            # Debug output
            if booked_dates:
                print(f"[DEBUG AutoDateRangeDialog] {self.staff_data['pib_nom']}: {len(booked_dates)} booked dates from {len(locked_info)} docs")
                print(f"[DEBUG] Booked dates: {sorted(list(booked_dates))[:5]}...")

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        layout = QVBoxLayout(self)

        # Інформація про співробітника
        if self.staff_data:
            info_text = f"Співробітник: {self.staff_data['pib_nom']}\n"
            info_text += f"Баланс відпустки: {self.staff_data['vacation_balance']} дн.\n"
            info_text += f"Кінець контракту: {self.staff_data['term_end'].strftime('%d.%m.%Y')}"
            info_label = QLabel(info_text)
            info_label.setStyleSheet("background-color: #E0F2FE; padding: 10px; border-radius: 5px;")
            layout.addWidget(info_label)

        # Інформація про заблоковані дати
        if hasattr(self, 'locked_info') and self.locked_info:
            locked_text = "<b>Заблоковані дати:</b><br>"
            for item in self.locked_info:
                locked_text += f"{item['status_icon']} {item['dates']} - {item['status_text']} (док. #{item['doc_id']})<br>"
            locked_label = QLabel(locked_text)
            locked_label.setStyleSheet("background-color: #FEE2E2; padding: 8px; border-radius: 5px; color: #991B1B;")
            layout.addWidget(locked_label)

        # Кількість днів
        days_layout = QHBoxLayout()
        days_layout.addWidget(QLabel("Кількість днів відпустки:"))
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setMinimum(1)
        self.days_spinbox.setMaximum(30)
        self.days_spinbox.setValue(14)
        self.days_spinbox.valueChanged.connect(self._update_preview)
        days_layout.addWidget(self.days_spinbox)
        layout.addLayout(days_layout)

        # Режим вибору дат
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(QLabel("<b>Режим вибору дат:</b>"))
        self.mode_group = QButtonGroup(self)

        self.single_range_radio = QRadioButton("Один безперервний діапазон")
        self.single_range_radio.setChecked(True)
        self.single_range_radio.toggled.connect(self._update_preview)
        mode_layout.addWidget(self.single_range_radio)
        self.mode_group.addButton(self.single_range_radio, 1)

        self.multiple_ranges_radio = QRadioButton("Кілька окремих діапазонів (наприклад, по тижнях)")
        self.multiple_ranges_radio.toggled.connect(self._update_preview)
        mode_layout.addWidget(self.multiple_ranges_radio)
        self.mode_group.addButton(self.multiple_ranges_radio, 2)

        self.single_dates_radio = QRadioButton("Окремі дні (не підряд)")
        self.single_dates_radio.toggled.connect(self._update_preview)
        mode_layout.addWidget(self.single_dates_radio)
        self.mode_group.addButton(self.single_dates_radio, 3)

        # Підказка для окремих днів
        single_dates_hint = QLabel("⚠️ Більше 5 днів не рекомендовано - документ буде заплутаним")
        single_dates_hint.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        single_dates_hint.setToolTip("Рекомендовано не більше 5 окремих днів, інакше документ виглядатиме заплутано")
        mode_layout.addWidget(single_dates_hint)

        self.mixed_radio = QRadioButton("Змішано: окремі дні та діапазони")
        self.mixed_radio.toggled.connect(self._update_preview)
        mode_layout.addWidget(self.mixed_radio)
        self.mode_group.addButton(self.mixed_radio, 4)

        # Налаштування для змішаного режиму (в контейнері)
        self.mixed_settings_widget = QWidget()
        mixed_settings_layout = QVBoxLayout(self.mixed_settings_widget)
        mixed_settings_layout.setContentsMargins(20, 5, 0, 0)  # Відступ зліва

        # Кількість окремих днів
        single_count_layout = QHBoxLayout()
        single_count_layout.addWidget(QLabel("Кількість окремих днів:"))
        self.single_count_spinbox = QSpinBox()
        self.single_count_spinbox.setMinimum(0)
        self.single_count_spinbox.setMaximum(30)
        self.single_count_spinbox.setValue(0)
        self.single_count_spinbox.valueChanged.connect(self._update_preview)
        single_count_layout.addWidget(self.single_count_spinbox)
        mixed_settings_layout.addLayout(single_count_layout)

        # Підказка про окремі дні
        single_hint = QLabel("Окремі дні повинні бути ізольовані (не сусідувати з іншими)")
        single_hint.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        single_hint.setToolTip("Дати, що йдуть підряд (напр., 6 і 7 лютого), будуть об'єднані в діапазон")
        mixed_settings_layout.addWidget(single_hint)

        # Автоматично заповнити решту діапазонами
        self.auto_fill_ranges_checkbox = QCheckBox("Автоматично заповнити решту днів діапазонами")
        self.auto_fill_ranges_checkbox.setChecked(True)
        self.auto_fill_ranges_checkbox.toggled.connect(self._update_preview)
        mixed_settings_layout.addWidget(self.auto_fill_ranges_checkbox)

        # Розмір діапазонів
        range_size_layout = QHBoxLayout()
        range_size_layout.addWidget(QLabel("Макс. днів у діапазоні:"))
        self.range_size_spinbox = QSpinBox()
        self.range_size_spinbox.setMinimum(2)
        self.range_size_spinbox.setMaximum(10)
        self.range_size_spinbox.setValue(5)
        range_size_layout.addWidget(self.range_size_spinbox)
        mixed_settings_layout.addLayout(range_size_layout)

        layout.addWidget(self.mixed_settings_widget)

        layout.addLayout(mode_layout)

        # Приховати налаштування за замовчуванням
        self._toggle_mixed_settings(False)

        # Обмеження місяців
        month_layout = QVBoxLayout()
        month_layout.addWidget(QLabel("<b>В яких місяцях:</b>"))

        # Період початку (мінімальна дата)
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Початок не раніше:"))
        self.min_date_edit = QDateEdit()
        self.min_date_edit.setCalendarPopup(True)
        self.min_date_edit.setDate(QDate.currentDate().addDays(14))  # 2 тижні від сьогодні
        self.min_date_edit.dateChanged.connect(self._update_preview)
        start_layout.addWidget(self.min_date_edit)
        month_layout.addLayout(start_layout)

        # Підказка
        hint = QLabel("Якщо в поточному місяці недостатньо днів — автоматично використаємо наступний")
        hint.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        month_layout.addWidget(hint)

        layout.addLayout(month_layout)

        # Попередження
        self.warning_label = QLabel()
        self.warning_label.setStyleSheet("color: #DC2626; font-weight: bold;")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)

        # Прев'ю результату
        preview_group = QGroupBox("Прев'ю")
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(100)
        self.preview_text.setMaximumHeight(300)
        self.preview_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_text.setPlaceholderText("Натисніть 'Підібрати' для прев'ю")
        preview_layout = QVBoxLayout()
        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # Додаємо розтяжку для вертикального розширення
        layout.setStretchFactor(preview_group, 1)

        # Кнопки
        btn_layout = QHBoxLayout()

        auto_btn = QPushButton("Підібрати дати")
        auto_btn.clicked.connect(self._auto_calculate)
        btn_layout.addWidget(auto_btn)

        btn_layout.addStretch()

        apply_btn = QPushButton("Застосувати")
        apply_btn.clicked.connect(self._apply_selection)
        btn_layout.addWidget(apply_btn)

        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # Початковий прев'ю
        self._update_preview()

    def _toggle_mixed_settings(self, visible: bool):
        """Показує/приховує налаштування змішаного режиму."""
        # Приховуємо/показуємо весь контейнер
        self.mixed_settings_widget.setVisible(visible)

    def _is_weekend(self, d: date) -> bool:
        """Перевіряє чи є день вихідним."""
        return d.weekday() >= 5  # 5 = Saturday, 6 = Sunday

    def _get_valid_dates(self, max_months: int = 3) -> list[date]:
        """
        Повертає список доступних дат для відпустки.

        Автоматично розширює на наступні місяці якщо потрібно.
        """
        if not self.staff_data:
            return []

        valid_dates = []
        contract_end = self.staff_data['term_end']
        min_date = self.min_date_edit.date().toPyDate()

        # Обмежуємо min_date датою контракту
        if min_date > contract_end:
            return []

        # Визначаємо max_date на основі max_months
        # max_months=1: до кінця поточного місяця
        # max_months=2: поточний + наступний
        # max_months=3+: до кінця контракту
        if max_months == 1:
            # До кінця поточного місяця
            if min_date.month == 12:
                last_of_month = date(min_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                last_of_month = date(min_date.year, min_date.month + 1, 1) - timedelta(days=1)
            max_date = min(last_of_month, contract_end)
        elif max_months == 2:
            # Поточний + наступний
            if min_date.month == 12:
                last_of_next_month = date(min_date.year + 1, 2, 1) - timedelta(days=1)
            elif min_date.month == 11:
                last_of_next_month = date(min_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                last_of_next_month = date(min_date.year, min_date.month + 2, 1) - timedelta(days=1)
            max_date = min(last_of_next_month, contract_end)
        else:
            # Всі доступні місяці до кінця контракту
            max_date = contract_end - timedelta(days=1)

        current = min_date
        while current <= max_date:
            # Пропускаємо вихідні
            if not self._is_weekend(current):
                # Пропускаємо вже заброньовані дати
                if current not in self.booked_dates:
                    valid_dates.append(current)
            current += timedelta(days=1)

        return valid_dates

    def _auto_calculate(self):
        """Автоматично підбирає дати."""
        mode = self.mode_group.checkedId()
        days_needed = self.days_spinbox.value()

        self.warning_label.setText("")

        # Clear previous result for regeneration
        self._result = None

        # Починаємо з поточного місяця, пропускаємо порожні місяці
        valid_dates = self._get_valid_dates(max_months=1)
        result = None

        # Пропускаємо місяці без доступних дат
        months_tried = 1
        while len(valid_dates) == 0 and months_tried <= 3:
            months_tried += 1
            valid_dates = self._get_valid_dates(max_months=months_tried)

        if not valid_dates:
            self.warning_label.setText("Немає доступних дат для відпустки в обраному періоді!")
            self.preview_text.setText("Немає доступних дат.")
            return

        # Shuffle dates for regeneration - each click gives different results
        import random
        shuffled_dates = valid_dates.copy()
        random.shuffle(shuffled_dates)

        if mode == 1:  # Один діапазон
            result = self._calculate_single_range(shuffled_dates, days_needed)

            # Expand months if needed
            while not result and months_tried < 3:
                months_tried += 1
                self.warning_label.setText(f"Недостатньо днів. Розширюємо на наступний...")
                valid_dates = self._get_valid_dates(max_months=months_tried)
                if valid_dates:
                    shuffled_dates = valid_dates.copy()
                    random.shuffle(shuffled_dates)
                    result = self._calculate_single_range(shuffled_dates, days_needed)

            # Try random search if still not found
            if not result:
                result = self._calculate_single_range_random(valid_dates, days_needed)

        elif mode == 2:  # Кілька діапазонів
            # Для кількох діапазонів перевіряємо чи достатньо робочих днів
            while len(valid_dates) < days_needed and months_tried < 3:
                months_tried += 1
                valid_dates = self._get_valid_dates(max_months=months_tried)

            if len(valid_dates) < days_needed:
                available = len(valid_dates)
                self.warning_label.setText(
                    f"Недостатньо доступних робочих днів! Потрібно: {days_needed}, доступно: {available}"
                )
                self.preview_text.setText("Немає достатньо доступних дат.")
                return

            result = self._calculate_multiple_ranges(shuffled_dates, days_needed)

        elif mode == 4:  # Змішано (окремі дні + діапазони)
            # Автоматично розширюємо місяці якщо потрібно
            while len(valid_dates) < days_needed and months_tried < 3:
                months_tried += 1
                valid_dates = self._get_valid_dates(max_months=months_tried)

            if len(valid_dates) < days_needed:
                available = len(valid_dates)
                self.warning_label.setText(
                    f"Недостатньо доступних днів! Потрібно: {days_needed}, доступно: {available}"
                )
                self.preview_text.setText("Немає достатньо доступних дат.")
                return

            result = self._calculate_mixed(shuffled_dates, days_needed)

        else:  # Окремі дні (mode == 3)
            # Автоматично розширюємо місяці якщо потрібно
            while len(valid_dates) < days_needed and months_tried < 3:
                months_tried += 1
                valid_dates = self._get_valid_dates(max_months=months_tried)

            if len(valid_dates) < days_needed:
                available = len(valid_dates)
                self.warning_label.setText(
                    f"Недостатньо доступних днів! Потрібно: {days_needed}, доступно: {available}"
                )
                self.preview_text.setText("Немає достатньо доступних дат.")
                return

            result = self._calculate_single_dates(shuffled_dates, days_needed)

        self._show_preview(result)

    def _calculate_single_range(self, valid_dates: list[date], days_needed: int) -> list[tuple]:
        """
        Підбирає один безперервний діапазон на N календарних днів.

        Правила:
        - Рахуємо календарні дні (включаючи вихідні)
        - Початок має бути робочим днем (не вихідний, не заброньований)
        - Всі дати в діапазоні НЕ МОЖУТЬ бути заброньовані
        - Кінець НЕ МОЖЕ бути вихідним
        - Діапазон МОЖЕ переходити на наступний місяць
        """
        if not valid_dates or len(valid_dates) < 1:
            return []

        possible_ranges = []
        booked_dates = self.booked_dates

        # Get the date range to search (from first valid_date to a reasonable limit)
        if not valid_dates:
            return []

        # Also get contract end to limit search
        contract_end = self.staff_data.get('term_end', date.today() + timedelta(days=365))
        search_start = valid_dates[0]
        search_end = min(contract_end, search_start + timedelta(days=180))  # Max 6 months ahead

        # Iterate through calendar dates, not just valid_dates
        # This allows us to find start dates AFTER booked periods
        current = search_start
        while current <= search_end:
            # Skip weekends and booked dates as start candidates
            if not self._is_weekend(current) and current not in booked_dates:
                # Цільова кінцева дата (включаючи вихідні)
                target_end = current + timedelta(days=days_needed - 1)

                # Якщо target_end вихідний — зсуваємо на понеділок
                end = target_end
                while self._is_weekend(end):
                    end += timedelta(days=1)

                # Перевіряємо, що ВСІ дати в діапазоні не заброньовані
                all_dates_available = True
                check_date = current
                while check_date <= end:
                    if check_date in booked_dates:
                        all_dates_available = False
                        print(f"[DEBUG] Skipping range {current}-{end}: {check_date} is booked")
                        break
                    check_date += timedelta(days=1)

                if all_dates_available:
                    # Перевіряємо що end не перевищує контракт
                    if end <= contract_end:
                        calendar_span = (end - current).days + 1
                        if calendar_span >= days_needed:
                            possible_ranges.append((current, end))

            current += timedelta(days=1)

        if not possible_ranges:
            print(f"[DEBUG] No available ranges found in {search_start} to {search_end}")
            return []

        # Вибираємо випадковий діапазон
        chosen = random.choice(possible_ranges)
        print(f"[DEBUG] Found range: {chosen[0]} - {chosen[1]}")
        return [chosen]

    def _calculate_single_range_random(self, valid_dates: list[date], days_needed: int) -> list[tuple]:
        """Випадковий пошук діапазону через комбінаторний підхід."""
        # Використовуємо той самий алгоритм що й _calculate_single_range
        return self._calculate_single_range(valid_dates, days_needed)

    def _calculate_multiple_ranges(self, valid_dates: list[date], days_needed: int) -> list[tuple]:
        """
        Підбирає кілька окремих випадкових діапазонів.

        Правила:
        - Мінімум 3 календарні дні в діапазоні
        - Діапазон НЕ МОЖЕ починатися у вихідний
        - Діапазон НЕ МОЖЕ закінчуватися у вихідний
        - Всі дати в діапазоні НЕ МОЖУТЬ бути заброньовані
        - Діапазон МОЖЕ охоплювати вихідні (напр., пт-ср = 6 днів через сб-нд)
        """
        result = []
        remaining = days_needed

        if not valid_dates or len(valid_dates) < 1:
            return result

        booked_dates = self.booked_dates
        contract_end = self.staff_data.get('term_end', date.today() + timedelta(days=365))
        search_start = valid_dates[0]
        search_end = min(contract_end, search_start + timedelta(days=180))

        # Track used dates (booked + already selected)
        used_dates = set(booked_dates)

        # Iterate through calendar dates to find start dates
        current = search_start
        max_attempts = 1000  # Safety limit
        attempts = 0

        while remaining >= 3 and current <= search_end and attempts < max_attempts:
            attempts += 1

            # Skip weekends and already used dates
            if self._is_weekend(current) or current in used_dates:
                current += timedelta(days=1)
                continue

            # Try to find a valid range starting from current
            # Target end date (calendar days)
            target_end = current + timedelta(days=2)  # At least 3 calendar days

            # Adjust end if it's a weekend
            end = target_end
            while self._is_weekend(end):
                end += timedelta(days=1)

            # Check if entire range is available
            all_available = True
            check = current
            while check <= end:
                if check in used_dates:
                    all_available = False
                    print(f"[DEBUG] Multiple ranges: skipping {current}-{end}, {check} is used")
                    break
                check += timedelta(days=1)

            if all_available and end <= contract_end:
                # Found a valid range
                calendar_days = (end - current).days + 1
                if calendar_days >= 3:
                    result.append((current, end))
                    remaining -= calendar_days

                    # Mark dates as used
                    check = current
                    while check <= end:
                        used_dates.add(check)
                        check += timedelta(days=1)

            current += timedelta(days=1)

        # Sort result by start date
        result.sort(key=lambda x: x[0])

        if not result:
            print(f"[DEBUG] No multiple ranges found")

        return result

    def _calculate_mixed(self, valid_dates: list[date], days_needed: int) -> list[tuple]:
        """
        Підбирає змішані дати: окремі дні та діапазони.

        Використовує налаштування користувача:
        - Кількість окремих днів (single_count_spinbox)
        - Автоматично заповнити решту діапазонами (auto_fill_ranges_checkbox)
        - Макс. днів у діапазоні (range_size_spinbox)
        """
        result = []
        remaining = days_needed

        # Отримуємо налаштування користувача
        user_single_count = self.single_count_spinbox.value()
        auto_fill = self.auto_fill_ranges_checkbox.isChecked()
        max_range_size = self.range_size_spinbox.value()

        # Визначаємо кількість окремих днів
        if user_single_count > 0:
            single_count = min(user_single_count, days_needed)
        else:
            # Якщо 0 і auto-fill увімкнено, всі дні будуть в діапазонах
            single_count = 0 if auto_fill else max(1, int(days_needed * 0.3))

        # Перемішуємо дати для випадковості
        shuffled = valid_dates.copy()
        random.shuffle(shuffled)

        # Знаходимо дати, які не сусідні з іншими в послідовному ряді
        # Це дні, які "виступають" з послідовності (напр., ..., 23, 24, 26, 27, ... - тут 23 і 27 ізольовані)
        sorted_dates = sorted(shuffled)
        date_set = set(sorted_dates)
        edge_dates = set()
        for d in sorted_dates:
            prev_day = d - timedelta(days=1)
            next_day = d + timedelta(days=1)
            # Дата ізольована якщо хоча б один сусід відсутній
            if prev_day not in date_set or next_day not in date_set:
                edge_dates.add(d)

        # Сортуємо edge_dates для випадкового вибору
        isolated = sorted(edge_dates, key=lambda x: random.random())

        # Беремо ізольовані дати, якщо є, інакше беремо випадкові
        actual_single_count = min(len(isolated), single_count)

        # Беремо окремі дні
        if actual_single_count > 0:
            # Спочатку ізольовані
            for d in isolated[:actual_single_count]:
                if remaining > 0:
                    result.append((d, d))
                    remaining -= 1
                    if d in shuffled:
                        shuffled.remove(d)
        elif single_count > 0:
            # Якщо немає ізольованих дат, все одно беремо випадкові окремі дні
            working_dates = [d for d in shuffled if not self._is_weekend(d)]
            working_dates = sorted(working_dates, key=lambda x: random.random())
            for d in working_dates[:single_count]:
                if remaining > 0 and d in shuffled:
                    result.append((d, d))
                    remaining -= 1
                    shuffled.remove(d)

        # Для діапазонів шукаємо по календарних днях
        # Поки потрібні дні і є доступні дати
        attempts = 0
        max_attempts = len(shuffled)  # Захист від нескінченного циклу

        while remaining >= 3 and shuffled and auto_fill and attempts < max_attempts:
            attempts += 1

            # Шукаємо діапазон по календарних днях
            found_range = None

            # Сортуємо дати для пошуку послідовних діапазонів
            sorted_dates = sorted(shuffled)

            # Шукаємо від більших діапазонів до менших (по календарних днях)
            for range_size in range(min(max_range_size, remaining), 2, -1):
                for i in range(len(sorted_dates) - range_size + 1):
                    chunk = sorted_dates[i:i + range_size]

                    # Перевіряємо що дати послідовні (різниця між сусідніми = 1 день)
                    is_consecutive = True
                    for j in range(len(chunk) - 1):
                        if (chunk[j + 1] - chunk[j]).days != 1:
                            is_consecutive = False
                            break

                    if not is_consecutive:
                        continue

                    # Перевіряємо що початок і кінець не вихідні
                    if self._is_weekend(chunk[0]) or self._is_weekend(chunk[-1]):
                        continue

                    # Перевіряємо чи всі дати робочі (в valid_dates)
                    if all(d in date_set for d in chunk):
                        found_range = chunk
                        break
                if found_range:
                    break

            if found_range:
                result.append((found_range[0], found_range[-1]))
                remaining -= len(found_range)
                # Видаляємо використані дати
                for d in found_range:
                    if d in shuffled:
                        shuffled.remove(d)
            else:
                # НЕ знайдено послідовний діапазон - шукаємо будь-який можливий
                # Сортуємо і беремо перші дати
                sorted_dates = sorted(shuffled)
                chunk = sorted_dates[:remaining][:max_range_size]
                if len(chunk) >= 2 and not self._is_weekend(chunk[0]) and not self._is_weekend(chunk[-1]):
                    result.append((chunk[0], chunk[-1]))
                    remaining -= len(chunk)
                    for d in chunk:
                        if d in shuffled:
                            shuffled.remove(d)
                else:
                    # Менше 2 дат залишилось або вони вихідні
                    break

        # Якщо залишилось менше 3 днів, додаємо як окремі
        while remaining > 0 and shuffled:
            d = shuffled.pop(0)
            if not self._is_weekend(d):
                result.append((d, d))
                remaining -= 1

        # Якщо залишились дні але auto_fill вимкнено
        if remaining > 0 and not auto_fill:
            for d in shuffled:
                if remaining <= 0:
                    break
                if not self._is_weekend(d):
                    result.append((d, d))
                    remaining -= 1

        # Сортуємо результат за датами
        result.sort(key=lambda x: x[0])

        return result

    def _calculate_single_dates(self, valid_dates: list[date], days_needed: int) -> list[tuple]:
        """
        Підбирає окремі дні (випадковий вибір).

        Вибирає тільки робочі дні (вихідні виключаються).
        Also looks for dates after booked periods.
        """
        if not valid_dates:
            return []

        # Get contract end for search limit
        contract_end = self.staff_data.get('term_end', date.today() + timedelta(days=365))
        search_start = valid_dates[0]
        search_end = min(contract_end, search_start + timedelta(days=180))

        booked_dates = self.booked_dates

        # Collect all available working dates (not weekend, not booked)
        working_dates = []
        current = search_start
        while current <= search_end and len(working_dates) < days_needed:
            if not self._is_weekend(current) and current not in booked_dates:
                working_dates.append(current)
            current += timedelta(days=1)

        if len(working_dates) <= days_needed:
            selected = working_dates.copy()
        else:
            selected = random.sample(working_dates, days_needed)
            selected.sort()

        result = [(d, d) for d in selected]
        return result

    def _show_preview(self, result: list[tuple]):
        """Показує прев'ю результату."""
        if not result:
            self.preview_text.setText("Не вдалося підібрати дати. Спробуйте змінити параметри.")
            return

        mode = self.mode_group.checkedId()
        text_parts = []
        total_working_days = 0

        for i, (start, end) in enumerate(result, 1):
            # Рахуємо робочі дні від початку до кінця
            working_days = 0
            current = start
            while current <= end:
                if current.weekday() < 5:  # Не вихідний
                    working_days += 1
                current += timedelta(days=1)

            total_working_days += working_days

            if mode == 1:  # Один діапазон - показуємо календарні дні
                calendar_days = (end - start).days + 1
                text_parts.append(f"{i}. {start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')} ({calendar_days} календарних днів, {working_days} робочих)")
            else:
                text_parts.append(f"{i}. {start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')} ({working_days} роб. дн.)")

        if mode == 1:  # Один діапазон
            text = f"<b>Знайдено 1 діапазон ({total_working_days} робочих днів):</b><br><br>"
        else:
            text = f"<b>Знайдено {len(result)} діапазон(и), {total_working_days} робочих днів:</b><br><br>"

        text += "<br>".join(text_parts)

        self.preview_text.setText(text)
        self._result = result

    def _update_preview(self):
        """Оновлює прев'ю при зміні параметрів."""
        self.warning_label.setText("")
        self.preview_text.setText("Натисніть 'Підібрати' для прев'ю")

        # Показуємо/приховуємо налаштування змішаного режиму
        mode = self.mode_group.checkedId()
        self._toggle_mixed_settings(mode == 4)

    def _apply_selection(self):
        """Застосовує вибір."""
        if hasattr(self, '_result') and self._result:
            self.selection_complete.emit(self._result)
            self.accept()
        else:
            QMessageBox.warning(self, "Попередження", "Спочатку підберіть дати!")
