"""Діалог картки працівника з повною історією змін."""

from datetime import date, datetime as dt, timedelta
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QSizePolicy,
)
import os

from shared.enums import StaffActionType, DocumentType, DocumentStatus, StaffPosition, get_position_label
from shared.absence_types import CODE_TO_ABSENCE_NAME
from shared.constants import STATUS_LABELS, STATUS_COLORS, STATUS_ICONS, STATUS_DESCRIPTIONS
from backend.services.tabel_service import MONTHS_UKR


class EmployeeCardDialog(QDialog):
    """
    Діалог картки працівника.

    Показує поточну інформацію та повну історію змін.
    Дозволяє відновлення неактивних співробітників.
    """

    # Сигнали для комунікації з батьківським вікном
    edit_document = pyqtSignal(int)  # document_id
    delete_document = pyqtSignal(int)  # document_id
    attendance_modified = pyqtSignal(object)  # date that was modified (for switching to correction tab)
    staff_changed = pyqtSignal()  # staff data changed (for refreshing parent)
    subposition_via_document = pyqtSignal()  # open builder for subposition document

    def __init__(self, staff_id: int, parent=None):
        """
        Ініціалізує діалог.

        Args:
            staff_id: ID співробітника
            parent: Батьківський віджет
        """
        super().__init__(parent)
        self.staff_id = staff_id
        self._load_data()
        self._setup_ui()

    def _load_data(self):
        """Завантажує дані співробітника та історію."""
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService

        with get_db_context() as db:
            from backend.models.staff import Staff

            staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
            if not staff:
                raise ValueError(f"Співробітника з ID {self.staff_id} не знайдено")

            # Зберігаємо PIB для пошуку інших позицій
            self.pib_nom = staff.pib_nom

            # Знаходимо всі позиції цього співробітника
            all_positions = db.query(Staff).filter(
                Staff.pib_nom == staff.pib_nom,
                Staff.is_active == True
            ).order_by(Staff.rate.desc()).all()

            # Зберігаємо всі активні позиції
            self.all_positions = []
            for pos in all_positions:
                pos_value = pos.position.value if hasattr(pos.position, 'value') else str(pos.position)
                emp_type_value = pos.employment_type.value if hasattr(pos.employment_type, 'value') else str(pos.employment_type)
                self.all_positions.append({
                    "id": pos.id,
                    "position": pos_value,
                    "position_label": get_position_label(pos_value),
                    "rate": float(pos.rate),
                    "employment_type": emp_type_value,
                    "term_start": pos.term_start,
                    "term_end": pos.term_end,
                })

            service = StaffService(db)
            history = service.get_staff_history(self.staff_id)

            # Зберігаємо дані поточної позиції (обраної)
            self.staff_data = {
                "id": staff.id,
                "pib_nom": staff.pib_nom,
                "pib_dav": staff.pib_dav,
                "degree": staff.degree,
                "rate": float(staff.rate),
                "position": staff.position,
                "employment_type": staff.employment_type,
                "work_basis": staff.work_basis,
                "term_start": staff.term_start,
                "term_end": staff.term_end,
                "vacation_balance": staff.vacation_balance,
                "is_active": staff.is_active,
                "days_until_term_end": staff.days_until_term_end,
            }

            # Перевіряємо чи має підписаний документ (для додавання сумісництва)
            from backend.models.document import Document
            from shared.enums import DocumentStatus

            signed_docs = db.query(Document).filter(
                Document.staff_id == staff.id,
                Document.status.in_([
                    DocumentStatus.SIGNED_RECTOR,
                    DocumentStatus.SCANNED,
                    DocumentStatus.PROCESSED,
                ])
            ).count()
            self.has_signed_document = signed_docs > 0

            # Зберігаємо історію з потрібними даними
            self.history = []
            for entry in history:
                self.history.append({
                    "id": entry.id,
                    "created_at": entry.created_at,
                    "action_type": entry.action_type,
                    "previous_values": entry.previous_values,
                    "changed_by": entry.changed_by,
                    "comment": entry.comment,
                })

            # Зберігаємо документи для відображення історії відпусток
            self.vacation_documents = []
            for doc in staff.documents:
                self.vacation_documents.append({
                    "id": doc.id,
                    "doc_type": doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type),
                    "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                    "date_start": doc.date_start,
                    "date_end": doc.date_end,
                    "days_count": doc.days_count,
                    "created_at": doc.created_at,
                })

            # Завантажуємо записи відвідуваності
            from backend.services.attendance_service import AttendanceService
            attendance_service = AttendanceService(db)
            attendance_records = attendance_service.get_staff_attendance(self.staff_id)
            self.attendance_records = []
            for record in attendance_records:
                self.attendance_records.append({
                    "id": record.id,
                    "date": record.date,
                    "date_end": record.date_end,
                    "code": record.code,
                    "hours": record.hours,
                    "notes": record.notes,
                    "created_at": record.created_at,
                    "is_correction": record.is_correction,
                    "correction_month": record.correction_month,
                    "correction_year": record.correction_year,
                    "correction_sequence": record.correction_sequence,
                })

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle(f"Картка працівника: {self.staff_data['pib_nom']}")
        self.setMinimumSize(1000, 900)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Інформація про співробітника
        self._info_frame = self._create_info_section()
        layout.addWidget(self._info_frame)

        # Історія відпусток
        vacation_header = QHBoxLayout()
        vacation_header.addWidget(QLabel("<b>Історія відпусток</b>"))
        vacation_header.addStretch()

        upload_scan_btn = QPushButton("📎 Завантажити скан")
        upload_scan_btn.setToolTip("Завантажити скан документа, створеного співробітником самостійно")
        upload_scan_btn.clicked.connect(self._on_upload_scan)
        vacation_header.addWidget(upload_scan_btn)

        layout.addLayout(vacation_header)

        self._vacation_history_table = self._create_vacation_history_table()
        layout.addWidget(self._vacation_history_table)

        # Секція відсутностей та особливих відміток
        layout.addWidget(QLabel("<b>📋 Відсутності та особливі відмітки</b>"))
        absence_header = QHBoxLayout()
        add_absence_btn = QPushButton("➕ Додати відмітку")
        add_absence_btn.clicked.connect(self._on_add_absence)
        absence_header.addWidget(add_absence_btn)
        absence_header.addStretch()
        layout.addLayout(absence_header)
        self._absence_table = self._create_absence_table()
        layout.addWidget(self._absence_table)

        # Історія змін
        layout.addWidget(QLabel("<b>Історія змін</b>"))
        layout.addWidget(self._create_history_table())

        # Кнопки дій
        layout.addLayout(self._create_action_buttons())

    def _create_info_section(self) -> QFrame:
        """Створює секцію з поточною інформацією."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background-color: #f5f5f5; border-radius: 5px; padding: 3px; }")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)

        # Заголовок
        title_layout = QHBoxLayout()
        status_label = QLabel("✅ Активний" if self.staff_data['is_active'] else "❌ Неактивний")
        status_label.setStyleSheet(
            "color: green; font-weight: bold;" if self.staff_data['is_active'] else "color: red; font-weight: bold;"
        )

        title = QLabel(f"<h2>{self.staff_data['pib_nom']}</h2>")
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(status_label)
        layout.addLayout(title_layout)

        # Секція ПІБ у давальному відмінку
        dative_layout = QHBoxLayout()
        dative_label = QLabel("ПІБ (давальний відмінок):")
        dative_label.setFixedWidth(160)
        self.pib_dav_edit = QLineEdit()
        self.pib_dav_edit.setPlaceholderText("Наприклад: Олександру Петровичу")
        self.pib_dav_edit.setText(self.staff_data.get('pib_dav') or "")
        self.pib_dav_edit.setMinimumWidth(250)

        generate_btn = QPushButton("🔄 Згенерувати")
        generate_btn.setToolTip("Автоматично створити давальний відмінок")
        generate_btn.clicked.connect(self._generate_dative)

        save_btn = QPushButton("💾")
        save_btn.setToolTip("Зберегти")
        save_btn.clicked.connect(self._save_pib_dative)

        dative_layout.addWidget(dative_label)
        dative_layout.addWidget(self.pib_dav_edit)
        dative_layout.addWidget(generate_btn)
        dative_layout.addWidget(save_btn)
        dative_layout.addStretch()

        layout.addLayout(dative_layout)

        # Роздільник
        separator = QLabel("<hr>")
        separator.setStyleSheet("color: #ccc;")
        layout.addWidget(separator)

        # Деталі
        # Handle both enum objects and string values
        emp_type_value = self.staff_data['employment_type'].value if hasattr(self.staff_data['employment_type'], 'value') else self.staff_data['employment_type']
        work_basis_value = self.staff_data['work_basis'].value if hasattr(self.staff_data['work_basis'], 'value') else self.staff_data['work_basis']

        # Формуємо список всіх позицій
        positions_html = ""
        for i, pos in enumerate(self.all_positions):
            if pos["id"] == self.staff_data["id"]:
                # Поточна позиція
                positions_html += f"<b>{pos['position_label']}</b> ({pos['rate']})"
            else:
                # Інші позиції
                positions_html += f"{pos['position_label']} ({pos['rate']})"
            if i < len(self.all_positions) - 1:
                positions_html += "<br>"

        details_text = f"""
        <table cellspacing="5">
            <tr><td><b>Позиції:</b></td><td>{positions_html}</td></tr>
            <tr><td><b>Вчений ступінь:</b></td><td>{self.staff_data['degree'] or '—'}</td></tr>
            <tr><td><b>Тип працевлаштування:</b></td><td>{self._format_employment_type(emp_type_value)}</td></tr>
            <tr><td><b>Основа:</b></td><td>{self._format_work_basis(work_basis_value)}</td></tr>
            <tr><td><b>Контракт:</b></td><td>
                {self.staff_data['term_start'].strftime('%d.%m.%Y')} —
                {self.staff_data['term_end'].strftime('%d.%m.%Y')}
            </td></tr>
            <tr><td><b>Баланс відпустки:</b></td><td>{self.staff_data['vacation_balance']} днів</td></tr>
            <tr><td><b>Днів до кінця контракту:</b></td><td>{self.staff_data['days_until_term_end']}</td></tr>
        </table>
        """

        details = QLabel(details_text.strip())
        layout.addWidget(details)

        return frame

    def _create_vacation_history_table(self) -> QTableWidget:
        """Створює таблицю історії відпусток з кнопками дій."""
        table = QTableWidget()
        table.setObjectName("vacation_history")
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Період", "Тип", "Днів", "Статус", "Створено", "Дії"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Make "Actions" column fixed width or resize to contents? 
        # User wants buttons to "fill cell", so Stretch is good. 
        # But for 3 buttons Stretch might be too wide or narrow.
        # Let's keep Stretch for now as requested "fill cell".
        
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(self.vacation_documents))

        # Status colors from shared constants
        status_colors = {
            "draft": QColor("#E0E0E0"),          # Сірий - чернетка
            "signed_by_applicant": QColor("#BBDEFB"),  # Синій - підписав заявник
            "approved_by_dispatcher": QColor("#B3E5FC"), # Блакитний - погоджено диспетчером
            "signed_dep_head": QColor("#C8E6C9"),       # Зелений - підписано зав. кафедри
            "agreed": QColor("#FFE082"),               # Помаранчевий - погоджено
            "signed_rector": QColor("#E1BEE7"),         # Фіолетовий - підписано ректором
            "scanned": QColor("#F8BBD0"),               # Маджента - відскановано
            "processed": QColor("#81D4FA"),             # Темно-блакитний - в табелі
            "not_confirmed": QColor("#FFCDD2"),         # Червоний - не підтверджено (немає скану)
        }

        for row, doc in enumerate(self.vacation_documents):
            # Період
            period = f"{doc['date_start'].strftime('%d.%m.%Y')} - {doc['date_end'].strftime('%d.%m.%Y')}"
            table.setItem(row, 0, QTableWidgetItem(period))

            # Тип документа
            doc_type_labels = {
                "vacation_paid": "Оплачувана відпустка",
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
            doc_type = doc_type_labels.get(doc['doc_type'], doc['doc_type'])
            table.setItem(row, 1, QTableWidgetItem(doc_type))

            # Кількість днів
            # For employment documents, show "-"
            if doc['doc_type'].startswith('employment_'):
                days_text = "-"
            else:
                days_text = str(doc['days_count'])
            table.setItem(row, 2, QTableWidgetItem(days_text))

            # Статус з кольором
            status_labels = {
                "draft": "Чернетка",
                "signed_by_applicant": "Підписав заявник",
                "approved_by_dispatcher": "Погоджено диспетчером",
                "signed_dep_head": "Підписано зав. кафедри",
                "agreed": "Погоджено",
                "signed_rector": "Підписано ректором",
                "scanned": "Відскановано",
                "processed": "В табелі",
                "not_confirmed": "Не підтверджено",
            }

            # Logic for visuals:
            # 1. If status is signed/processed but NO SCAN -> Not Confirmed (Red)
            # 2. If status is signed AND HAS SCAN -> Treat as Processed (Blue/Approved)
            
            raw_status = doc['status']
            has_scan = bool(doc.get('file_scan_path'))
            
            display_status_key = raw_status
            
            if raw_status in ('signed', 'processed'):
                if not has_scan:
                    display_status_key = 'not_confirmed'
                elif raw_status == 'signed' and has_scan:
                    # User request: "fully signed and scaned ... should be Обробленно"
                    display_status_key = 'processed'

            status_text = status_labels.get(display_status_key, display_status_key)
            status_item = QTableWidgetItem(status_text)
            status_item.setBackground(status_colors.get(display_status_key, QColor("white")))
            table.setItem(row, 3, status_item)

            # Дата створення
            created = doc['created_at'].strftime("%d.%m.%Y %H:%M") if doc['created_at'] else "—"
            table.setItem(row, 4, QTableWidgetItem(created))

            # Кнопки дій
            button_container = QWidget()
            # User wants buttons to fill cell: Remove spacing/margins, expand policy
            button_layout = QHBoxLayout(button_container)
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setSpacing(1) # Small spacing line

            # Перевіряємо чи документ заблоковано (скановано або оброблено - не можна редагувати/видаляти)
            locked_statuses = ('signed_rector', 'scanned', 'processed')
            is_locked = display_status_key in locked_statuses or raw_status == 'processed'
            
            # Additional check: raw status 'processed' means applied to tabel.
            if raw_status == 'processed':
                is_locked = True
            
            # Кнопка редагування (Edit)
            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Редагувати документ")
            edit_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            edit_btn.setEnabled(not is_locked)
            if is_locked:
                edit_btn.setToolTip("Неможливо редагувати (документ оброблено)")
                # Greying out is handled by system style for disabled widgets usually.
            edit_btn.clicked.connect(lambda checked, d=doc: self._on_edit_document(d['id']))
            button_layout.addWidget(edit_btn)

            # Кнопка підписання (Workflow/Signature) - Middle button
            workflow_btn = QPushButton("📋") # Using same icon as before? Or ✍️?
            # User image showed a clipboard/checklist icon. 📋 is clipboard.
            workflow_btn.setToolTip("Етапи підписання")
            workflow_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            workflow_btn.clicked.connect(lambda checked, d=doc: self._on_workflow_document(d['id']))
            button_layout.addWidget(workflow_btn)

            # Кнопка видалення (Delete)
            delete_btn = QPushButton("🗑️")
            delete_btn.setToolTip("Видалити документ")
            delete_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            delete_btn.setEnabled(not is_locked)
            if is_locked:
                delete_btn.setToolTip("Неможливо видалити (документ оброблено)")
            delete_btn.clicked.connect(lambda checked, d=doc: self._on_delete_document(d['id']))
            button_layout.addWidget(delete_btn)

            table.setCellWidget(row, 5, button_container)

            # Зберігаємо ID
            table.item(row, 0).setData(Qt.ItemDataRole.UserRole, doc['id'])

        return table

    def _create_history_table(self) -> QTableWidget:
        """Створює таблицю історії змін."""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["Дата/Час", "Дія", "Поля", "Хто вніс зміни", "Коментар"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Заборонити редагування
        table.setRowCount(len(self.history))

        for row, entry in enumerate(self.history):
            # Дата/Час
            date_item = QTableWidgetItem(entry['created_at'].strftime("%d.%m.%Y %H:%M"))
            table.setItem(row, 0, date_item)

            # Дія з кольором
            action_item = QTableWidgetItem(self._format_action_type(entry['action_type']))
            action_item.setBackground(self._get_action_color(entry['action_type']))
            table.setItem(row, 1, action_item)

            # Змінені поля
            fields = ", ".join(entry['previous_values'].keys()) if entry['previous_values'] else "—"
            table.setItem(row, 2, QTableWidgetItem(fields))

            # Хто вніс зміни
            changed_by = "🖥️ СИСТЕМА" if entry['changed_by'] == "SYSTEM" else entry['changed_by']
            table.setItem(row, 3, QTableWidgetItem(changed_by))

            # Коментар
            comment = entry['comment'] or ""
            table.setItem(row, 4, QTableWidgetItem(comment))

            # Зберігаємо ID
            table.item(row, 0).setData(Qt.ItemDataRole.UserRole, entry['id'])

        return table

    def _create_action_buttons(self) -> QHBoxLayout:
        """Створює кнопки дій."""
        layout = QHBoxLayout()

        if self.staff_data['is_active']:
            # Перевіряємо чи можна додати сумісництво:
            # Можна додавати тільки з основної позиції (ставка 1.00)
            is_main_position = self.staff_data['rate'] == 1.0

            if is_main_position:
                add_subposition_btn = QPushButton("➕ Додати сумісництво")
                add_subposition_btn.setToolTip("Додати додаткову позицію (ставка < 1.00)")
                add_subposition_btn.clicked.connect(self._add_subposition)
                layout.addWidget(add_subposition_btn)
            else:
                # Показуємо що можна додавати тільки з основної позиції
                info_btn = QPushButton("ℹ️ Сумісництво з основної позиції")
                info_btn.setToolTip("Додавати сумісництво можна тільки з основної позиції (ставка 1.00)")
                info_btn.setEnabled(False)
                layout.addWidget(info_btn)

        if not self.staff_data['is_active']:
            # Кнопка відновлення для неактивних
            restore_btn = QPushButton("Відновити (новий запис)")
            restore_btn.clicked.connect(self._restore_staff)
            layout.addWidget(restore_btn)

            # Кнопка повного видалення для неактивних
            hard_delete_btn = QPushButton("🗑️ Видалити назавжди")
            hard_delete_btn.clicked.connect(self._hard_delete_staff)
            layout.addWidget(hard_delete_btn)

        # Закрити
        close_btn = QPushButton("Закрити")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        return layout

    def _on_edit_document(self, document_id: int):
        """Обробляє редагування документа."""
        self.edit_document.emit(document_id)
        self.accept()

    def _on_workflow_document(self, document_id: int):
        """Обробляє оновлення етапів підписання."""
        self._update_workflow_steps(document_id)

    def _on_delete_document(self, document_id: int):
        """Обробляє видалення документа."""
        from backend.core.database import get_db_context
        from backend.models.document import Document
        from backend.services.document_service import DocumentService
        from backend.services.grammar_service import GrammarService
        from shared.enums import DocumentStatus
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox

        reply = QMessageBox.question(
            self,
            "Підтвердження",
            "Ви впевнені, що хочете видалити цей документ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        with get_db_context() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                QMessageBox.warning(self, "Помилка", "Документ не знайдено")
                return

            # Перевіряємо статус
            if doc.status == DocumentStatus.DRAFT:
                # Чернетка - видаляємо повністю
                db.delete(doc)
                db.commit()
                QMessageBox.information(self, "Успіх", "Документ видалено")

            elif doc.status in (
                DocumentStatus.SIGNED_BY_APPLICANT,
                DocumentStatus.APPROVED_BY_DISPATCHER,
                DocumentStatus.SIGNED_DEP_HEAD,
                DocumentStatus.AGREED,
                DocumentStatus.SIGNED_RECTOR,
            ):
                # На етапах підписання - показуємо діалог введення причини
                reason_dialog = QDialog(self)
                reason_dialog.setWindowTitle("Причина відкату")
                reason_dialog.setMinimumWidth(400)

                layout = QVBoxLayout(reason_dialog)
                layout.addWidget(QLabel("Вкажіть причину повернення документа в чернетку:"))

                reason_input = QTextEdit()
                reason_input.setPlaceholderText("Наприклад: Помилка в датах, зміна планів тощо...")
                reason_input.setMinimumHeight(100)
                layout.addWidget(reason_input)

                buttons = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                )
                buttons.accepted.connect(reason_dialog.accept)
                buttons.rejected.connect(reason_dialog.reject)
                layout.addWidget(buttons)

                if reason_dialog.exec() != QDialog.DialogCode.Accepted:
                    return  # Користувач скасував

                reason = reason_input.toPlainText().strip()
                if not reason:
                    QMessageBox.warning(self, "Попередження", "Будь ласка, вкажіть причину відкату документа.")
                    return

                # Відкатуємо до чернетки з причиною
                doc_service = DocumentService(db, GrammarService())
                doc_service.rollback_to_draft(doc, reason)
                QMessageBox.information(self, "Успіх", "Документ повернуто в чернетку")

            elif doc.status in (DocumentStatus.SCANNED, DocumentStatus.PROCESSED):
                QMessageBox.warning(
                    self,
                    "Помилка",
                    "Неможливо видалити відсканований або оброблений документ."
                )
                return

        # Перезавантажуємо дані та оновлюємо таблиці
        self._load_data()
        # Refresh the tables in place
        self._refresh_tables()

    def _refresh_tables(self):
        """Оновлює таблиці без перестворення всього інтерфейсу."""
        # Create new vacation history table
        new_table = self._create_vacation_history_table()

        # Replace the old table in layout
        layout = self.layout()
        if layout and hasattr(self, '_vacation_history_table'):
            # Find index of old table
            old_table_index = -1
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self._vacation_history_table:
                    old_table_index = i
                    break

            if old_table_index >= 0:
                # Remove old table from layout
                layout.takeAt(old_table_index)
                self._vacation_history_table.setParent(None)

                # Insert new table at the same position
                layout.insertWidget(old_table_index, new_table)
                self._vacation_history_table = new_table

    def _show_workflow_dialog(self):
        """Показує діалог для оновлення етапів підписання."""
        from backend.core.database import get_db_context
        from backend.models.document import Document
        from backend.models.settings import Approvers
        from backend.services.grammar_service import GrammarService
        import datetime

        # Ask user which document to update
        doc_dialog = QDialog(self)
        doc_dialog.setWindowTitle("Оберіть документ")
        doc_dialog.setMinimumWidth(400)
        layout = QVBoxLayout(doc_dialog)

        layout.addWidget(QLabel("Оберіть документ для оновлення етапів підписання:"))

        # Create document list
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        doc_list = QListWidget()
        for doc in self.vacation_documents:
            item = QListWidgetItem()
            item.setText(f"#{doc['id']} - {doc['date_start'].strftime('%d.%m.%Y')} - {doc['doc_type']}")
            item.setData(Qt.ItemDataRole.UserRole, doc['id'])
            doc_list.addItem(item)
        layout.addWidget(doc_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(doc_dialog.accept)
        buttons.rejected.connect(doc_dialog.reject)
        layout.addWidget(buttons)

        if doc_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = doc_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "Попередження", "Оберіть документ")
            return

        document_id = selected.data(Qt.ItemDataRole.UserRole)

        # Now show the workflow dialog for this document
        self._update_workflow_steps(document_id)

    def _update_workflow_steps(self, document_id: int):
        """Оновлює етапи підписання для документа."""
        from backend.core.database import get_db_context
        from backend.models.document import Document
        from backend.models.settings import Approvers
        from backend.services.grammar_service import GrammarService
        import datetime

        # Define fixed workflow steps (order: applicant -> approval -> department_head)
        fixed_steps = [
            ("applicant", "Підпис викладача", "✍️"),
            ("approval", "Перевірено диспетчерською", "📋"),
            ("department_head", "Підпис завідувача кафедри", "👔"),
        ]

        # Get approvers from database (between department_head and rector)
        approvers = []
        with get_db_context() as db:
            approvers_data = db.query(Approvers).order_by(Approvers.order_index).all()
            for approver in approvers_data:
                full_name = approver.full_name_nom or approver.full_name_dav
                if full_name:
                    approvers.append((f"approver_{full_name}", full_name, "📄"))

        # Fixed steps after approvers (rector -> scanned -> tabel)
        final_steps = [
            ("rector", "Підпис ректора", "🏛️"),
            ("scanned", "Відскановано (вхідний скан)", "📷"),
            ("tabel", "Додано до табелю", "✅"),
        ]

        # Create workflow dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Етапи підписання документа #{document_id}")
        dialog.setMinimumWidth(600)
        dialog_layout = QVBoxLayout(dialog)

        # Load document data
        with get_db_context() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                QMessageBox.warning(self, "Помилка", "Документ не знайдено")
                return

            progress = doc.get_workflow_progress()
            completed_approvers = doc.approval_order_comment or ""

            # Store checkboxes
            checkboxes = {}
            comments = {}

            # Add fixed steps
            for step_key, step_name, step_icon in fixed_steps:
                step_layout = QHBoxLayout()
                
                # Checkbox
                checkbox = QCheckBox(f"{step_icon} {step_name}")
                step_data = progress.get(step_key, {})
                is_completed = step_data.get("completed", False)
                checkbox.setChecked(is_completed)
                checkboxes[step_key] = checkbox
                step_layout.addWidget(checkbox)

                # Date label
                date_str = ""
                if is_completed and step_data.get("at"):
                    date_val = step_data["at"]
                    if isinstance(date_val, str):
                        try:
                            date_val = datetime.datetime.fromisoformat(date_val)
                        except ValueError:
                            pass
                    if isinstance(date_val, datetime.datetime):
                        date_str = date_val.strftime("%d.%m.%Y %H:%M")
                
                date_label = QLabel(date_str)
                date_label.setStyleSheet("color: #666; font-size: 11px;")
                step_layout.addWidget(date_label)

                # Comment input
                comment_edit = QLineEdit()
                comment_edit.setPlaceholderText("Коментар")
                comment_edit.setText(step_data.get("comment") or "")
                comment_edit.setMaximumWidth(200)
                comments[step_key] = comment_edit
                step_layout.addWidget(comment_edit)

                dialog_layout.addLayout(step_layout)

            # Add separator for approvers
            dialog_layout.addWidget(QLabel("<b>Підписи погоджувачів</b>"))
            approver_checkboxes = {}
            approver_comments = {}

            for step_key, approver_name, icon in approvers:
                step_layout = QHBoxLayout()
                
                # Checkbox
                checkbox = QCheckBox(f"{icon} {approver_name}")
                is_completed = approver_name in completed_approvers
                checkbox.setChecked(is_completed)
                approver_checkboxes[step_key] = checkbox
                step_layout.addWidget(checkbox)

                # Date label (approvers typically store date in comment or separate field, but strictly we only have the order_at)
                # For multiple approvers, we rely on approval_order_at if this box is checked, 
                # OR we might not have individual timestamps for them easily without parsing comments differently.
                # Simplification: Show "Signed" if checked, but no specific date unless we track it per-approver individually (which we don't effectively do yet).
                # We'll use the generic approval_order_at if available for now if checked.
                
                date_str = ""
                if is_completed and progress.get("approval_order", {}).get("at"):
                     # Using general approval order date as a proxy/best effort
                    date_val = progress["approval_order"]["at"]
                    if isinstance(date_val, datetime.datetime):
                        date_str = date_val.strftime("%d.%m.%Y") # Just date maybe?

                date_label = QLabel(date_str)
                date_label.setStyleSheet("color: #666; font-size: 11px;")
                step_layout.addWidget(date_label)

                # Comment input
                comment_edit = QLineEdit()
                comment_edit.setPlaceholderText("Коментар")
                comment_edit.setMaximumWidth(200)
                approver_comments[step_key] = comment_edit
                step_layout.addWidget(comment_edit)

                dialog_layout.addLayout(step_layout)

            # Add final steps
            dialog_layout.addWidget(QLabel("<b>Завершальні етапи</b>"))

            # Rector Step (Checkbox)
            step_key = "rector"
            step_name = "Підпис ректора"
            step_icon = "🏛️"

            step_layout = QHBoxLayout()
            checkbox = QCheckBox(f"{step_icon} {step_name}")
            step_data = progress.get(step_key, {})
            is_completed = step_data.get("completed", False)
            checkbox.setChecked(is_completed)
            checkboxes[step_key] = checkbox
            step_layout.addWidget(checkbox)

            date_str = ""
            if is_completed and step_data.get("at"):
                date_val = step_data["at"]
                if isinstance(date_val, str):
                     try:
                        date_val = datetime.datetime.fromisoformat(date_val)
                     except ValueError: pass
                if isinstance(date_val, datetime.datetime):
                    date_str = date_val.strftime("%d.%m.%Y %H:%M")

            date_label = QLabel(date_str)
            date_label.setStyleSheet("color: #666; font-size: 11px;")
            step_layout.addWidget(date_label)

            comment_edit = QLineEdit()
            comment_edit.setPlaceholderText("Коментар")
            comment_edit.setText(step_data.get("comment") or "")
            comment_edit.setMaximumWidth(200)
            comments[step_key] = comment_edit
            step_layout.addWidget(comment_edit)
            dialog_layout.addLayout(step_layout)


            # Scanned Step (Upload Button)
            step_key = "scanned"
            step_name = "Відскановано"
            step_icon = "📷"
            step_data = progress.get(step_key, {})
            is_scanned = step_data.get("completed", False)

            step_layout = QHBoxLayout()
            
            lbl = QLabel(f"{step_icon} {step_name}:")
            lbl.setFixedWidth(150)
            step_layout.addWidget(lbl)

            status_text = "Ні"
            status_style = "color: red; font-weight: bold;"
            if is_scanned:
                status_text = "Так"
                if doc.file_scan_path:
                   status_text += f" ({os.path.basename(doc.file_scan_path)})"
                status_style = "color: green; font-weight: bold;"

            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet(status_style)
            step_layout.addWidget(status_lbl)

            upload_btn = QPushButton("Завантажити скан")
            upload_btn.clicked.connect(lambda: self._upload_scan(document_id, dialog))
            step_layout.addWidget(upload_btn)

            dialog_layout.addLayout(step_layout)
            
            # Warning
            if progress["rector"]["completed"] and not is_scanned:
                warn_lbl = QLabel("⚠️ Увага: Документ підписано ректором, але скан не завантажено!")
                warn_lbl.setStyleSheet("color: red; font-weight: bold;")
                dialog_layout.addWidget(warn_lbl)

            # Tabel Step (Read-only)
            step_key = "tabel"
            step_name = "Додано до табелю"
            step_icon = "✅"
            step_data = progress.get(step_key, {})
            is_in_tabel = step_data.get("completed", False)

            step_layout = QHBoxLayout()
            lbl = QLabel(f"{step_icon} {step_name}:")
            lbl.setFixedWidth(150)
            step_layout.addWidget(lbl)

            tabel_status = "Так" if is_in_tabel else "Ні"
            tabel_style = "color: green; font-weight: bold;" if is_in_tabel else "color: gray;"

            # Adding date if available
            if is_in_tabel and step_data.get("at"):
                 date_val = step_data["at"]
                 if isinstance(date_val, datetime.datetime):
                    tabel_status += f" ({date_val.strftime('%d.%m.%Y')})"

            t_lbl = QLabel(tabel_status)
            t_lbl.setStyleSheet(tabel_style)
            step_layout.addWidget(t_lbl)

            dialog_layout.addLayout(step_layout)

            # Buttons
            btn_layout = QHBoxLayout()

            save_btn = QPushButton("Зберегти")
            save_btn.clicked.connect(dialog.accept)
            btn_layout.addWidget(save_btn)

            clear_btn = QPushButton("Очистити всі")
            clear_btn.clicked.connect(lambda: self._clear_all_workflow_steps(document_id, dialog))
            btn_layout.addWidget(clear_btn)

            cancel_btn = QPushButton("Скасувати")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(cancel_btn)

            dialog_layout.addLayout(btn_layout)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                now = dt.now()

                def _create_correction_attendance(db_session, document):
                    """Create correction attendance record for approved months."""
                    from backend.models import Attendance
                    from backend.models.document import DocumentType
                    from backend.services.attendance_service import (
                        AttendanceService,
                        AttendanceConflictError,
                        AttendanceLockedError,
                    )

                    # Determine vacation code
                    if document.doc_type == DocumentType.VACATION_PAID:
                        code = "В"
                    elif document.doc_type == DocumentType.VACATION_UNPAID:
                        code = "НА"
                    else:
                        return  # Not a vacation

                    # Use AttendanceService for consistency
                    att_service = AttendanceService(db_session)

                    # Create attendance record for each vacation day
                    current = document.date_start
                    while current <= document.date_end:
                        existing = db_session.query(Attendance).filter(
                            Attendance.staff_id == document.staff_id,
                            Attendance.date == current,
                            Attendance.is_correction == True,
                            Attendance.correction_month == document.date_start.month,
                            Attendance.correction_year == document.date_start.year,
                            Attendance.correction_sequence == document.correction_sequence,
                        ).first()

                        if not existing:
                            try:
                                att_service.create_attendance(
                                    staff_id=document.staff_id,
                                    attendance_date=current,
                                    code=code,
                                    hours=8.0,
                                    notes=f"Корекція: документ №{document.id}",
                                    is_correction=True,
                                    correction_month=document.date_start.month,
                                    correction_year=document.date_start.year,
                                    correction_sequence=document.correction_sequence,
                                )
                            except (AttendanceConflictError, AttendanceLockedError):
                                # If already exists or locked, ignore
                                pass

                        current += timedelta(days=1)

                # Update fixed steps (applicant, approval, department_head)
                # AND Rector (manually added to iteration list)
                steps_to_save = fixed_steps + [("rector", "Підпис ректора", "🏛️")]
                
                for step_key, _, _ in steps_to_save:
                    checkbox = checkboxes.get(step_key)
                    # comments dict should contain all keys
                    comment_widget = comments.get(step_key)
                    comment = comment_widget.text().strip() or None if comment_widget else None
                    
                    if not checkbox:
                        continue
                        
                    # Logic to preserve timestamps:
                    # If checked and was already valid -> keep old time
                    # If checked and was empty -> set now
                    # If unchecked -> set None
                    
                    is_checked = checkbox.isChecked()
                    
                    # Helper to get current attribute value
                    # Handle special naming for applicant
                    current_at_attr = f"{step_key}_at" if step_key != "applicant" else "applicant_signed_at"
                    current_at = getattr(doc, current_at_attr, None)
                    
                    if is_checked:
                        new_at = current_at if current_at else now
                    else:
                        new_at = None
                        
                    if step_key == "applicant":
                        doc.applicant_signed_at = new_at
                        doc.applicant_signed_comment = comment
                    elif step_key == "approval":
                        doc.approval_at = new_at
                        doc.approval_comment = comment
                    elif step_key == "department_head":
                        doc.department_head_at = new_at
                        doc.department_head_comment = comment
                    
                    # Final steps
                    elif step_key == "rector":
                        doc.rector_at = new_at
                        doc.rector_comment = comment

                        # Coupling: If Rector is signed, Tabel must be added
                        # We enforce this automatically.
                        if new_at and not doc.tabel_added_at:
                            # Check if the document's month is already approved
                            from backend.services.tabel_approval_service import TabelApprovalService
                            approval_service = TabelApprovalService(db)
                            doc_month = doc.date_start.month
                            doc_year = doc.date_start.year
                            is_month_locked = approval_service.is_month_locked(doc_month, doc_year)

                            if is_month_locked:
                                # Month is approved - create correction attendance record
                                doc.tabel_added_at = None
                                doc.tabel_added_comment = f"Місяць {doc_month}.{doc_year} вже затверджено. Додано до корегуючого табелю."
                                # Set correction fields (reuse approval_service from above)
                                correction_sequence = approval_service.get_or_create_correction_sequence(doc_month, doc_year)
                                doc.is_correction = True
                                doc.correction_month = doc_month
                                doc.correction_year = doc_year
                                doc.correction_sequence = correction_sequence
                                _create_correction_attendance(db, doc)
                            else:
                                # Month not approved - add to main tabel
                                doc.tabel_added_at = now
                                doc.tabel_added_comment = "Автоматично додано після підпису ректора"
                        elif not new_at:
                            # Optional: if rector removed, remove from tabel?
                            # Maybe safer not to automate REMOVAL to avoid data loss,
                            # or follow the user's "automatic" wish.
                            # Let's keep tabel if it was added, or maybe remove only if it was auto-added.
                            # For now, strict coupling: No rector -> No tabel (unless manual? but tabel is read only now).
                            pass

                # Update approvers
                completed_approvers_list = []
                for step_key, approver_name, _ in approvers:
                    checkbox = approver_checkboxes[step_key]
                    if checkbox.isChecked():
                        completed_approvers_list.append(approver_name)

                doc.approval_order_at = now if completed_approvers_list else None
                doc.approval_order_comment = ", ".join(completed_approvers_list) if completed_approvers_list else None

                # Оновлюємо статус на основі етапів
                doc.update_status_from_workflow()

                db.commit()
                QMessageBox.information(self, "Успіх", "Етапи підписання оновлено")
                
                # Refresh UI
                self._load_data()
                self._refresh_tables()

    def _upload_scan(self, document_id: int, parent_dialog: QDialog):
        """Завантаження скану документа."""
        from backend.core.database import get_db_context
        from backend.models.document import Document
        from backend.services.document_service import DocumentService
        
        file_path, _ = QFileDialog.getOpenFileName(
            parent_dialog,
            "Оберіть скан документа",
            "",
            "PDF Files (*.pdf);;Images (*.png *.jpg *.jpeg)"
        )
        
        if not file_path:
            return

        try:
            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if not doc:
                    return

                from backend.services.grammar_service import GrammarService
                grammar = GrammarService()
                service = DocumentService(db, grammar)
                service.set_scanned(doc, file_path=file_path, comment="Завантажено через UI")
                QMessageBox.information(self, "Успіх", "Скан успішно завантажено")
                
                # Refresh parent dialog? usually needs closure and reopen or dynamic update.
                # Simplest is to close and let user reopen or just show success.
                # Ideally, we should update the label in parent_dialog dynamically.
                # But parent_dialog is constructed in method local scope. 
                # We can close it to force refresh.
                parent_dialog.accept() 
                
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити скан: {e}")

    def _clear_all_workflow_steps(self, document_id: int, dialog: QDialog):
        """Очищає всі етапи підписання."""
        from backend.core.database import get_db_context
        from backend.models.document import Document

        reply = QMessageBox.question(
            self,
            "Підтвердження",
            "Очистити всі етапи підписання?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        with get_db_context() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                return

            # Скидаємо всі етапи підписання
            doc.reset_workflow()
            db.commit()

        dialog.accept()
        QMessageBox.information(self, "Успіх", "Всі етапи очищено")

    def _generate_dative(self):
        """Генерує ПІБ у давальному відмінку."""
        from backend.services.grammar_service import GrammarService

        pib_nom = self.staff_data.get('pib_nom', '')
        if not pib_nom:
            QMessageBox.warning(self, "Попередження", "ПІБ не знайдено")
            return

        try:
            grammar = GrammarService()
            pib_dav = grammar.to_dative(pib_nom)
            self.pib_dav_edit.setText(pib_dav)

            # Запитуємо чи користувач задоволений результатом
            reply = QMessageBox.question(
                self,
                "Перевірка",
                f"Згенеровано: <b>{pib_dav}</b>\n\n"
                f"Це правильно? Якщо ні, ви можете відредагувати вручну.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._save_pib_dative()
            else:
                self.pib_dav_edit.setFocus()
                self.pib_dav_edit.selectAll()

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося згенерувати відмінок: {e}")

    def _save_pib_dative(self):
        """Зберігає ПІБ у давальному відмінку."""
        from backend.core.database import get_db_context
        from backend.models.staff import Staff

        pib_dav = self.pib_dav_edit.text().strip() or None

        try:
            with get_db_context() as db:
                staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
                if staff:
                    staff.pib_dav = pib_dav
                    db.commit()
                    self.staff_data['pib_dav'] = pib_dav
                    QMessageBox.information(self, "Успіх", "ПІБ у давальному відмінку збережено")
                else:
                    QMessageBox.warning(self, "Помилка", "Працівника не знайдено")

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти: {e}")

    def _format_employment_type(self, value: str) -> str:
        """Форматує тип працевлаштування для відображення."""
        type_map = {
            "main": "Основне місце роботи",
            "internal": "Внутрішній сумісник",
            "external": "Зовнішній сумісник",
        }
        return type_map.get(value, value)

    def _format_work_basis(self, value: str) -> str:
        """Форматує основу роботи для відображення."""
        basis_map = {
            "contract": "Контракт",
            "competitive": "Конкурсна основа",
            "statement": "Заява",
        }
        return basis_map.get(value, value)

    def _format_position(self, position: str) -> str:
        """Форматує посаду для відображення."""
        return get_position_label(position)

    def _format_action_type(self, action_type: str) -> str:
        """Форматує тип дії для відображення."""
        action_map = {
            StaffActionType.CREATE.value: "➕ Створення",
            StaffActionType.UPDATE.value: "✏️ Оновлення",
            StaffActionType.DEACTIVATE.value: "❌ Деактивація",
            StaffActionType.RESTORE.value: "🔄 Відновлення",
        }
        return action_map.get(action_type, action_type)

    def _get_action_color(self, action_type: str) -> QColor:
        """Повертає колір для типу дії."""
        color_map = {
            StaffActionType.CREATE.value: QColor("#C8E6C9"),  # Світло-зелений
            StaffActionType.UPDATE.value: QColor("#BBDEFB"),  # Світло-синій
            StaffActionType.DEACTIVATE.value: QColor("#FFCDD2"),  # Світло-червоний
            StaffActionType.RESTORE.value: QColor("#FFF9C4"),  # Світло-жовтий
        }
        return color_map.get(action_type, QColor("#FFFFFF"))

    def _add_subposition(self):
        """Додає сумісництво - показує діалог з вибором способу."""
        from datetime import date, timedelta
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame
        from desktop.ui.scan_upload_dialog import ScanUploadDialog

        # Створюємо діалог з вибором способу
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Додати сумісництво: {self.staff_data['pib_nom']}")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        # Інформація про співробітника
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout(info_frame)

        info_layout.addWidget(QLabel(f"<b>Співробітник:</b> {self.staff_data['pib_nom']}"))
        info_layout.addWidget(QLabel(f"<b>Поточна позиція:</b> {get_position_label(self.staff_data['position'])} ({self.staff_data['rate']})"))
        info_layout.addWidget(QLabel(""))

        info_text = QLabel(
            "<i>Оберіть спосіб додавання сумісництва:</i><br><br>"
            "• <b>Створити документ</b> - перехід до конструктора заяв на продовження сумісництва<br>"
            "• <b>Завантажити скан</b> - завантажити скан договору для створення нової позиції"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        layout.addWidget(info_frame)

        # Кнопки вибору способу
        button_layout = QHBoxLayout()

        create_doc_btn = QPushButton("📄 Створити документ\n(продовження сумісництва)")
        create_doc_btn.setMinimumHeight(70)
        create_doc_btn.clicked.connect(lambda: self._add_subposition_via_document(dialog))
        button_layout.addWidget(create_doc_btn)

        upload_scan_btn = QPushButton("📎 Завантажити скан\nдоговору")
        upload_scan_btn.setMinimumHeight(70)
        upload_scan_btn.clicked.connect(lambda: self._add_subposition_via_scan(dialog))
        button_layout.addWidget(upload_scan_btn)

        layout.addLayout(button_layout)
        dialog.exec()

    def _add_subposition_via_document(self, parent_dialog: QDialog):
        """Додає сумісництво через створення документа."""
        parent_dialog.reject()

        # Emit signal to open builder tab with subposition document type
        # Parent (staff_tab) should handle this signal
        self.subposition_via_document.emit()

    def _add_subposition_via_scan(self, parent_dialog: QDialog):
        """Додає сумісництво через завантаження скану."""
        parent_dialog.reject()

        # Open scan upload dialog
        dialog = ScanUploadDialog(self.staff_id, parent=self)
        dialog.scan_uploaded.connect(self._on_subposition_scan_uploaded)
        dialog.exec()

    def _on_subposition_scan_uploaded(self, staff_id: int):
        """Обробляє завантаження скану для сумісництва."""
        # Reload data to show new position
        self._load_data()
        # Refresh the info section
        self._refresh_info_section()

    def _refresh_info_section(self):
        """Оновлює секцію інформації."""
        # Find and replace the info section
        layout = self.layout()
        if layout and hasattr(self, '_info_frame'):
            # Find index of old frame
            old_frame_index = -1
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self._info_frame:
                    old_frame_index = i
                    break

            if old_frame_index >= 0:
                # Remove old frame from layout
                layout.takeAt(old_frame_index)
                self._info_frame.setParent(None)

                # Create and insert new frame at the same position
                self._info_frame = self._create_info_section()
                layout.insertWidget(old_frame_index, self._info_frame)

    def _add_subposition_direct(self):
        """Додає сумісництво напряму (без документа) - для завантаженого скану."""
        from datetime import date
        from PyQt6.QtWidgets import QDialog, QFormLayout, QComboBox, QDoubleSpinBox, QDateEdit, QDialogButtonBox, QLabel, QHBoxLayout, QPushButton
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService
        from backend.models.settings import SystemSettings
        from shared.enums import EmploymentType, WorkBasis

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Додати сумісництво: {self.staff_data['pib_nom']}")
        dialog.setMinimumWidth(400)

        layout = QFormLayout(dialog)

        # Попередження
        warning = QLabel("⚠️ Ставка має бути менше 1.00 для сумісництва")
        warning.setStyleSheet("color: #666; font-style: italic;")
        layout.addRow("", warning)

        # Посада
        position_input = QComboBox()
        position_input.setEditable(False)
        position_items = {
            StaffPosition.HEAD_OF_DEPARTMENT: "Завідувач кафедри",
            StaffPosition.ACTING_HEAD_OF_DEPARTMENT: "В.о завідувача кафедри",
            StaffPosition.PROFESSOR: "Професор",
            StaffPosition.ASSOCIATE_PROFESSOR: "Доцент",
            StaffPosition.SENIOR_LECTURER: "Старший викладач",
            StaffPosition.LECTURER: "Асистент",
            StaffPosition.SPECIALIST: "Фахівець",
        }
        for pos_value, pos_label in position_items.items():
            position_input.addItem(pos_label, pos_value)
        layout.addRow("Посада:", position_input)

        # Ставка - only allow values < 1.0
        rate_layout = QHBoxLayout()
        rate_input = QDoubleSpinBox()
        rate_input.setRange(0.01, 0.99)
        rate_input.setSingleStep(0.05)
        rate_input.setDecimals(2)
        rate_input.setValue(0.25)
        rate_layout.addWidget(rate_input)

        # Quick rate buttons
        for rate_value in [0.25, 0.5, 0.75]:
            rate_btn = QPushButton(f"{rate_value:.2f}")
            rate_btn.setFixedWidth(50)
            rate_btn.clicked.connect(lambda checked, r=rate_value: rate_input.setValue(r))
            rate_layout.addWidget(rate_btn)
        layout.addRow("Ставка:", rate_layout)

        # Тип працевлаштування
        employment_type_input = QComboBox()
        employment_type_items = {
            EmploymentType.MAIN: "Основне місце роботи",
            EmploymentType.INTERNAL: "Внутрішній сумісник",
            EmploymentType.EXTERNAL: "Зовнішній сумісник",
        }
        for et, label in employment_type_items.items():
            employment_type_input.addItem(label, et)
        # Default to internal for subposition
        employment_type_input.setCurrentIndex(1)  # Внутрішній сумісник
        layout.addRow("Тип працевлаштування:", employment_type_input)

        # Контракт - дати
        term_start_input = QDateEdit()
        term_start_input.setCalendarPopup(True)
        term_start_input.setDate(date.today())
        layout.addRow("Початок контракту:", term_start_input)

        term_end_input = QDateEdit()
        term_end_input.setCalendarPopup(True)
        term_end_input.setDate(date.today())
        layout.addRow("Кінець контракту:", term_end_input)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Валідація
        if rate_input.value() >= 1.0:
            QMessageBox.warning(
                dialog,
                "Помилка",
                "Для сумісництва ставка має бути менше 1.00"
            )
            return

        if term_end_input.date().toPyDate() <= term_start_input.date().toPyDate():
            QMessageBox.warning(
                dialog,
                "Помилка",
                "Дата закінчення контракту має бути пізніше за дату початку"
            )
            return

        # Збереження
        staff_data = {
            "pib_nom": self.staff_data['pib_nom'],
            "pib_dav": self.staff_data.get('pib_dav') or "",
            "degree": self.staff_data.get('degree'),
            "position": position_input.currentData(),
            "rate": rate_input.value(),
            "employment_type": employment_type_input.currentData(),
            "work_basis": WorkBasis.CONTRACT,
            "term_start": term_start_input.date().toPyDate(),
            "term_end": term_end_input.date().toPyDate(),
            "is_active": True,
            "vacation_balance": 0,
            "department": "",
            "work_schedule": self.staff_data.get('work_schedule', 'standard'),
        }

        try:
            with get_db_context() as db:
                service = StaffService(db, changed_by="USER")
                service.create_staff(staff_data)

            QMessageBox.information(
                self,
                "Успіх",
                f"Сумісництво додано: {get_position_label(staff_data['position'])} ({staff_data['rate']})"
            )

            # Повідомляємо батьківський вікно про зміни
            self.staff_changed.emit()
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося додати сумісництво: {e}")

    def _restore_staff(self):
        """Відновлює співробітника - пропонує створити документ або завантажити скан."""
        from datetime import date, timedelta
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame
        from desktop.ui.scan_upload_dialog import ScanUploadDialog

        # Створюємо діалог з вибором способу реактивації
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Реактивація: {self.staff_data['pib_nom']}")
        dialog.setMinimumWidth(550)

        layout = QVBoxLayout(dialog)

        # Інформація про співробітника
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout(info_frame)

        info_layout.addWidget(QLabel(f"<b>Співробітник:</b> {self.staff_data['pib_nom']}"))
        info_layout.addWidget(QLabel(f"<b>Попередня посада:</b> {get_position_label(self.staff_data['position'])}"))
        info_layout.addWidget(QLabel(f"<b>Ставка:</b> {self.staff_data['rate']}"))
        info_layout.addWidget(QLabel(f"<b>Тип працевлаштування:</b> {self._get_employment_type_label(self.staff_data['employment_type'])}"))
        info_layout.addWidget(QLabel(""))

        info_text = QLabel(
            "<i>Для реактивації співробітника оберіть один із способів:</i><br><br>"
            "• <b>Створити документ</b> - перехід до конструктора заяв з попередньо заповненими даними<br>"
            "• <b>Завантажити скан</b> - завантажити скан договору для створення нового запису"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        layout.addWidget(info_frame)

        # Кнопки вибору способу
        button_layout = QHBoxLayout()

        create_doc_btn = QPushButton("📄 Створити документ (продовження контракту)")
        create_doc_btn.setMinimumHeight(60)
        create_doc_btn.clicked.connect(lambda: self._restore_via_document(dialog))
        button_layout.addWidget(create_doc_btn)

        upload_scan_btn = QPushButton("📎 Завантажити скан договору")
        upload_scan_btn.setMinimumHeight(60)
        upload_scan_btn.clicked.connect(lambda: self._restore_via_scan(dialog))
        button_layout.addWidget(upload_scan_btn)

        layout.addLayout(button_layout)
        dialog.exec()

    def _get_employment_type_label(self, emp_type: str) -> str:
        """Отримує українську мітку для типу працевлаштування."""
        # Handle both enum objects and string values
        type_value = emp_type.value if hasattr(emp_type, 'value') else emp_type
        labels = {
            "main": "Основне місце роботи",
            "internal": "Внутрішній сумісник",
            "external": "Зовнішній сумісник",
        }
        return labels.get(type_value, type_value)

    def _restore_via_document(self, dialog: QDialog):
        """Реактивує через створення документа - переходить до конструктора заяв."""
        # Закриваємо спочатку діалог вибору способу реактивації
        dialog.done(QDialog.DialogCode.Accepted)

        # Зберігаємо дані для попереднього заповнення
        from desktop.ui.builder_tab import BuilderTab
        BuilderTab._reactivation_data = {
            'staff_id': self.staff_id,
            'pib_nom': self.staff_data['pib_nom'],
            'position': self.staff_data['position'],
            'rate': self.staff_data['rate'],
            'employment_type': self.staff_data['employment_type'],
            'work_basis': self.staff_data['work_basis'],
            'degree': self.staff_data.get('degree'),
            'vacation_balance': self.staff_data.get('vacation_balance', 0),
        }

        # Знаходимо головне вікно через ланцюжок батьків ПЕРЕД закриттям діалогу
        main_window = self
        while main_window.parent() is not None:
            main_window = main_window.parent()

        if hasattr(main_window, 'navigate_to_builder'):
            # Закриваємо картку співробітника
            self.done(QDialog.DialogCode.Accepted)
            # Переходимо до конструктора з новим документом
            main_window.navigate_to_builder(staff_id=self.staff_id)
        else:
            QMessageBox.warning(self, "Помилка", "Не вдалося знайти головне вікно")

    def _restore_via_scan(self, dialog: QDialog):
        """Реактивує через завантаження скану."""
        dialog.accept()

        # Відкриваємо діалог завантаження скану з попередньо заповненими даними
        scan_dialog = ScanUploadDialog(parent=self, staff_id=self.staff_id)

        # Передаємо дані для попереднього заповнення
        # (можна додати спеціальні методи до ScanUploadDialog для цього)
        result = scan_dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            # Якщо скан завантажено успішно, оновлюємо дані
            QMessageBox.information(
                self, "Успішно",
                f"Скан завантажено для {self.staff_data['pib_nom']}.\n"
                f"Запис про працевлаштування створено."
            )
            self.accept()

    def _hard_delete_staff(self):
        """Повністю видаляє співробітника (hard delete)."""
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService
        from backend.models.staff import Staff

        # Підтвердження
        confirm = QMessageBox.warning(
            self,
            "ОСТОРОЖНО!",
            f"Ви впевнені, що хочете назавжди видалити\n"
            f"{self.staff_data['pib_nom']} ({get_position_label(self.staff_data['position'])})?\n\n"
            f"ЦЯ ДІЯ НЕЗВОРОТНЯ! Всі дані та історія будуть втрачені.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with get_db_context() as db:
                service = StaffService(db, changed_by="USER")
                staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
                if staff:
                    service.hard_delete_staff(staff)
                    QMessageBox.information(
                        self, "Успішно", f"Запис повністю видалено"
                    )
                    self.accept()
                else:
                    QMessageBox.warning(self, "Помилка", "Запис не знайдено")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося видалити запис: {e}")

    def _create_absence_table(self) -> QTableWidget:
        """Створює таблицю відсутностей та особливих відміток."""
        table = QTableWidget()
        table.setObjectName("absence_table")
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["Дата", "Код", "Тип", "Створено", "Дії"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(self.attendance_records))

        for row, record in enumerate(self.attendance_records):
            # Дата
            if record.get('date_end'):
                date_str = f"{record['date'].strftime('%d.%m.%Y')} - {record['date_end'].strftime('%d.%m.%Y')}"
            else:
                date_str = record['date'].strftime("%d.%m.%Y")
            table.setItem(row, 0, QTableWidgetItem(date_str))

            # Код
            table.setItem(row, 1, QTableWidgetItem(record['code']))

            # Тип (з українською назвою)
            type_name = CODE_TO_ABSENCE_NAME.get(record['code'], record['code'])
            table.setItem(row, 2, QTableWidgetItem(type_name))

            # Дата створення запису
            created_at = record.get('created_at')
            created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "—"
            table.setItem(row, 3, QTableWidgetItem(created_str))

            # Кнопки дій
            button_container = QWidget()
            button_layout = QHBoxLayout(button_container)
            button_layout.setContentsMargins(2, 2, 2, 2)
            button_layout.setSpacing(4)

            # Check locking status
            is_locked = False
            
            # Since checking DB for every row is slow, we ideally should have pre-fetched status.
            # But for simplicity and correctness now, we check on demand or rely on simple logic.
            # However, simpler logic (is_past_month) was what we are replacing.
            # Let's use a cached service approach or context if possible. 
            # Actually, _create_absence_table is called once. We can open DB here.
            
            # Use on-the-fly check (not optimal for large lists but safe)
            # Optimization: We can instantiate service once outside loop if we had DB session.
            # Since we cannot easily pass db session here without changing signature, 
            # we will rely on a helper or just check locally if we can.
            
            # BETTER APPROACH: Open DB session for the duration of table creation
            # Note: This tool call replaces a chunk inside the method. I cannot wrap the whole method easily.
            # So I will use a local check function that opens DB briefly if necessary, OR
            # simply open DB for each row (performance hit). 
            
            # Alternative: The user just asked for logic.
            # "for locked attendances buttons to update them should be hiden"
            
            # Let's try to check based on what we know.
            # If we assume we can't easily query DB here efficiency, maybe we can assume:
            # If it's old enough, it's locked? No, manual approval matters.
            
            # I will wrap the check in a quick DB call. It's acceptable for UI responsiveness typically < 100 items.
            is_locked = False
            try:
                from backend.core.database import get_db_context
                from backend.services.tabel_approval_service import TabelApprovalService
                with get_db_context() as db:
                    srv = TabelApprovalService(db)
                    if record.get('is_correction'):
                        is_locked = srv.is_correction_locked(
                            record.get('correction_month'),
                            record.get('correction_year'),
                            record.get('correction_sequence')
                        )
                    else:
                        r_date = record['date']
                        is_locked = srv.is_month_locked(r_date.month, r_date.year)
            except Exception as e:
                print(f"Error checking lock status: {e}")
                is_locked = True # Fail safe

            # Редагування
            if not is_locked:
                edit_btn = QPushButton("✏️")
                edit_btn.setFixedWidth(32)
                edit_btn.setToolTip("Редагувати")
                edit_btn.clicked.connect(lambda checked, r=record: self._on_edit_absence(r))
                button_layout.addWidget(edit_btn)

                # Видалення
                delete_btn = QPushButton("🗑️")
                delete_btn.setFixedWidth(32)
                delete_btn.setToolTip("Видалити")
                delete_btn.clicked.connect(lambda checked, r=record: self._on_delete_absence(r))
                button_layout.addWidget(delete_btn)
            else:
                 # Show lock icon or nothing
                 lock_lbl = QLabel("🔒")
                 lock_lbl.setToolTip("Запис затверджено")
                 button_layout.addWidget(lock_lbl)

            table.setCellWidget(row, 4, button_container)

            # Зберігаємо ID
            table.item(row, 0).setData(Qt.ItemDataRole.UserRole, record['id'])

        return table

    def _on_add_absence(self):
        """Обробляє додавання нової відмітки."""
        from desktop.ui.absence_entry_dialog import AbsenceEntryDialog
        from backend.core.database import get_db_context
        from backend.services.attendance_service import AttendanceService, AttendanceConflictError
        from backend.models.staff import Staff

        dialog = AbsenceEntryDialog(
            staff_id=self.staff_id,
            staff_name=self.staff_data['pib_nom'],
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        result = dialog.get_result()

        # Get employee contract dates
        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
            if not staff:
                QMessageBox.warning(self, "Помилка", "Працівника не знайдено")
                return

            term_start = staff.term_start
            term_end = staff.term_end
            work_basis = staff.work_basis

        # Get proper term name based on work_basis
        basis_labels = {
            "contract": ("контракту", "контракт"),
            "competitive": ("конкурсної основи", "конкурс"),
            "statement": ("заяви", "заява"),
        }
        term_label, term_short = basis_labels.get(work_basis.value, ("терміну", "термін"))

        # Validate dates are within contract period
        if result['is_range']:
            check_date = result['start_date']
            check_end = result['end_date']
        else:
            check_date = result['date']
            check_end = result['date']

        if check_date < term_start or check_end > term_end:
            QMessageBox.warning(
                self,
                f"Дата поза межами {term_label}",
                f"Період {check_date.strftime('%d.%m.%Y')} - {check_end.strftime('%d.%m.%Y')} виходить за межі {term_label} працівника.\n"
                f"{term_short.capitalize()}: {term_start.strftime('%d.%m.%Y')} - {term_end.strftime('%d.%m.%Y')}\n\n"
                f"Відмітку можна додавати лише на період дії {term_label}.",
                QMessageBox.StandardButton.Ok
            )
            return

        # Check if month is locked (approved by HR)
        check_date = result['start_date'] if result['is_range'] else result['date']
        check_end = result['end_date'] if result['is_range'] else result['date']
        target_correction_month = None
        target_correction_year = None
        target_correction_sequence = 1

        from datetime import date as date_today
        from backend.services.tabel_approval_service import TabelApprovalService

        with get_db_context() as db:
            approval_service = TabelApprovalService(db)
            current_month = date_today.today().month
            current_year = date_today.today().year

            can_edit = True
            reason = ""

            # First check: is the attendance date itself in a locked month?
            attendance_month_locked = approval_service.is_month_locked(check_date.month, check_date.year)

            # Second check: does the range include any locked months?
            locked_months_in_range = []
            for month_to_check in range(check_date.month, check_end.month + 1):
                year_to_check = check_date.year if month_to_check >= check_date.month else check_end.year
                if approval_service.is_month_locked(month_to_check, year_to_check):
                    locked_months_in_range.append((month_to_check, year_to_check))

            # Priority 1: If attendance date is in a locked month -> correction for that month
            if attendance_month_locked:
                can_edit = False
                month_name = MONTHS_UKR[check_date.month - 1]
                reason = f"Період ({check_date.strftime('%B %Y')}) вже погоджено з кадрами. Зміни будуть внесені в корегуючий табель."
                target_correction_month = check_date.month
                target_correction_year = check_date.year
            # Priority 2: If current month (when entry is added) is locked -> correction
            elif approval_service.is_month_locked(current_month, current_year):
                can_edit = False
                reason = f"Поточний місяць ({date_today.today().strftime('%B %Y')}) вже погоджено з кадрами. Зміни будуть внесені в корегуючий табель."
                target_correction_month = current_month
                target_correction_year = current_year
            # Priority 3: If range includes locked months (but attendance date is not locked) -> correction
            elif locked_months_in_range:
                if len(locked_months_in_range) == 1:
                    target_correction_month, target_correction_year = locked_months_in_range[0]
                else:
                    target_correction_month, target_correction_year = sorted(locked_months_in_range)[0]

                can_edit = False
                month_name = MONTHS_UKR[target_correction_month - 1]
                reason = f"Період включає заблокований місяць ({month_name} {target_correction_year}). Зміни будуть внесені в корегуючий табель."
            else:
                # No locked months involved - add to main tabel
                can_edit = True
                target_correction_month = check_date.month
                target_correction_year = check_date.year

            if not can_edit:
                # Get next sequence number for this correction month/year
                target_correction_sequence = approval_service.get_or_create_correction_sequence(
                    target_correction_month,
                    target_correction_year
                )

                # Create new correction approval record
                approval_service.record_generation(
                    month=target_correction_month,  # For corrections, month/year = correction month/year
                    year=target_correction_year,
                    is_correction=True,
                    correction_month=target_correction_month,
                    correction_year=target_correction_year,
                    correction_sequence=target_correction_sequence
                )

                reply = QMessageBox.question(
                    self,
                    "Місяць погоджено з кадрами",
                    f"{reason}\n\n"
                    f"Буде створено корегуючий табель #{target_correction_sequence} за {check_date.strftime('%B %Y')}.\n\n"
                    "Бажаєте продовжити?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        try:
            with get_db_context() as db:
                service = AttendanceService(db)

                # Determine if this is a correction (can_edit=False means locked month)
                is_correction_record = not can_edit

                if result['is_range']:
                    service.create_attendance_range(
                        staff_id=self.staff_id,
                        start_date=result['start_date'],
                        end_date=result['end_date'],
                        code=result['code'],
                        notes=result['notes'],
                        is_correction=is_correction_record,
                        correction_month=target_correction_month if is_correction_record else None,
                        correction_year=target_correction_year if is_correction_record else None,
                        correction_sequence=target_correction_sequence if is_correction_record else 1,
                    )
                    modified_date = result['start_date']
                else:
                    service.create_attendance(
                        staff_id=self.staff_id,
                        attendance_date=result['date'],
                        code=result['code'],
                        notes=result['notes'],
                        is_correction=is_correction_record,
                        correction_month=target_correction_month if is_correction_record else None,
                        correction_year=target_correction_year if is_correction_record else None,
                        correction_sequence=target_correction_sequence if is_correction_record else 1,
                    )
                    modified_date = result['date']

            QMessageBox.information(self, "Успіх", "Відмітку додано")
            self._load_data()
            self._refresh_absence_table()
            # Pass correction info for switching to correct tab
            correction_info = {
                "date": modified_date,
                "correction_month": target_correction_month,
                "correction_year": target_correction_year,
            }
            self.attendance_modified.emit(correction_info)

        except AttendanceConflictError as e:
            # Конфлікт дат - показуємо спеціальне повідомлення
            conflict_msg = str(e)
            QMessageBox.warning(
                self,
                "Конфлікт дат",
                f"{conflict_msg}\n\n"
                f"Будь ласка, видаліть конфліктуючі записи з таблиці нижче та спробуйте ще раз.",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося додати відмітку: {e}")

    def _on_upload_scan(self):
        """Обробляє завантаження скану документа."""
        from desktop.ui.scan_upload_dialog import ScanUploadDialog
        from backend.models.document import Document
        from backend.core.database import get_db_context
        from backend.services.document_service import DocumentService
        from backend.services.attendance_service import AttendanceService
        from shared.exceptions import DocumentGenerationError
        from datetime import date as date_today
        from decimal import Decimal

        dialog = ScanUploadDialog(self, staff_id=self.staff_id)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()

        try:
            with get_db_context() as db:
                # Create document entry
                doc = Document(
                    staff_id=data["staff_id"],
                    doc_type=DocumentType(data["doc_type"]),
                    date_start=data["date_start"],
                    date_end=data["date_end"],
                    days_count=data["days_count"],
                    payment_period="Скан завантажено вручну",
                    status=DocumentStatus.SCANNED,  # Scanned document
                )

                # Set workflow timestamps to indicate it's a scanned document
                doc.tabel_added_comment = "Додано зі скану (документ створено співробітником самостійно)"

                db.add(doc)
                db.commit()
                db.refresh(doc)

                # Copy scan file
                scan_path = Path(data["scan_path"])
                if scan_path.exists():
                    output_dir = Path(__file__).parent.parent.parent / "desktop" / "documents" / str(doc.id) / "scans"
                    output_dir.mkdir(parents=True, exist_ok=True)

                    # Copy file with standardized name
                    import shutil
                    new_filename = f"scan_{doc.id}_{scan_path.name}"
                    new_path = output_dir / new_filename
                    shutil.copy2(str(scan_path), str(new_path))

                    doc.file_scan_path = str(new_path)
                    db.commit()

                # Add to attendance if it's a vacation type
                doc_type_value = data["doc_type"]
                if doc_type_value in ["vacation_paid", "vacation_unpaid", "vacation_main", "vacation_additional",
                                       "vacation_study", "vacation_children", "vacation_unpaid_study",
                                       "vacation_unpaid_mandatory", "vacation_unpaid_agreement", "vacation_unpaid_other"]:
                    # Determine code based on doc type
                    paid_vacations = ["vacation_paid", "vacation_main", "vacation_additional", "vacation_children"]
                    if doc_type_value in paid_vacations:
                        code = "В"
                    elif doc_type_value == "vacation_study":
                        code = "Н"
                    elif doc_type_value == "vacation_unpaid":
                        code = "НА"
                    elif doc_type_value == "vacation_unpaid_study":
                        code = "НБ"
                    elif doc_type_value == "vacation_unpaid_mandatory":
                        code = "ДБ"
                    elif doc_type_value in ["vacation_unpaid_agreement", "vacation_unpaid_other"]:
                        code = "БЗ"
                    else:
                        code = "НА"  # Default

                    # Create attendance records
                    att_service = AttendanceService(db)
                    current = data["date_start"]
                    while current <= data["date_end"]:
                        try:
                            att_service.create_attendance(
                                staff_id=data["staff_id"],
                                attendance_date=current,
                                code=code,
                                hours=Decimal("8.0"),
                                notes=f"Скан №{doc.id}",
                            )
                        except Exception:
                            pass  # Skip if already exists
                        current += timedelta(days=1)

                QMessageBox.information(
                    self,
                    "Успіх",
                    f"Скан документа завантажено та збережено.\n"
                    f"ID документа: {doc.id}\n"
                    f"Тип: {data['doc_type']}\n"
                    f"Період: {data['date_start'].strftime('%d.%m.%Y')} - {data['date_end'].strftime('%d.%m.%Y')}"
                )

                # Refresh data
                self._load_data()
                self._refresh_tables()

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти скан:\n{str(e)}")

    def _on_edit_absence(self, record: dict):
        """Обробляє редагування відмітки."""
        from desktop.ui.absence_entry_dialog import AbsenceEntryDialog
        from backend.core.database import get_db_context
        from backend.services.attendance_service import AttendanceService
        from backend.models.staff import Staff

        # Get employee contract dates
        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
            if not staff:
                QMessageBox.warning(self, "Помилка", "Працівника не знайдено")
                return
            term_start = staff.term_start
            term_end = staff.term_end
            work_basis = staff.work_basis

        # Get proper term name based on work_basis
        basis_labels = {
            "contract": ("контракту", "контракт"),
            "competitive": ("конкурсної основи", "конкурс"),
            "statement": ("заяви", "заява"),
        }
        term_label, term_short = basis_labels.get(work_basis.value, ("терміну", "термін"))

        # Check if record date is within contract period
        record_date = record['date']
        record_date_end = record.get('date_end') or record_date

        if record_date > term_end:
            QMessageBox.warning(
                self,
                "Редагування неможливе",
                f"Ця відмітка виходить за межі {term_label} працівника.\n"
                f"{term_short.capitalize()} закінчився: {term_end.strftime('%d.%m.%Y')}",
                QMessageBox.StandardButton.Ok
            )
            return

        dialog = AbsenceEntryDialog(
            staff_id=self.staff_id,
            staff_name=self.staff_data['pib_nom'],
            parent=self,
            edit_data=record,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        result = dialog.get_result()

        # Check if month is locked (approved by HR)
        check_date = result.get('start_date') or result.get('date') or record_date
        check_end = result.get('end_date') or check_date
        target_correction_month = None
        target_correction_year = None
        target_correction_sequence = 1

        from datetime import date as date_today
        from backend.services.tabel_approval_service import TabelApprovalService

        with get_db_context() as db:
            approval_service = TabelApprovalService(db)
            current_month = date_today.today().month
            current_year = date_today.today().year

            can_edit = True
            reason = ""

            # First check: is the attendance date itself in a locked month?
            attendance_month_locked = approval_service.is_month_locked(check_date.month, check_date.year)

            # Second check: does the range include any locked months?
            locked_months_in_range = []
            for month_to_check in range(check_date.month, check_end.month + 1):
                year_to_check = check_date.year if month_to_check >= check_date.month else check_end.year
                if approval_service.is_month_locked(month_to_check, year_to_check):
                    locked_months_in_range.append((month_to_check, year_to_check))

            # Priority 1: If attendance date is in a locked month -> correction for that month
            if attendance_month_locked:
                can_edit = False
                month_name = MONTHS_UKR[check_date.month - 1]
                reason = f"Період ({check_date.strftime('%B %Y')}) вже погоджено з кадрами. Зміни будуть внесені в корегуючий табель."
                target_correction_month = check_date.month
                target_correction_year = check_date.year
            # Priority 2: If current month (when entry is added) is locked -> correction
            elif approval_service.is_month_locked(current_month, current_year):
                can_edit = False
                reason = f"Поточний місяць ({date_today.today().strftime('%B %Y')}) вже погоджено з кадрами. Зміни будуть внесені в корегуючий табель."
                target_correction_month = current_month
                target_correction_year = current_year
            # Priority 3: If range includes locked months (but attendance date is not locked) -> correction
            elif locked_months_in_range:
                if len(locked_months_in_range) == 1:
                    target_correction_month, target_correction_year = locked_months_in_range[0]
                else:
                    target_correction_month, target_correction_year = sorted(locked_months_in_range)[0]

                can_edit = False
                month_name = MONTHS_UKR[target_correction_month - 1]
                reason = f"Період включає заблокований місяць ({month_name} {target_correction_year}). Зміни будуть внесені в корегуючий табель."
            else:
                # No locked months involved - add to main tabel
                can_edit = True
                target_correction_month = check_date.month
                target_correction_year = check_date.year

            if not can_edit:
                # Get next sequence number for this correction month/year
                target_correction_sequence = approval_service.get_or_create_correction_sequence(
                    target_correction_month,
                    target_correction_year
                )

                # Create new correction approval record
                approval_service.record_generation(
                    month=target_correction_month,
                    year=target_correction_year,
                    is_correction=True,
                    correction_month=target_correction_month,
                    correction_year=target_correction_year,
                    correction_sequence=target_correction_sequence
                )

                reply = QMessageBox.question(
                    self,
                    "Місяць погоджено з кадрами",
                    f"{reason}\n\n"
                    f"Буде створено корегуючий табель #{target_correction_sequence} за {check_date.strftime('%B %Y')}.\n\n"
                    "Бажаєте продовжити?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        try:
            with get_db_context() as db:
                service = AttendanceService(db)
                service.update_attendance(
                    attendance_id=record['id'],
                    code=result['code'],
                    notes=result['notes'],
                )

            QMessageBox.information(self, "Успіх", "Відмітку оновлено")
            self._load_data()
            self._refresh_absence_table()
            # Pass correction info
            correction_info = {
                "date": check_date,
                "correction_month": target_correction_month,
                "correction_year": target_correction_year,
            }
            self.attendance_modified.emit(correction_info)

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося оновити відмітку: {e}")

    def _on_delete_absence(self, record: dict):
        """Обробляє видалення відмітки."""
        from backend.core.database import get_db_context
        from backend.services.attendance_service import AttendanceService
        from backend.models.staff import Staff

        # Показуємо діалог з полем для коментаря
        from PyQt6.QtWidgets import QInputDialog, QLineEdit

        comment, ok = QInputDialog.getText(
            self,
            "Видалення відмітки",
            "Введіть причину видалення:",
            QLineEdit.EchoMode.Normal,
            ""
        )

        if not ok or not comment.strip():
            return

        # Get employee contract dates
        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
            term_start = staff.term_start if staff else None

        # Check if month is locked (approved by HR)
        record_date = record['date']
        target_correction_month = None
        target_correction_year = None
        target_correction_sequence = 1

        from datetime import date as date_today
        from backend.services.tabel_approval_service import TabelApprovalService

        with get_db_context() as db:
            approval_service = TabelApprovalService(db)
            current_month = date_today.today().month
            current_year = date_today.today().year

            can_edit = True
            reason = ""

            # First check: is the record date itself in a locked month?
            record_month_locked = approval_service.is_month_locked(record_date.month, record_date.year)

            # Priority 1: If record date is in a locked month -> correction for that month
            if record_month_locked:
                can_edit = False
                month_name = MONTHS_UKR[record_date.month - 1]
                reason = f"Період ({record_date.strftime('%B %Y')}) вже погоджено з кадрами. Зміни будуть внесені в корегуючий табель."
                target_correction_month = record_date.month
                target_correction_year = record_date.year
            # Priority 2: If current month (when entry is deleted) is locked -> correction
            elif approval_service.is_month_locked(current_month, current_year):
                can_edit = False
                reason = f"Поточний місяць ({date_today.today().strftime('%B %Y')}) вже погоджено з кадрами. Зміни будуть внесені в корегуючий табель."
                target_correction_month = current_month
                target_correction_year = current_year
            else:
                # No locked months involved - delete from main tabel
                can_edit = True
                target_correction_month = record_date.month
                target_correction_year = record_date.year

            if not can_edit:
                # Get next sequence number for this correction month/year
                target_correction_sequence = approval_service.get_or_create_correction_sequence(
                    target_correction_month,
                    target_correction_year
                )

                # Create new correction approval record
                approval_service.record_generation(
                    month=target_correction_month,
                    year=target_correction_year,
                    is_correction=True,
                    correction_month=target_correction_month,
                    correction_year=target_correction_year,
                    correction_sequence=target_correction_sequence
                )

                reply = QMessageBox.question(
                    self,
                    "Місяць погоджено з кадрами",
                    f"{reason}\n\n"
                    f"Буде створено корегуючий табель #{target_correction_sequence} за {record_date.strftime('%B %Y')}.\n\n"
                    "Бажаєте продовжити?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        try:
            with get_db_context() as db:
                service = AttendanceService(db)
                # Видаляємо з коментарем
                service.delete_attendance(record['id'], notes=comment.strip())

            QMessageBox.information(self, "Успіх", "Відмітку видалено")
            self._load_data()
            self._refresh_absence_table()
            # Pass correction info
            correction_info = {
                "date": record_date,
                "correction_month": target_correction_month,
                "correction_year": target_correction_year,
            }
            self.attendance_modified.emit(correction_info)

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося видалити відмітку: {e}")

    def _refresh_absence_table(self):
        """Оновлює таблицю відсутностей."""
        new_table = self._create_absence_table()

        layout = self.layout()
        if layout and hasattr(self, '_absence_table'):
            old_table_index = -1
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self._absence_table:
                    old_table_index = i
                    break

            if old_table_index >= 0:
                layout.takeAt(old_table_index)
                self._absence_table.setParent(None)
                layout.insertWidget(old_table_index, new_table)
                self._absence_table = new_table
