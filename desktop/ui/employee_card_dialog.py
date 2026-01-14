"""Діалог картки працівника з повною історією змін."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QVBoxLayout,
)

from shared.enums import StaffActionType


class EmployeeCardDialog(QDialog):
    """
    Діалог картки працівника.

    Показує поточну інформацію та повну історію змін.
    Дозволяє відновлення неактивних співробітників.
    """

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

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle(f"Картка працівника: {self.staff_data['pib_nom']}")
        self.setMinimumSize(1000, 700)

        layout = QVBoxLayout(self)

        # Інформація про співробітника
        layout.addWidget(self._create_info_section())

        # Історія змін
        layout.addWidget(QLabel("<b>Історія змін</b>"))
        layout.addWidget(self._create_history_table())

        # Кнопки дій
        layout.addLayout(self._create_action_buttons())

    def _create_info_section(self) -> QFrame:
        """Створює секцію з поточною інформацією."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background-color: #f5f5f5; border-radius: 5px; padding: 10px; }")

        layout = QVBoxLayout(frame)

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

        # Деталі
        details_text = f"""
        <table cellspacing="5">
            <tr><td><b>Посада:</b></td><td>{self.staff_data['position']}</td></tr>
            <tr><td><b>Вчений ступінь:</b></td><td>{self.staff_data['degree'] or '—'}</td></tr>
            <tr><td><b>Ставка:</b></td><td>{self.staff_data['rate']}</td></tr>
            <tr><td><b>Тип працевлаштування:</b></td><td>{self._format_employment_type(self.staff_data['employment_type'].value)}</td></tr>
            <tr><td><b>Основа:</b></td><td>{self.staff_data['work_basis'].value}</td></tr>
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
        layout.addStretch()

        if not self.staff_data['is_active']:
            # Кнопка відновлення для неактивних
            restore_btn = QPushButton("Відновити (новий запис)")
            restore_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """
            )
            restore_btn.clicked.connect(self._restore_staff)
            layout.addWidget(restore_btn)

        # Закрити
        close_btn = QPushButton("Закрити")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        return layout

    def _format_employment_type(self, value: str) -> str:
        """Форматує тип працевлаштування для відображення."""
        type_map = {
            "main": "Основне місце роботи",
            "internal": "Внутрішній сумісник",
            "external": "Зовнішній сумісник",
        }
        return type_map.get(value, value)

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
