"""Вкладка конструктора заяв з WYSIWYG редактором."""

import json
from datetime import date, timedelta
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
    QSplitter,
    QMessageBox,
    QProgressDialog,
    QToolBar,
    QStyle,
    QLineEdit,
    QCalendarWidget,
    QTableView,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QDate
from PyQt6.QtGui import QColor, QTextCharFormat, QBrush
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from jinja2 import Environment, FileSystemLoader

from shared.enums import DocumentType, DocumentStatus
from desktop.ui.wysiwyg_bridge import WysiwygBridge, WysiwygEditorState


class BuilderTab(QWidget):
    """
    Вкладка для створення заяв на відпустку з WYSIWYG редактором.

    Містить форму введення даних та інтерактивний редактор документа.
    """

    document_created = pyqtSignal()
    document_updated = pyqtSignal(int)  # document_id

    def __init__(self):
        """Ініціалізує вкладку конструктора."""
        super().__init__()
        self._current_document_id: int | None = None
        self._current_status = DocumentStatus.DRAFT
        self._editor_state = WysiwygEditorState()
        self._parsed_dates: list[date] = []  # Список розпізнаних дат
        self._setup_ui()

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

        # Зберегти чернетку
        save_draft_btn = QPushButton("💾 Зберегти чернетку")
        save_draft_btn.clicked.connect(self._save_draft)
        save_draft_btn.setToolTip("Зберегти поточний стан як чернетку")
        toolbar.addWidget(save_draft_btn)

        toolbar.addSeparator()

        # Оновити прев'ю
        refresh_btn = QPushButton("🔄 Оновити")
        refresh_btn.clicked.connect(self._update_preview)
        toolbar.addWidget(refresh_btn)

        # Сбросити зміни
        reset_btn = QPushButton("↶ Сбросити")
        reset_btn.clicked.connect(self._reset_changes)
        reset_btn.setToolTip("Сбросити всі зміни в редакторі")
        toolbar.addWidget(reset_btn)

        toolbar.addSeparator()

        # Друкувати
        print_btn = QPushButton("🖨 Друк")
        print_btn.clicked.connect(self._print_document)
        toolbar.addWidget(print_btn)

        # Згенерувати DOCX
        self.generate_btn = QPushButton("📄 Згенерувати DOCX")
        self.generate_btn.clicked.connect(self._generate_document)
        self.generate_btn.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; font-weight: bold; padding: 8px 16px; }"
        )
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
        staff_group = QGroupBox("👤 Співробітник")
        staff_layout = QFormLayout()

        self.staff_input = QComboBox()
        self.staff_input.currentIndexChanged.connect(self._on_field_changed)
        staff_layout.addRow("ПІБ:", self.staff_input)

        self.staff_info_label = QLabel()
        self.staff_info_label.setWordWrap(True)
        staff_layout.addRow(self.staff_info_label)

        # Load staff after creating the label
        self._load_staff()

        staff_group.setLayout(staff_layout)
        layout.addWidget(staff_group)

        # Тип документа
        doc_group = QGroupBox("📋 Тип документа")
        doc_layout = QVBoxLayout()

        self.doc_type_group = QButtonGroup()
        self.doc_type_paid = QRadioButton("✓ Відпустка оплачувана")
        self.doc_type_unpaid = QRadioButton("✓ Відпустка без збереження")
        self.doc_type_extension = QRadioButton("✓ Продовження контракту")

        self.doc_type_paid.setChecked(True)
        self.doc_type_group.addButton(self.doc_type_paid, 1)
        self.doc_type_group.addButton(self.doc_type_unpaid, 2)
        self.doc_type_group.addButton(self.doc_type_extension, 3)

        self.doc_type_group.buttonClicked.connect(self._on_field_changed)

        doc_layout.addWidget(self.doc_type_paid)
        doc_layout.addWidget(self.doc_type_unpaid)
        doc_layout.addWidget(self.doc_type_extension)

        doc_group.setLayout(doc_layout)
        layout.addWidget(doc_group)

        # Дати - кнопка для відкриття діалогу вибору дати
        date_group = QGroupBox("📅 Вибір дат відпустки")
        date_layout = QVBoxLayout()

        # Інформація про вибрані дати
        self.dates_info_label = QLabel("Не вибрано")
        self.dates_info_label.setStyleSheet("color: #666; font-size: 12px; padding: 10px;")
        date_layout.addWidget(self.dates_info_label)

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
        add_range_btn = QPushButton("Додати діапазон")
        add_range_btn.clicked.connect(self._add_date_range)
        buttons_layout.addWidget(add_range_btn)

        clear_ranges_btn = QPushButton("Очистити все")
        clear_ranges_btn.clicked.connect(self._clear_all_ranges)
        buttons_layout.addWidget(clear_ranges_btn)

        date_layout.addLayout(buttons_layout)

        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        # Оплата - завжди автоматична (приховано)
        self._payment_is_automatic = True

        layout.addStretch()

        return panel

    def _create_wysiwyg_panel(self) -> QWidget:
        """Створює панель WYSIWYG редактора."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Заголовок
        header = QLabel("📝 Візуальний редактор документа")
        header.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(header)

        # WebEngineView з JavaScript мостом
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

        layout.addWidget(self.web_view)

        # Інструкція
        help_label = QLabel(
            "💡 Підказка: Клікніть на будь-який блок тексту для редагування. "
            "Використовуйте панель інструментів для форматування."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        layout.addWidget(help_label)

        return panel

    def _load_staff(self):
        """Завантажує список співробітників."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            staff_list = (
                db.query(Staff)
                .filter(Staff.is_active == True)
                .order_by(Staff.pib_nom)
                .all()
            )

            self.staff_input.clear()
            for staff in staff_list:
                self.staff_input.addItem(staff.pib_nom, staff.id)

        self._update_staff_info()

    def _update_staff_info(self):
        """Оновлює інформацію про співробітника."""
        if not hasattr(self, 'staff_input') or not hasattr(self, 'staff_info_label'):
            return
        staff_id = self.staff_input.currentData()
        if staff_id:
            from backend.models.staff import Staff
            from backend.core.database import get_db_context

            with get_db_context() as db:
                staff = db.query(Staff).filter(Staff.id == staff_id).first()
                if staff:
                    # Перевіряємо термін контракту
                    from datetime import timedelta
                    days_until_expiry = (staff.term_end - date.today()).days

                    info_text = (
                        f"Посада: {staff.position}\n"
                        f"Ставка: {staff.rate}\n"
                        f"Баланс: {staff.vacation_balance} днів\n"
                        f"Тип: {self._get_employment_type_label(staff.employment_type.value)}\n"
                        f"Контракт до: {staff.term_end.strftime('%d.%m.%Y')}"
                    )

                    # Додаємо попередження про закінчення контракту
                    if days_until_expiry <= 30:
                        info_text += f"\n⚠️ Контракт закінчується через {days_until_expiry} днів!"

                    self.staff_info_label.setText(info_text)

    def _get_employment_type_label(self, value: str) -> str:
        """Повертає українську назву типу працевлаштування."""
        labels = {
            "main": "Основне місце роботи",
            "internal": "Внутрішній сумісник",
            "external": "Зовнішній сумісник",
        }
        return labels.get(value, value)

    def _get_doc_type(self) -> DocumentType:
        """Повертає обраний тип документа."""
        if not hasattr(self, 'doc_type_group'):
            return DocumentType.VACATION_PAID
        checked = self.doc_type_group.checkedButton()
        if checked == self.doc_type_unpaid:
            return DocumentType.VACATION_UNPAID
        elif checked == self.doc_type_extension:
            return DocumentType.TERM_EXTENSION
        return DocumentType.VACATION_PAID

    def _on_field_changed(self):
        """Обробляє зміну будь-якого поля."""
        if hasattr(self, 'staff_info_label'):
            self._update_staff_info()
        # Оновлюємо прев'ю при зміні
        if hasattr(self, 'web_view'):
            self._update_preview()

    def _update_payment_period(self):
        """Період оплати завжди автоматичний (застарілий метод)."""
        # Оплата завжди автоматична - більше не потрібно
        pass

    def _get_doc_type(self) -> DocumentType:
        """
        Повертає обраний тип документа.

        Returns:
            Тип документа з enum DocumentType
        """
        checked = self.doc_type_group.checkedButton()
        if checked == self.doc_type_unpaid:
            return DocumentType.VACATION_UNPAID
        elif checked == self.doc_type_extension:
            return DocumentType.TERM_EXTENSION
        return DocumentType.VACATION_PAID

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
                ])
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
            QTimer.singleShot(100, lambda: self.wysiwyg_bridge.set_document_status(
                self.web_view,
                self._current_status.value,
                self._get_status_label()
            ))

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
        staff_id = self.staff_input.currentData()
        from backend.models.staff import Staff
        from backend.models.settings import SystemSettings, Approvers
        from backend.core.database import get_db_context
        from backend.services.grammar_service import GrammarService

        grammar = GrammarService()
        staff_name = ""
        staff_position = ""
        rector_name = ""
        university_name = ""
        dept_name = ""
        signatories = []

        if staff_id:
            with get_db_context() as db:
                staff = db.query(Staff).filter(Staff.id == staff_id).first()
                if staff:
                    staff_name = staff.pib_nom  # Will be formatted to genitive below
                    staff_position = staff.position  # Will be formatted to genitive below
                    print(f"DEBUG: Staff data - ID: {staff.id}, Name: {staff_name}, Position: {staff_position}")

                # Отримуємо налаштування
                rector_name_dative = SystemSettings.get_value(db, "rector_name_dative", "")
                rector_name_nominative = SystemSettings.get_value(db, "rector_name_nominative", "")
                dept_name_raw = SystemSettings.get_value(db, "dept_name", "")
                dept_abbr_raw = SystemSettings.get_value(db, "dept_abbr", "")
                university_name_raw = SystemSettings.get_value(db, "university_name", "")

                print(f"DEBUG: Raw settings - rector_dative: '{rector_name_dative}', rector_nom: '{rector_name_nominative}', university: '{university_name_raw}', dept: '{dept_name_raw}'")

                # Форматуємо ім'я ректора: "Олені ФІЛОНИЧ" (ім'я в давальному + ПРІЗВИЩЕ в називному caps)
                if rector_name_nominative:
                    parts = rector_name_nominative.split()
                    # Обробляємо різні формати імен
                    if len(parts) == 2:
                        # "Ім'я Прізвище"
                        first_name = grammar.to_dative(parts[0])
                        last_name = parts[1].upper()
                        rector_name = f"{first_name} {last_name}"
                    elif len(parts) >= 3:
                        # "Ім'я По-батькові Прізвище" або "Прізвище Ім'я По-батькові"
                        # Припускаємо, що якщо перше слово закінчується на -а, -я, -я - це жіноче ім'я
                        if parts[0].endswith(('а', 'я', 'я')):
                            # "Вікторія Іванівна Філонич" - First Middle Last
                            first_name = grammar.to_dative(parts[0])
                            last_name = parts[-1].upper()  # Last word is surname
                            rector_name = f"{first_name} {last_name}"
                        else:
                            # "Філонич Вікторія Іванівна" - Last First Middle
                            # Find the first name (usually second word, ends with а/я)
                            for i, part in enumerate(parts[1:], 1):
                                if part.endswith(('а', 'я', 'я')) and not part.endswith(('вна', 'вич', 'ська', 'цька')):
                                    first_name = grammar.to_dative(part)
                                    last_name = parts[0].upper()
                                    rector_name = f"{first_name} {last_name}"
                                    break
                            else:
                                # Fallback - use dative from settings
                                rector_name = rector_name_dative
                    else:
                        rector_name = rector_name_dative
                else:
                    rector_name = rector_name_dative

                # University name - already in genitive from settings
                university_name = university_name_raw

                # Dept name - keep as is
                dept_name = dept_name_raw

                print(f"DEBUG: Formatted - University: '{university_name}', Rector: '{rector_name}', Dept: '{dept_name}'")

                # Отримуємо погоджувачів з таблиці Approvers
                approvers = (
                    db.query(Approvers)
                    .order_by(Approvers.order_index)
                    .all()
                )

                for approver in approvers:
                    # Format the signatory name: "Ім'я ПРІЗВИЩЕ" or "Ім'я По-батькові ПРІЗВИЩЕ"
                    # Приклад: "Василь САВИК" or "Сергій ГАВРИК"
                    display_name = self._format_signatory_name(approver.full_name_nom or approver.full_name_dav)

                    # Format position with abbreviation if available
                    position = approver.position_name
                    position_multiline = ""
                    if dept_abbr_raw:
                        position_multiline = dept_abbr_raw

                    signatories.append({
                        "position": position,
                        "position_multiline": position_multiline,
                        "name": display_name
                    })

                print(f"DEBUG: Loaded signatories from Approvers table: {signatories}")

                # Завідувач кафедри - додаємо автоматично, якщо є і ще не в списку
                dept_head_id = SystemSettings.get_value(db, "dept_head_id", None)
                if dept_head_id and staff and staff.id != dept_head_id:
                    head = db.query(Staff).filter(Staff.id == dept_head_id).first()
                    if head:
                        # Перевіряємо, чи вже не є в списку (порівнюємо відформатовані імена)
                        head_name_formatted = self._format_signatory_name(head.pib_nom)
                        already_exists = any(s.get("name") == head_name_formatted for s in signatories)
                        if not already_exists:
                            # Format position with abbreviation if available
                            position = head.position
                            position_multiline = ""
                            if dept_abbr_raw:
                                position_multiline = dept_abbr_raw

                            signatories.insert(0, {
                                "position": position,
                                "position_multiline": position_multiline,
                                "name": head_name_formatted
                            })
                            print(f"DEBUG: Added dept head to signatories: {head_name_formatted}")

                print(f"DEBUG: Final signatories list: {signatories}")

        # Форматуємо дані заявника (давальний/родовий відмінок)
        # Для прикладу "Професора кафедри нафтогазової інженерії та технологій" + "Цвєтковіча Браніміра"
        print(f"DEBUG: Formatting applicant - staff_position: '{staff_position}', dept_name: '{dept_name}'")

        # Очищаємо назву кафедри від "кафедри"/"кафедра" якщо вона там є
        dept_clean = dept_name
        if dept_name:
            # Видаляємо всі варіанти "кафедра"/"кафедри" на початку (case-insensitive)
            dept_lower = dept_name.lower().strip()
            print(f"DEBUG: Stripping dept_name - original: '{dept_name}', lower: '{dept_lower}'")
            if dept_lower.startswith("кафедри "):
                dept_clean = dept_name[8:]  # Remove "кафедри " (8 chars including space)
                print(f"DEBUG: Matched 'кафедри ', stripped to: '{dept_clean}'")
            elif dept_lower.startswith("кафедра "):
                dept_clean = dept_name[8:]  # Remove "кафедра " (8 chars including space)
                print(f"DEBUG: Matched 'кафедра ', stripped to: '{dept_clean}'")
            elif dept_lower.startswith("кафедри"):
                dept_clean = dept_name[7:]  # Remove "кафедри"
                print(f"DEBUG: Matched 'кафедри', stripped to: '{dept_clean}'")
            elif dept_lower.startswith("кафедра"):
                dept_clean = dept_name[7:]  # Remove "кафедра"
                print(f"DEBUG: Matched 'кафедра', stripped to: '{dept_clean}'")

        # Additional safety - strip any remaining leading/trailing whitespace
        if dept_clean:
            dept_clean = dept_clean.strip()

        print(f"DEBUG: dept_clean FINAL: '{dept_clean}'")

        # Спочатку об'єднуємо посаду з назвою кафедри ( якщо потрібно )
        if staff_position and dept_clean:
            position_lower = staff_position.lower()
            print(f"DEBUG: position_lower: '{position_lower}'")

            # Якщо посаду вже містить "кафедри", "кафедру" (завідувача кафедри), просто додаємо назву кафедри без повторення
            if "кафедри" in position_lower or "кафедру" in position_lower or "кафедр" in position_lower:
                # Видаляємо зайві пробіли та додаємо назву кафедри
                staff_position_full = f"{staff_position} {dept_clean}"
            # Якщо це професор/доцент без згадки кафедри, додаємо "кафедри"
            elif any(x in position_lower for x in ["професор", "доцент", "асистент", "викладач", "старший викладач"]):
                staff_position_full = f"{staff_position} кафедри {dept_clean}"
            else:
                staff_position_full = staff_position
        elif staff_position:
            staff_position_full = staff_position
        else:
            staff_position_full = ""

        print(f"DEBUG: staff_position_full BEFORE genitive: '{staff_position_full}'")

        # Тепер перетворюємо в родовий відмінок (GrammarService тепер обробляє це коректно)
        if staff_position_full:
            try:
                # Очищаємо кеш перед використанням, щоб отримати свіжі результати
                grammar.clear_cache()
                staff_position_gen = grammar.to_genitive(staff_position_full)
                staff_position_display = staff_position_gen
                print(f"DEBUG: Applied genitive: '{staff_position_full}' → '{staff_position_display}'")
            except Exception as e:
                print(f"DEBUG: Error in genitive conversion: {e}")
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
                print(f"DEBUG: Error converting name to genitive: {e}")
                staff_name_display = staff_name
        else:
            staff_name_display = staff_name

        # Форматуємо дати для контексту
        date_start = ""
        date_end = ""
        days_count = 0
        days_count_text = "0 днів"

        if self._parsed_dates:
            date_start = self._parsed_dates[0].strftime("%d.%m.%Y")
            date_end = self._parsed_dates[-1].strftime("%d.%m.%Y")
            days_count = len(self._parsed_dates)
            # Правильна українська граматика
            if days_count == 1:
                days_count_text = f"{days_count} календарний день"
            elif days_count % 10 == 1 and days_count % 100 != 11:
                days_count_text = f"{days_count} календарний день"
            elif 2 <= days_count % 10 <= 4 and not (12 <= days_count % 100 <= 14):
                days_count_text = f"{days_count} календарні дні"
            else:
                days_count_text = f"{days_count} календарних днів"

        # Оплата - завжди автоматично
        payment_period = "у першій половині серпня 2025 року"
        if self._parsed_dates:
            start = self._parsed_dates[0]
            month_names = {
                1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
                5: "травня", 6: "червня", 7: "липня", 8: "серпня",
                9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
            }
            month_name = month_names.get(start.month, "місяця")
            half = "першій" if start.day <= 15 else "другій"
            payment_period = f"у {half} половині {month_name} {start.year} року"

        return {
            "doc_type": self._get_doc_type().value,
            "staff_name": staff_name_display,
            "staff_position": staff_position_display,
            "date_start": date_start,
            "date_end": date_end,
            "days_count": days_count_text,
            "payment_period": payment_period,
            "custom_text": "",  # Custom text can be added later
            # Для шаблону
            "rector_name": rector_name,
            "university_name": university_name,
            "dept_name": dept_name,
            "signatories": signatories,
        }

    def _get_status_label(self) -> str:
        """Повертає текстову мітку статусу."""
        status_labels = {
            DocumentStatus.DRAFT: "Чернетка",
            DocumentStatus.ON_SIGNATURE: "На підписі",
            DocumentStatus.SIGNED: "Підписано",
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
        # Експортуємо контент з JavaScript
        self.wysiwyg_bridge.export_content(self.web_view)

        QMessageBox.information(
            self,
            "Чернетку збережено",
            "Чернетку документа успішно збережено."
        )

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
        """Друкує документ."""
        self.web_view.page().print()

    def _generate_document(self):
        """Генерує документ."""
        from backend.services.document_service import DocumentService
        from backend.services.grammar_service import GrammarService
        from backend.services.validation_service import ValidationService
        from backend.models.document import Document
        from backend.models.staff import Staff
        from backend.core.database import get_db_context
        from shared.exceptions import ValidationError
        from PyQt6.QtCore import Qt

        # Валідація
        staff_id = self.staff_input.currentData()
        if not staff_id:
            QMessageBox.warning(self, "Помилка", "Не обрано співробітника")
            return

        if not self._parsed_dates:
            QMessageBox.warning(self, "Помилка", "Не введено дати відпустки")
            return

        start = self._parsed_dates[0]
        end = self._parsed_dates[-1]
        days_count = len(self._parsed_dates)
        doc_type = self._get_doc_type()

        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff:
                QMessageBox.warning(self, "Помилка", "Співробітника не знайдено")
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

                    document.date_start = start
                    document.date_end = end
                    document.days_count = days_count
                    # Оплата - завжди автоматично
                    payment_period = "У першій половині місяця"
                    if start.day > 15:
                        payment_period = "У другій половині місяця"
                    document.payment_period = payment_period
                else:
                    # Створюємо новий документ
                    # Оплата - завжди автоматично
                    payment_period = "У першій половині місяця"
                    if start.day > 15:
                        payment_period = "У другій половині місяця"

                    document = Document(
                        staff_id=staff_id,
                        doc_type=doc_type,
                        date_start=start,
                        date_end=end,
                        days_count=days_count,
                        payment_period=payment_period,
                    )
                    db.add(document)

                db.commit()
                db.refresh(document)

                progress.setValue(50)

                # Зберігаємо стан редактора
                self._save_editor_state(db, document)

                # Генерація .docx
                grammar = GrammarService()
                doc_service = DocumentService(db, grammar)

                file_path = doc_service.generate_document(document)
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
        # Експортуємо контент з JavaScript
        self.wysiwyg_bridge.export_content(self.web_view)

        # Зберігаємо в додаткове поле документа (якщо є)
        # Для цього можна додати поле editor_state в модель Document
        # Поки що просто зберігаємо в пам'яті
        pass

    def _update_ui_status(self):
        """Оновлює UI відповідно до статусу документа."""
        self.status_label.setText(f"Статус: {self._get_status_label()}")

        # Оновлюємо колір статусу
        colors = {
            DocumentStatus.DRAFT: "#3B82F6",
            DocumentStatus.ON_SIGNATURE: "#F59E0B",
            DocumentStatus.SIGNED: "#10B981",
            DocumentStatus.PROCESSED: "#047857",
        }
        self.status_label.setStyleSheet(
            f"font-weight: bold; color: {colors.get(self._current_status, '#666')};"
        )

        # Показуємо/ховаємо кнопку відкликання
        self.rollback_btn.setVisible(
            self._current_document_id is not None and
            self._current_status in (DocumentStatus.ON_SIGNATURE, DocumentStatus.SIGNED)
        )

        # Оновлюємо статус в редакторі
        self.wysiwyg_bridge.set_document_status(
            self.web_view,
            self._current_status.value,
            self._get_status_label()
        )

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

    def load_document(self, document_id: int):
        """
        Завантажує існуючий документ в редактор.

        Args:
            document_id: ID документа
        """
        from backend.models.document import Document
        from backend.core.database import get_db_context

        with get_db_context() as db:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                QMessageBox.warning(self, "Помилка", "Документ не знайдено")
                return

            # Встановлюємо дані форми
            staff_index = self.staff_input.findData(document.staff_id)
            if staff_index >= 0:
                self.staff_input.setCurrentIndex(staff_index)

            # Тип документа
            if document.doc_type == DocumentType.VACATION_PAID:
                self.doc_type_paid.setChecked(True)
            elif document.doc_type == DocumentType.VACATION_UNPAID:
                self.doc_type_unpaid.setChecked(True)
            elif document.doc_type == DocumentType.TERM_EXTENSION:
                self.doc_type_extension.setChecked(True)

            # Дати - завантажуємо як один діапазон
            self._date_ranges = [(document.date_start, document.date_end)]
            self._update_ranges_list()
            self._update_dates_info()

            # Статус
            self._current_document_id = document.id
            self._current_status = document.status

            self._update_ui_status()
            self._update_preview()

    def clear_form(self):
        """Очищає форму для створення нового документа."""
        self._current_document_id = None
        self._current_status = DocumentStatus.DRAFT
        self._editor_state.clear()
        self._parsed_dates = []

        # Скидаємо поля форми
        if self.staff_input.count() > 0:
            self.staff_input.setCurrentIndex(0)
        self.doc_type_paid.setChecked(True)

        # Очищаємо дати
        self._date_ranges = []
        self._update_ranges_list()
        self.dates_info_label.setText("Не вибрано")

        self._update_ui_status()
        self._update_preview()

    def refresh(self):
        """Оновлює дані вкладки (перезавантажує список співробітників)."""
        # Перезавантажуємо список співробітників
        current_staff_id = self.staff_input.currentData()
        self._load_staff()
        if current_staff_id:
            index = self.staff_input.findData(current_staff_id)
            if index >= 0:
                self.staff_input.setCurrentIndex(index)

    def _add_date_range(self):
        """Відкриває popup для додавання діапазону дат."""
        popup = DateRangePickerPopup(self)
        popup.selection_complete.connect(self._on_popup_selection_complete)
        popup.show_popup()

        # Зберігаємо посилання на popup щоб він не був видалений
        self._current_popup = popup

    def _on_popup_selection_complete(self, dates: list[date]):
        """Обробляє завершення вибору в popup."""
        if dates:
            start = dates[0]
            end = dates[-1]
            self._date_ranges.append((start, end))
            self._update_ranges_list()
            self._update_dates_info()
            self._update_preview()
        # Очищаємо посилання на popup
        self._current_popup = None

    def _clear_all_ranges(self):
        """Очищає всі діапазони."""
        self._date_ranges = []
        self._update_ranges_list()
        self._update_dates_info()
        self._update_preview()

    def _remove_range(self, index: int):
        """Видаляє діапазон за індексом."""
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

            # Кнопка видалення
            remove_btn = QPushButton("✕")
            remove_btn.setFixedSize(24, 24)
            remove_btn.setStyleSheet("QPushButton { color: #dc3545; font-weight: bold; }")
            remove_btn.clicked.connect(lambda checked, idx=i: self._remove_range(idx))
            range_layout.addWidget(remove_btn)

            self._ranges_layout.addWidget(range_widget)

    def _update_dates_info(self):
        """Оновлює інформацію про вибрані дати."""
        if not self._date_ranges:
            self.dates_info_label.setText("Не вибрано")
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

        days_count = len(all_dates)
        range_count = len(self._date_ranges)
        self.dates_info_label.setText(f"✓ Вибрано: {days_count} днів ({range_count} діапазонів)")

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_dates: list[date] = []
        self._picker = None
        self._setup_picker()

    def _setup_picker(self):
        """Створює і налаштовує віджет."""
        from date_range_popover import DatePickerConfig, DateRangePicker, PickerMode
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

        self._picker = DateRangePicker(config=config)

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
