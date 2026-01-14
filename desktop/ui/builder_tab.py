"""Вкладка конструктора заяв з WYSIWYG редактором."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QWidget,
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
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
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

        # Toolbar для швидких дій
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Splitter для форми та прев'ю
        splitter = QSplitter(Qt.Orientation.Horizontal)

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

        # Дати - календар
        date_group = QGroupBox("📅 Вибір дат відпустки")
        date_layout = QVBoxLayout()

        # Інструкція
        date_help = QLabel("Клікніть на дати в календарі для вибору.\nCtrl+клік - для вибору кількох дат.")
        date_help.setWordWrap(True)
        date_help.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        date_layout.addWidget(date_help)

        # Календар з можливістю вибору кількох дат
        self.calendar = MultiSelectCalendar()
        self.calendar.selectionChanged.connect(self._on_calendar_selection_changed)
        date_layout.addWidget(self.calendar)

        # Кнопки швидкого вибору
        quick_buttons_layout = QHBoxLayout()

        select_range_btn = QPushButton("Вибрати діапазон")
        select_range_btn.clicked.connect(self._select_date_range)
        quick_buttons_layout.addWidget(select_range_btn)

        clear_dates_btn = QPushButton("Очистити")
        clear_dates_btn.clicked.connect(self._clear_dates)
        quick_buttons_layout.addWidget(clear_dates_btn)

        date_layout.addLayout(quick_buttons_layout)

        # Інформація про вибрані дати
        self.dates_info_label = QLabel("Вибрано: 0 днів")
        self.dates_info_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        date_layout.addWidget(self.dates_info_label)

        # Попередження про вихідні
        self.weekend_warning_label = QLabel("")
        self.weekend_warning_label.setWordWrap(True)
        self.weekend_warning_label.setStyleSheet("color: #F59E0B; font-size: 11px; padding: 5px;")
        date_layout.addWidget(self.weekend_warning_label)

        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        # Оплата
        payment_group = QGroupBox("💰 Оплата")
        payment_layout = QFormLayout()

        self.payment_input = QComboBox()
        self.payment_input.addItems([
            "У першій половині місяця",
            "У другій половині місяця",
        ])
        payment_layout.addRow("Період:", self.payment_input)

        # Автоматичний розрахунок
        self.auto_payment_cb = QComboBox()
        self.auto_payment_cb.addItems([
            "Автоматично (за датою)",
            "Вручну",
        ])
        self.auto_payment_cb.setCurrentIndex(0)
        self.auto_payment_cb.currentIndexChanged.connect(self._on_auto_payment_changed)
        payment_layout.addRow("Розрахунок:", self.auto_payment_cb)

        payment_group.setLayout(payment_layout)
        layout.addWidget(payment_group)

        # Кастомний текст
        text_group = QGroupBox("✏️ Додатковий текст")
        text_layout = QVBoxLayout()

        self.custom_text_input = QTextEdit()
        self.custom_text_input.setPlaceholderText(
            "Введіть додатковий текст для документа (опціонально)\n"
            "Наприклад: причину відпустки або додаткові умови"
        )
        self.custom_text_input.setMaximumHeight(100)
        self.custom_text_input.textChanged.connect(self._on_text_changed)
        text_layout.addWidget(self.custom_text_input)

        text_group.setLayout(text_layout)
        layout.addWidget(text_group)

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

        # Налаштування WebChannel для взаємодії з JavaScript
        self.web_channel = QWebChannel()
        self.wysiwyg_bridge = WysiwygBridge(self)

        # Підключаємо сигнали
        self.wysiwyg_bridge.content_changed.connect(self._on_editor_content_changed)

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
        if hasattr(self, 'auto_payment_cb'):
            self._update_payment_period()
        # Оновлюємо прев'ю при зміні
        if hasattr(self, 'web_view'):
            self._update_preview()

    def _on_text_changed(self):
        """Обробляє зміну тексту."""
        # Оновлюємо тільки кастомний текст блок без повного перезавантаження
        self._update_custom_text_block()

    def _on_auto_payment_changed(self):
        """Обробляє зміну способу розрахунку оплати."""
        is_auto = self.auto_payment_cb.currentIndex() == 0
        self.payment_input.setEnabled(not is_auto)
        if is_auto:
            self._update_payment_period()
            self._update_preview()

    def _update_payment_period(self):
        """Оновлює період оплати автоматично."""
        if self.auto_payment_cb.currentIndex() == 0 and self._parsed_dates:  # Автоматично
            start = self._parsed_dates[0]  # Перша дата
            if start.day <= 15:
                self.payment_input.setCurrentIndex(0)  # Перша половина
            else:
                self.payment_input.setCurrentIndex(1)  # Друга половина

    def _update_custom_text_block(self):
        """Оновлює тільки блок кастомного тексту в редакторі."""
        custom_text = self.custom_text_input.toPlainText()
        if custom_text:
            # Екрануємо для JavaScript
            escaped_text = json.dumps(custom_text)
            script = f"updateBlock('custom_text', {escaped_text});"
            self.web_view.page().runJavaScript(script)

    def _update_preview(self):
        """Оновлює прев'ю документа."""
        try:
            # Отримуємо дані форми
            context = self._get_context()

            # Рендеримо HTML з Jinja2
            env = Environment(loader=FileSystemLoader("desktop/templates"))
            template = env.get_template("wysiwyg_editor.html")
            html = template.render(**context)

            # Встановлюємо HTML
            self.web_view.setHtml(html)

            # Встановлюємо статус
            self.wysiwyg_bridge.set_document_status(
                self.web_view,
                self._current_status.value,
                self._get_status_label()
            )

        except Exception as e:
            print(f"Error updating preview: {e}")
            QMessageBox.warning(self, "Помилка", f"Не вдалося оновити прев'ю: {e}")

    def _get_context(self) -> dict[str, Any]:
        """Збирає контекст для шаблону."""
        staff_id = self.staff_input.currentData()
        from backend.models.staff import Staff
        from backend.models.settings import SystemSettings
        from backend.core.database import get_db_context

        staff_name = ""
        staff_position = ""
        show_dept_head = False
        dept_head_name = ""
        dept_head_position = ""
        rector_name = ""
        dept_name = ""

        if staff_id:
            with get_db_context() as db:
                staff = db.query(Staff).filter(Staff.id == staff_id).first()
                if staff:
                    staff_name = staff.pib_nom
                    staff_position = staff.position

                # Отримуємо налаштування
                rector_name = SystemSettings.get_value(db, "rector_name_dative", "")
                dept_name = SystemSettings.get_value(db, "dept_name", "")
                dept_head_id = SystemSettings.get_value(db, "dept_head_id", None)

                # Завідувач кафедри
                if dept_head_id and staff and staff.id != dept_head_id:
                    show_dept_head = True
                    head = db.query(Staff).filter(Staff.id == dept_head_id).first()
                    if head:
                        dept_head_name = head.pib_nom
                        dept_head_position = head.position

        # Форматуємо дати для контексту
        date_start = ""
        date_end = ""
        days_count_text = "0 днів"

        if self._parsed_dates:
            date_start = self._parsed_dates[0].strftime("%d.%m.%Y")
            date_end = self._parsed_dates[-1].strftime("%d.%m.%Y")
            days_count_text = f"{len(self._parsed_dates)} днів"

        return {
            "doc_type": self._get_doc_type().value,
            "staff_name": staff_name,
            "staff_position": staff_position,
            "date_start": date_start,
            "date_end": date_end,
            "days_count": days_count_text,
            "payment_period": self.payment_input.currentText(),
            "custom_text": self.custom_text_input.toPlainText() or None,
            # Для шаблону
            "rector_name": rector_name,
            "dept_name": dept_name,
            "show_dept_head": show_dept_head,
            "dept_head_name": dept_head_name,
            "dept_head_position": dept_head_position,
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
                    document.payment_period = self.payment_input.currentText()
                    document.custom_text = self.custom_text_input.toPlainText() or None
                else:
                    # Створюємо новий документ
                    document = Document(
                        staff_id=staff_id,
                        doc_type=doc_type,
                        date_start=start,
                        date_end=end,
                        days_count=days_count,
                        payment_period=self.payment_input.currentText(),
                        custom_text=self.custom_text_input.toPlainText() or None,
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

            # Дати - завантажуємо в календар
            self.calendar.clear_selection()

            # Створюємо список дат на основі date_start та date_end
            current = document.date_start
            while current <= document.date_end:
                self.calendar.select_date(current)
                current += timedelta(days=1)

            # Оновлюємо список дат
            self._parsed_dates = sorted(self.calendar.selected_dates())
            self._update_dates_info()

            # Оплата
            payment_items = [self.payment_input.itemText(i) for i in range(self.payment_input.count())]
            if document.payment_period in payment_items:
                index = payment_items.index(document.payment_period)
                self.payment_input.setCurrentIndex(index)

            # Кастомний текст
            if document.custom_text:
                self.custom_text_input.setPlainText(document.custom_text)

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

        # Очищаємо календар
        self.calendar.clear_selection()
        self.weekend_warning_label.setText("")
        self.dates_info_label.setText("Вибрано: 0 днів")

        self.payment_input.setCurrentIndex(0)
        self.custom_text_input.clear()

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

    def _on_calendar_selection_changed(self):
        """Обробляє зміну вибору дат в календарі."""
        self._parsed_dates = sorted(self.calendar.selected_dates())
        self._update_dates_info()
        self._update_payment_period()
        self._update_preview()

    def _update_dates_info(self):
        """Оновлює інформацію про вибрані дати."""
        if not self._parsed_dates:
            self.dates_info_label.setText("Вибрано: 0 днів")
            self.weekend_warning_label.setText("")
            return

        days_count = len(self._parsed_dates)
        start_date = self._parsed_dates[0].strftime("%d.%m.%Y")
        end_date = self._parsed_dates[-1].strftime("%d.%m.%Y")

        # Перевіряємо на вихідні
        weekend_dates = [d for d in self._parsed_dates if d.weekday() >= 5]

        if weekend_dates:
            weekend_str = ", ".join(d.strftime("%d.%m") for d in weekend_dates[:3])
            if len(weekend_dates) > 3:
                weekend_str += f" та ще {len(weekend_dates) - 3}"
            self.weekend_warning_label.setText(f"⚠ Вихідні дні: {weekend_str}")
        else:
            self.weekend_warning_label.setText("")

        self.dates_info_label.setText(f"✓ Вибрано: {days_count} днів ({start_date} - {end_date})")

    def _select_date_range(self):
        """Відкриває діалог для вибору діапазону дат."""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QDateEdit as QDE

        dialog = QDialog(self)
        dialog.setWindowTitle("Вибір діапазону дат")
        layout = QVBoxLayout(dialog)

        # Початкова дата
        layout.addWidget(QLabel("Початкова дата:"))
        start_edit = QDE()
        start_edit.setCalendarPopup(True)
        start_edit.setDate(date.today())
        layout.addWidget(start_edit)

        # Кінцева дата
        layout.addWidget(QLabel("Кінцева дата:"))
        end_edit = QDE()
        end_edit.setCalendarPopup(True)
        end_edit.setDate(date.today() + timedelta(days=14))
        layout.addWidget(end_edit)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            start = start_edit.date().toPyDate()
            end = end_edit.date().toPyDate()

            # Очищаємо попередній вибір
            self.calendar.clear_selection()

            # Додаємо всі дати діапазону
            current = start
            while current <= end:
                self.calendar.select_date(current)
                current += timedelta(days=1)

    def _clear_dates(self):
        """Очищає вибір дат."""
        self.calendar.clear_selection()
        self._parsed_dates = []
        self._update_dates_info()
        self._update_payment_period()
        self._update_preview()


class MultiSelectCalendar(QCalendarWidget):
    """
    Календар з можливістю вибору кількох дат.

    Дозволяє вибирати кілька дат кліком або Ctrl+кліком.
    Вибрані дати підсвічуються синім кольором.
    """

    def __init__(self, parent=None):
        """Ініціалізує календар."""
        super().__init__(parent)
        self._selected_dates: set[date] = set()

        # Стилі для підсвічування вибраних дат
        self.setStyleSheet("""
            QCalendarWidget QTableView::item:selected {
                background-color: #3B82F6;
                color: white;
            }
        """)

    def mousePressEvent(self, event):
        """
        Обробляє натискання миші для вибору кількох дат.

        - Клік: toggles дату
        - Ctrl+клік: додає дату до вибору
        - Shift+клік: вибирає діапазон
        """
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QMouseEvent

        clicked_date = self.selectedDate()
        py_date = clicked_date.toPyDate()

        modifiers = QApplication.keyboardModifiers()

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            # Ctrl+клік - додає/прибирає дату
            if py_date in self._selected_dates:
                self._selected_dates.remove(py_date)
            else:
                self._selected_dates.add(py_date)
        elif modifiers == Qt.KeyboardModifier.ShiftModifier and self._selected_dates:
            # Shift+клік - вибирає діапазон
            last_date = max(self._selected_dates) if self._selected_dates else py_date
            if py_date > last_date:
                start, end = last_date, py_date
            else:
                start, end = py_date, last_date

            current = start
            while current <= end:
                self._selected_dates.add(current)
                current += timedelta(days=1)
        else:
            # Звичайний клік - toggles поточну дату
            if py_date in self._selected_dates and len(self._selected_dates) > 1:
                self._selected_dates.remove(py_date)
            else:
                self._selected_dates.clear()
                self._selected_dates.add(py_date)

        self.updateCells()
        super().mousePressEvent(event)

    def selected_dates(self) -> list[date]:
        """Повертає список вибраних дат."""
        return sorted(self._selected_dates)

    def select_date(self, date_obj: date):
        """Додає дату до вибору."""
        self._selected_dates.add(date_obj)
        self.updateCells()

    def clear_selection(self):
        """Очищає весь вибір."""
        self._selected_dates.clear()
        self.updateCells()
