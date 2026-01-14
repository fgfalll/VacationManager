"""Діалог картки працівника з повною історією змін."""

from datetime import date

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
)

from shared.enums import StaffActionType
from shared.absence_types import CODE_TO_ABSENCE_NAME


class EmployeeCardDialog(QDialog):
    """
    Діалог картки працівника.

    Показує поточну інформацію та повну історію змін.
    Дозволяє відновлення неактивних співробітників.
    """

    # Сигнали для комунікації з батьківським вікном
    edit_document = pyqtSignal(int)  # document_id
    delete_document = pyqtSignal(int)  # document_id

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

            service = StaffService(db)
            history = service.get_staff_history(self.staff_id)

            # Зберігаємо дані перед закриттям сесії (detached instance problem)
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
                })

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle(f"Картка працівника: {self.staff_data['pib_nom']}")
        self.setMinimumSize(1000, 900)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Інформація про співробітника
        layout.addWidget(self._create_info_section())

        # Історія відпусток
        layout.addWidget(QLabel("<b>Історія відпусток</b>"))
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
        details_text = f"""
        <table cellspacing="5">
            <tr><td><b>Посада:</b></td><td>{self._format_position(self.staff_data['position'])}</td></tr>
            <tr><td><b>Вчений ступінь:</b></td><td>{self.staff_data['degree'] or '—'}</td></tr>
            <tr><td><b>Ставка:</b></td><td>{self.staff_data['rate']}</td></tr>
            <tr><td><b>Тип працевлаштування:</b></td><td>{self._format_employment_type(self.staff_data['employment_type'].value)}</td></tr>
            <tr><td><b>Основа:</b></td><td>{self._format_work_basis(self.staff_data['work_basis'].value)}</td></tr>
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
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(self.vacation_documents))

        # Status colors
        status_colors = {
            "draft": QColor("#E0E0E0"),       # Сірий - чернетка
            "on_signature": QColor("#FFE082"), # Жовтий - на підписі
            "signed": QColor("#C8E6C9"),       # Зелений - підписано
            "processed": QColor("#81D4FA"),    # Блакитний - оброблено
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
            }
            doc_type = doc_type_labels.get(doc['doc_type'], doc['doc_type'])
            table.setItem(row, 1, QTableWidgetItem(doc_type))

            # Кількість днів
            table.setItem(row, 2, QTableWidgetItem(str(doc['days_count'])))

            # Статус з кольором
            status_labels = {
                "draft": "Чернетка",
                "on_signature": "На підписі",
                "signed": "Підписано",
                "processed": "Оброблено",
            }
            status = status_labels.get(doc['status'], doc['status'])
            status_item = QTableWidgetItem(status)
            status_item.setBackground(status_colors.get(doc['status'], QColor("white")))
            table.setItem(row, 3, status_item)

            # Дата створення
            created = doc['created_at'].strftime("%d.%m.%Y %H:%M") if doc['created_at'] else "—"
            table.setItem(row, 4, QTableWidgetItem(created))

            # Кнопки дій
            button_container = QWidget()
            button_layout = QHBoxLayout(button_container)
            button_layout.setContentsMargins(2, 2, 2, 2)
            button_layout.setSpacing(4)

            # Перевіряємо чи документ відскановано (не можна редагувати/видаляти)
            is_scanned = doc['status'] in ('processed', 'signed')

            # Кнопка редагування (для чернеток та на підписі)
            edit_btn = QPushButton("✏️")
            edit_btn.setFixedWidth(32)
            edit_btn.setToolTip("Редагувати документ")
            edit_btn.setEnabled(not is_scanned)
            if is_scanned:
                edit_btn.setToolTip("Неможливо редагувати (документ відскановано)")
            edit_btn.clicked.connect(lambda checked, d=doc: self._on_edit_document(d['id']))
            button_layout.addWidget(edit_btn)

            # Кнопка видалення
            delete_btn = QPushButton("🗑️")
            delete_btn.setFixedWidth(32)
            delete_btn.setToolTip("Видалити документ")
            delete_btn.setEnabled(not is_scanned)
            if is_scanned:
                delete_btn.setToolTip("Неможливо видалити (документ відскановано)")
            delete_btn.clicked.connect(lambda checked, d=doc: self._on_delete_document(d['id']))
            button_layout.addWidget(delete_btn)

            # Кнопка етапів підписання
            workflow_btn = QPushButton("📋")
            workflow_btn.setFixedWidth(32)
            workflow_btn.setToolTip("Етапи підписання")
            workflow_btn.clicked.connect(lambda checked, d=doc: self._on_workflow_document(d['id']))
            button_layout.addWidget(workflow_btn)

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

            elif doc.status == DocumentStatus.ON_SIGNATURE:
                # На підписі - показуємо діалог введення причини
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

            elif doc.status in (DocumentStatus.SIGNED, DocumentStatus.PROCESSED):
                QMessageBox.warning(
                    self,
                    "Помилка",
                    "Неможливо видалити підписаний або оброблений документ."
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
                checkbox = QCheckBox(f"{step_icon} {step_name}")
                step_data = progress.get(step_key, {})
                checkbox.setChecked(step_data.get("completed", False))
                checkboxes[step_key] = checkbox
                step_layout.addWidget(checkbox)

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
                checkbox = QCheckBox(f"{icon} {approver_name}")
                is_completed = approver_name in completed_approvers
                checkbox.setChecked(is_completed)
                approver_checkboxes[step_key] = checkbox
                step_layout.addWidget(checkbox)

                comment_edit = QLineEdit()
                comment_edit.setPlaceholderText("Коментар")
                comment_edit.setMaximumWidth(200)
                approver_comments[step_key] = comment_edit
                step_layout.addWidget(comment_edit)

                dialog_layout.addLayout(step_layout)

            # Add final steps
            dialog_layout.addWidget(QLabel("<b>Завершальні етапи</b>"))

            for step_key, step_name, step_icon in final_steps:
                step_layout = QHBoxLayout()
                checkbox = QCheckBox(f"{step_icon} {step_name}")
                step_data = progress.get(step_key, {})
                checkbox.setChecked(step_data.get("completed", False))
                checkboxes[step_key] = checkbox
                step_layout.addWidget(checkbox)

                comment_edit = QLineEdit()
                comment_edit.setPlaceholderText("Коментар")
                comment_edit.setText(step_data.get("comment") or "")
                comment_edit.setMaximumWidth(200)
                comments[step_key] = comment_edit
                step_layout.addWidget(comment_edit)

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
                now = datetime.datetime.now()

                # Update fixed steps
                for step_key, _, _ in fixed_steps:
                    checkbox = checkboxes[step_key]
                    comment = comments[step_key].text().strip() or None

                    if step_key == "applicant":
                        doc.applicant_signed_at = now if checkbox.isChecked() else None
                        doc.applicant_signed_comment = comment
                    elif step_key == "approval":
                        doc.approval_at = now if checkbox.isChecked() else None
                        doc.approval_comment = comment
                    elif step_key == "department_head":
                        doc.department_head_at = now if checkbox.isChecked() else None
                        doc.department_head_comment = comment
                    elif step_key == "rector":
                        doc.rector_at = now if checkbox.isChecked() else None
                        doc.rector_comment = comment
                    elif step_key == "scanned":
                        doc.scanned_at = now if checkbox.isChecked() else None
                        doc.scanned_comment = comment
                    elif step_key == "tabel":
                        doc.tabel_added_at = now if checkbox.isChecked() else None
                        doc.tabel_added_comment = comment

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
        """Форматує посаду - перша літера велика."""
        if not position:
            return position
        # Capitalize first letter of each word
        return position.title()

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

    def _restore_staff(self):
        """Відновлює співробітника (реактивує запис з новими даними)."""
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService
        from backend.models.staff import Staff
        from datetime import date, timedelta
        from PyQt6.QtWidgets import QDialog, QFormLayout, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QDialogButtonBox, QLineEdit
        from shared.enums import EmploymentType, WorkBasis

        # Створюємо діалог для введення нових даних
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Відновлення: {self.staff_data['pib_nom']}")
        dialog.setMinimumWidth(500)

        layout = QFormLayout(dialog)

        # Посада - dropdown with predefined values
        position = QComboBox()
        position.setEditable(True)
        position.addItems([
            "Завідувач кафедри",
            "В.о завідувача кафедри",
            "професор",
            "доцент",
            "ст. викладач",
            "асистент",
            "фахівець",
        ])
        # Set current position
        pos_index = position.findText(self.staff_data['position'])
        if pos_index >= 0:
            position.setCurrentIndex(pos_index)
        else:
            position.setCurrentText(self.staff_data['position'])

        # Вчений ступінь
        degree = QLineEdit(self.staff_data['degree'] or "")

        # Ставка
        rate = QDoubleSpinBox()
        rate.setRange(0.1, 1.0)
        rate.setSingleStep(0.1)
        rate.setDecimals(1)
        rate.setValue(float(self.staff_data['rate']))

        # Тип працевлаштування - з українськими мітками
        employment_type = QComboBox()
        employment_type_items = {
            EmploymentType.MAIN: "Основне місце роботи",
            EmploymentType.INTERNAL: "Внутрішній сумісник",
            EmploymentType.EXTERNAL: "Зовнішній сумісник",
        }
        for et, label in employment_type_items.items():
            employment_type.addItem(label, et)
        # Set current employment type
        for i in range(employment_type.count()):
            if employment_type.itemData(i) == self.staff_data['employment_type']:
                employment_type.setCurrentIndex(i)
                break

        # Основа роботи - з українськими мітками
        work_basis = QComboBox()
        work_basis_items = {
            WorkBasis.CONTRACT: "Контракт",
            WorkBasis.COMPETITIVE: "Конкурсна основа",
            WorkBasis.STATEMENT: "Заява",
        }
        for wb, label in work_basis_items.items():
            work_basis.addItem(label, wb)
        # Set current work basis
        for i in range(work_basis.count()):
            if work_basis.itemData(i) == self.staff_data['work_basis']:
                work_basis.setCurrentIndex(i)
                break

        # Дати контракту
        term_start = QDateEdit()
        term_start.setCalendarPopup(True)
        term_start.setDate(date.today())

        term_end = QDateEdit()
        term_end.setCalendarPopup(True)
        # За замовчуванням +1 рік від початку
        future_date = date.today() + timedelta(days=365)
        term_end.setDate(future_date)

        vacation_balance = QSpinBox()
        vacation_balance.setRange(0, 365)
        vacation_balance.setValue(self.staff_data['vacation_balance'])

        # Додаємо поля до форми
        layout.addRow("Посада:", position)
        layout.addRow("Вчений ступінь:", degree)
        layout.addRow("Ставка:", rate)
        layout.addRow("Тип працевлаштування:", employment_type)
        layout.addRow("Основа:", work_basis)
        layout.addRow("Початок контракту:", term_start)
        layout.addRow("Кінець контракту:", term_end)
        layout.addRow("Баланс відпустки:", vacation_balance)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec():
            # Прямо реактивуємо старий запис з новими даними
            with get_db_context() as db:
                service = StaffService(db, changed_by="USER")

                # Отримуємо оригінальний запис
                old_staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
                if not old_staff:
                    QMessageBox.critical(self, "Помилка", "Запис не знайдено")
                    return

                # Нові дані для оновлення
                new_data = {
                    "pib_nom": self.staff_data['pib_nom'],  # Ім'я не змінюється
                    "degree": degree.text() or None,
                    "position": position.currentText(),
                    "rate": rate.value(),
                    "employment_type": employment_type.currentData(),
                    "work_basis": work_basis.currentData(),
                    "term_start": term_start.date().toPyDate(),
                    "term_end": term_end.date().toPyDate(),
                    "vacation_balance": vacation_balance.value(),
                    "is_active": True,  # Реактивуємо
                }

                try:
                    service.restore_staff(old_staff, new_data)
                    QMessageBox.information(
                        self, "Успішно", f"Запис відновлено з новими даними"
                    )
                    self.accept()
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося відновити запис: {e}")

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
            f"{self.staff_data['pib_nom']} ({self.staff_data['position']})?\n\n"
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

            # Перевіряємо чи запис минулого місяця
            record_date = record['date']
            today = date.today()
            is_past_month = record_date.year < today.year or (
                record_date.year == today.year and record_date.month < today.month
            )

            # Редагування
            edit_btn = QPushButton("✏️")
            edit_btn.setFixedWidth(32)
            edit_btn.setToolTip("Редагувати")
            edit_btn.setEnabled(not is_past_month)
            edit_btn.clicked.connect(lambda checked, r=record: self._on_edit_absence(r))
            button_layout.addWidget(edit_btn)

            # Видалення
            delete_btn = QPushButton("🗑️")
            delete_btn.setFixedWidth(32)
            delete_btn.setToolTip("Видалити")
            delete_btn.clicked.connect(lambda checked, r=record: self._on_delete_absence(r))
            button_layout.addWidget(delete_btn)

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

        try:
            with get_db_context() as db:
                service = AttendanceService(db)

                if result['is_range']:
                    service.create_attendance_range(
                        staff_id=self.staff_id,
                        start_date=result['start_date'],
                        end_date=result['end_date'],
                        code=result['code'],
                        notes=result['notes'],
                    )
                else:
                    service.create_attendance(
                        staff_id=self.staff_id,
                        attendance_date=result['date'],
                        code=result['code'],
                        notes=result['notes'],
                    )

            QMessageBox.information(self, "Успіх", "Відмітку додано")
            self._load_data()
            self._refresh_absence_table()

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

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося оновити відмітку: {e}")

    def _on_delete_absence(self, record: dict):
        """Обробляє видалення відмітки."""
        from backend.core.database import get_db_context
        from backend.services.attendance_service import AttendanceService

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

        try:
            with get_db_context() as db:
                service = AttendanceService(db)
                # Видаляємо з коментарем
                service.delete_attendance(record['id'], notes=comment.strip())

            QMessageBox.information(self, "Успіх", "Відмітку видалено")
            self._load_data()
            self._refresh_absence_table()

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
