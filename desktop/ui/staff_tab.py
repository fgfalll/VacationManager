"""Вкладка управління персоналом."""

from datetime import date

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QDialog,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
    QDateEdit,
    QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from desktop.widgets.status_badge import StatusBadge
from shared.enums import EmploymentType, WorkBasis


class StaffTab(QWidget):
    """
    Вкладка для управління списком співробітників.

    Містить таблицю персоналу з можливістю додавання,
    редагування та перегляду деталей.
    """

    document_created = pyqtSignal()

    def __init__(self):
        """Ініціалізує вкладку персоналу."""
        super().__init__()
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        layout = QVBoxLayout(self)

        # Панель пошуку та фільтрів
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Пошук за ПІБ...")
        self.search_input.textChanged.connect(self._on_search)

        self.filter_active = QComboBox()
        self.filter_active.addItems(["Всі", "Активні", "Неактивні"])
        self.filter_active.currentIndexChanged.connect(self._load_data)

        self.refresh_btn = QPushButton("Оновити")
        self.refresh_btn.clicked.connect(self._load_data)

        search_layout.addWidget(QLabel("Пошук:"))
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(QLabel("Фільтр:"))
        search_layout.addWidget(self.filter_active)
        search_layout.addWidget(self.refresh_btn)
        search_layout.addStretch()

        layout.addLayout(search_layout)

        # Таблиця
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ПІБ",
            "Посада",
            "Ставка",
            "Тип",
            "Контракт",
            "Баланс",
            "Дні до кінця",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Кнопки дій
        actions_layout = QHBoxLayout()

        self.add_btn = QPushButton("Додати")
        self.add_btn.clicked.connect(self._add_staff)

        self.edit_btn = QPushButton("Редагувати")
        self.edit_btn.clicked.connect(self._edit_staff)
        self.edit_btn.setEnabled(False)

        self.delete_btn = QPushButton("Видалити")
        self.delete_btn.clicked.connect(self._delete_staff)
        self.delete_btn.setEnabled(False)

        self.view_docs_btn = QPushButton("Документи")
        self.view_docs_btn.clicked.connect(self._view_documents)
        self.view_docs_btn.setEnabled(False)

        actions_layout.addWidget(self.add_btn)
        actions_layout.addWidget(self.edit_btn)
        actions_layout.addWidget(self.delete_btn)
        actions_layout.addWidget(self.view_docs_btn)
        actions_layout.addStretch()

        layout.addLayout(actions_layout)

        # Підключення сигналів таблиці
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def _load_data(self):
        """Завантажує дані в таблицю."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            query = db.query(Staff)

            # Фільтр активності
            filter_idx = self.filter_active.currentIndex()
            if filter_idx == 1:  # Активні
                query = query.filter(Staff.is_active == True)
            elif filter_idx == 2:  # Неактивні
                query = query.filter(Staff.is_active == False)

            staff_list = query.order_by(Staff.pib_nom).all()

            self.table.setRowCount(len(staff_list))

            for row, staff in enumerate(staff_list):
                self._set_row_data(row, staff)

    def _set_row_data(self, row: int, staff):
        """Встановлює дані в рядок таблиці."""
        from backend.models.settings import SystemSettings

        # Отримуємо поріг попередження з налаштувань
        warning_days = 30  # За замовчуванням
        try:
            with get_db_context() as db:
                warning_days = SystemSettings.get_value(db, "contract_warning_days", 30)
        except Exception:
            pass

        # ПІБ - з іконкою попередження якщо контракт закінчується
        name_text = staff.pib_nom
        if staff.is_term_expired:
            name_text = "⚠️ " + name_text
        elif staff.days_until_term_end <= warning_days:
            name_text = "⏰ " + name_text

        self.table.setItem(row, 0, QTableWidgetItem(name_text))
        self.table.setItem(row, 1, QTableWidgetItem(staff.position))
        self.table.setItem(row, 2, QTableWidgetItem(str(staff.rate)))
        self.table.setItem(row, 3, QTableWidgetItem(staff.employment_type.value))

        term_item = QTableWidgetItem(
            f"{staff.term_start.strftime('%d.%m.%Y')} - "
            f"{staff.term_end.strftime('%d.%m.%Y')}"
        )
        self.table.setItem(row, 4, term_item)

        balance_item = QTableWidgetItem(str(staff.vacation_balance))
        self.table.setItem(row, 5, balance_item)

        # Дні до кінця контракту з підсвіткою
        days_text = str(staff.days_until_term_end)
        if staff.is_term_expired:
            days_text = f"⛔ {days_text}"
        elif staff.days_until_term_end <= warning_days:
            days_text = f"⚠️ {days_text}"

        days_item = QTableWidgetItem(days_text)

        # Підсвітка рядка червоним якщо контракт закінчується
        if staff.is_term_expired:
            for col in range(7):
                item = QTableWidgetItem() if col != 0 else self.table.item(row, 0)
                if col != 0:
                    self.table.setItem(row, col, item)
                item.setBackground(QColor("#FFCCCC"))
        elif staff.days_until_term_end <= warning_days:
            # Тільки days_item підсвітчуємо
            days_item.setBackground(QColor("#FFEBEE"))
            days_item.setForeground(QColor("#D32F2F"))

        self.table.setItem(row, 6, days_item)

        # Зберігаємо ID в першому елементі
        self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, staff.id)

    def _on_search(self):
        """Фільтрує дані при пошуку."""
        search_text = self.search_input.text().lower()

        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            match = search_text in name
            self.table.setRowHidden(row, not match)

    def _on_selection_changed(self):
        """Обробляє зміну виділення."""
        has_selection = len(self.table.selectedItems()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.view_docs_btn.setEnabled(has_selection)

    def _add_staff(self):
        """Відкриває діалог додавання співробітника."""
        dialog = StaffDialog(parent=self)
        if dialog.exec():
            self._load_data()

    def _edit_staff(self):
        """Відкриває діалог редагування співробітника."""
        item = self.table.currentItem()
        if not item:
            return

        staff_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        dialog = StaffDialog(staff_id, parent=self)
        if dialog.exec():
            self._load_data()

    def _delete_staff(self):
        """Видаляє співробітника."""
        from backend.models.staff import Staff
        from backend.models.document import Document
        from backend.core.database import get_db_context
        from PyQt6.QtWidgets import QMessageBox
        from shared.enums import DocumentStatus

        item = self.table.currentItem()
        if not item:
            return

        staff_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

        with get_db_context() as db:
            # Перевіряємо наявність документів
            documents = (
                db.query(Document)
                .filter(Document.staff_id == staff_id)
                .all()
            )

            # Кількість неархівованих документів
            non_archived = [d for d in documents if d.status != DocumentStatus.PROCESSED]

            if non_archived:
                doc_info = "\n".join([
                    f"  - {d.doc_type.value}: {d.date_start} - {d.date_end} ({d.status.value})"
                    for d in non_archived[:5]
                ])
                if len(non_archived) > 5:
                    doc_info += f"\n  ... та ще {len(non_archived) - 5} документів"

                QMessageBox.warning(
                    self,
                    "Неможливо видалити",
                    f"Неможливо видалити співробітника, оскільки є "
                    f"{len(non_archived)} незавершених документів:\n\n{doc_info}\n\n"
                    f"Спочатку архівуйте або видаліть ці документи."
                )
                return

            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff:
                return

            reply = QMessageBox.question(
                self,
                "Підтвердження",
                f"Деактивувати співробітника {staff.pib_nom}?\n\n"
                "Це soft delete - дані залишаться в системі.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                staff.is_active = False
                db.commit()
                self._load_data()

    def _view_documents(self):
        """Відкриває список документів співробітника."""
        # TODO: Реалізувати перегляд документів
        pass

    def refresh_documents(self):
        """Оновлює список документів (слот для сигналу)."""
        # TODO: Оновити список документів
        pass

    def refresh(self):
        """Оновлює дані вкладки."""
        self._load_data()


class StaffDialog(QDialog):
    """Діалог для створення/редагування співробітника."""

    def __init__(self, staff_id: int | None = None, parent=None):
        """Ініціалізує діалог."""
        super().__init__(parent)
        self.staff_id = staff_id
        self._setup_ui()
        if staff_id:
            self._load_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("Співробітник" if self.staff_id is None else "Редагування")
        self.setMinimumWidth(500)

        layout = QFormLayout(self)

        self.pib_input = QLineEdit()
        self.degree_input = QLineEdit()

        # Посада - dropdown with predefined values
        self.position_input = QComboBox()
        self.position_input.setEditable(True)
        self.position_input.addItems([
            "В.о завідувача кафедри",
            "професор",
            "доцент",
            "ст. викладач",
            "асистент",
            "фахівець",
        ])

        # Ставка - from 1.0 to 0.1 with step 0.1
        self.rate_input = QDoubleSpinBox()
        self.rate_input.setRange(0.1, 1.0)
        self.rate_input.setSingleStep(0.1)
        self.rate_input.setDecimals(1)
        self.rate_input.setValue(1.0)

        # Тип працевлаштування - with Ukrainian labels
        self.employment_type_input = QComboBox()
        self.employment_type_items = {
            EmploymentType.MAIN: "Основне місце роботи",
            EmploymentType.INTERNAL: "Внутрішній сумісник",
            EmploymentType.EXTERNAL: "Зовнішній сумісник",
        }
        for et, label in self.employment_type_items.items():
            self.employment_type_input.addItem(label, et)

        self.work_basis_input = QComboBox()
        self.work_basis_input.addItems([e.value for e in WorkBasis])

        # Контракт - dates
        self.term_start_input = QDateEdit()
        self.term_start_input.setCalendarPopup(True)
        self.term_end_input = QDateEdit()
        self.term_end_input.setCalendarPopup(True)

        self.vacation_balance_input = QSpinBox()
        self.vacation_balance_input.setRange(0, 365)

        layout.addRow("ПІБ:", self.pib_input)
        layout.addRow("Вчений ступінь:", self.degree_input)
        layout.addRow("Посада:", self.position_input)
        layout.addRow("Ставка:", self.rate_input)
        layout.addRow("Тип працевлаштування:", self.employment_type_input)
        layout.addRow("Основа:", self.work_basis_input)
        layout.addRow("Період контракту (початок):", self.term_start_input)
        layout.addRow("Період контракту (кінець):", self.term_end_input)
        layout.addRow("Наявна кількість днів відпустки:", self.vacation_balance_input)

        # Кнопки
        from PyQt6.QtWidgets import QDialogButtonBox

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_data(self):
        """Завантажує дані співробітника."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
            if staff:
                self.pib_input.setText(staff.pib_nom)
                self.degree_input.setText(staff.degree or "")
                # Set position text in editable combobox
                index = self.position_input.findText(staff.position)
                if index >= 0:
                    self.position_input.setCurrentIndex(index)
                else:
                    self.position_input.setCurrentText(staff.position)
                # Rate is now decimal (1.0 to 0.1)
                self.rate_input.setValue(float(staff.rate))
                # Find employment type by enum value
                for i in range(self.employment_type_input.count()):
                    if self.employment_type_input.itemData(i) == staff.employment_type:
                        self.employment_type_input.setCurrentIndex(i)
                        break
                self.work_basis_input.setCurrentText(staff.work_basis.value)
                self.term_start_input.setDate(staff.term_start)
                self.term_end_input.setDate(staff.term_end)
                self.vacation_balance_input.setValue(staff.vacation_balance)

    def accept(self):
        """Зберігає дані."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        # Rate is now already in decimal format (1.0 to 0.1)
        rate = self.rate_input.value()
        # Get employment type from stored data
        employment_type = self.employment_type_input.currentData()

        with get_db_context() as db:
            if self.staff_id is None:
                # Створення
                staff = Staff(
                    pib_nom=self.pib_input.text(),
                    degree=self.degree_input.text() or None,
                    position=self.position_input.currentText(),
                    rate=rate,
                    employment_type=employment_type,
                    work_basis=WorkBasis(self.work_basis_input.currentText()),
                    term_start=self.term_start_input.date().toPyDate(),
                    term_end=self.term_end_input.date().toPyDate(),
                    vacation_balance=self.vacation_balance_input.value(),
                )
                db.add(staff)
            else:
                # Оновлення
                staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
                if staff:
                    staff.pib_nom = self.pib_input.text()
                    staff.degree = self.degree_input.text() or None
                    staff.position = self.position_input.currentText()
                    staff.rate = rate
                    staff.employment_type = employment_type
                    staff.work_basis = WorkBasis(self.work_basis_input.currentText())
                    staff.term_start = self.term_start_input.date().toPyDate()
                    staff.term_end = self.term_end_input.date().toPyDate()
                    staff.vacation_balance = self.vacation_balance_input.value()

            db.commit()
        super().accept()
