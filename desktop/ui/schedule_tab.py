"""Вкладка річного графіка відпусток."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QSpinBox,
    QDialog,
    QFormLayout,
    QDateEdit,
    QHeaderView,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from datetime import date

from shared.enums import EmploymentType


class ScheduleTab(QWidget):
    """
    Вкладка для управління річним графіком відпусток.

    Містить таблицю записів графіку з можливістю додавання,
    редагування та автоматичного розподілу.
    """

    data_changed = pyqtSignal()

    def __init__(self):
        """Ініціалізує вкладку графіку."""
        super().__init__()
        self.current_year = date.today().year
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        layout = QVBoxLayout(self)

        # Панель керування
        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel("Рік:"))
        self.year_input = QSpinBox()
        self.year_input.setRange(2020, 2100)
        self.year_input.setValue(self.current_year)
        self.year_input.valueChanged.connect(self._on_year_changed)
        control_layout.addWidget(self.year_input)

        self.refresh_btn = QPushButton("Оновити")
        self.refresh_btn.clicked.connect(self._load_data)
        control_layout.addWidget(self.refresh_btn)

        self.auto_distribute_btn = QPushButton("Авторозподіл")
        self.auto_distribute_btn.clicked.connect(self._auto_distribute)
        control_layout.addWidget(self.auto_distribute_btn)

        control_layout.addStretch()

        layout.addLayout(control_layout)

        # Таблиця
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Співробітник",
            "Початок",
            "Кінець",
            "Днів",
            "Ставка",
            "Використано",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Кнопки дій
        actions_layout = QHBoxLayout()

        self.add_btn = QPushButton("Додати")
        self.add_btn.clicked.connect(self._add_entry)

        self.edit_btn = QPushButton("Редагувати")
        self.edit_btn.clicked.connect(self._edit_entry)
        self.edit_btn.setEnabled(False)

        self.delete_btn = QPushButton("Видалити")
        self.delete_btn.clicked.connect(self._delete_entry)
        self.delete_btn.setEnabled(False)

        self.create_doc_btn = QPushButton("Створити заяву")
        self.create_doc_btn.clicked.connect(self._create_document)
        self.create_doc_btn.setEnabled(False)

        actions_layout.addWidget(self.add_btn)
        actions_layout.addWidget(self.edit_btn)
        actions_layout.addWidget(self.delete_btn)
        actions_layout.addWidget(self.create_doc_btn)
        actions_layout.addStretch()

        layout.addLayout(actions_layout)

        # Підключення сигналів
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def _load_data(self):
        """Завантажує дані графіку."""
        from backend.models.schedule import AnnualSchedule
        from backend.core.database import get_db_context

        year = self.year_input.value()
        with get_db_context() as db:
            entries = (
                db.query(AnnualSchedule)
                .filter(AnnualSchedule.year == year)
                .order_by(AnnualSchedule.planned_start)
                .all()
            )

            self.table.setRowCount(len(entries))

            for row, entry in enumerate(entries):
                self._set_row_data(row, entry)

    def _set_row_data(self, row: int, entry):
        """Встановлює дані в рядок таблиці."""
        self.table.setItem(row, 0, QTableWidgetItem(entry.staff.pib_nom))
        self.table.setItem(
            row,
            1,
            QTableWidgetItem(entry.planned_start.strftime("%d.%m.%Y")),
        )
        self.table.setItem(
            row,
            2,
            QTableWidgetItem(entry.planned_end.strftime("%d.%m.%Y")),
        )
        self.table.setItem(row, 3, QTableWidgetItem(str(entry.days_count)))
        self.table.setItem(row, 4, QTableWidgetItem(str(entry.staff.rate)))

        used_item = QTableWidgetItem("Так" if entry.is_used else "Ні")
        if entry.is_used:
            used_item.setBackground(QColor("#CCFFCC"))
        else:
            used_item.setBackground(QColor("#FFFFCC"))
        self.table.setItem(row, 5, used_item)

        # Зберігаємо ID
        self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, entry.id)

    def _on_year_changed(self):
        """Обробляє зміну року."""
        self.current_year = self.year_input.value()
        self._load_data()

    def _on_selection_changed(self):
        """Обробляє зміну виділення."""
        has_selection = len(self.table.selectedItems()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.create_doc_btn.setEnabled(has_selection)

    def _add_entry(self):
        """Відкриває діалог додавання запису."""
        dialog = ScheduleEntryDialog(self.current_year, parent=self)
        if dialog.exec():
            self._load_data()
            self.data_changed.emit()

    def _edit_entry(self):
        """Відкриває діалог редагування запису."""
        item = self.table.currentItem()
        if not item:
            return

        entry_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        dialog = ScheduleEntryDialog(self.current_year, entry_id, parent=self)
        if dialog.exec():
            self._load_data()
            self.data_changed.emit()

    def _delete_entry(self):
        """Видаляє запис."""
        from backend.models.schedule import AnnualSchedule
        from backend.core.database import get_db_context

        item = self.table.currentItem()
        if not item:
            return

        reply = QMessageBox.question(
            self,
            "Підтвердження",
            "Видалити запис з графіку?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            entry_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
            with get_db_context() as db:
                entry = db.query(AnnualSchedule).filter(AnnualSchedule.id == entry_id).first()
                if entry:
                    db.delete(entry)
                    db.commit()
                    self._load_data()
                    self.data_changed.emit()

    def _auto_distribute(self):
        """Автоматично розподіляє відпустки."""
        from backend.services.schedule_service import ScheduleService

        service = ScheduleService(self.db)
        result = service.auto_distribute(self.current_year)

        QMessageBox.information(
            self,
            "Авторозподіл",
            f"Створено записів: {result['entries_created']}\n"
            f"Попереджень: {len(result['warnings'])}",
        )

        self._load_data()
        self.data_changed.emit()

    def _create_document(self):
        """Створює заяву на основі запису графіку."""
        from backend.core.database import get_db_context
        from backend.models.schedule import AnnualSchedule

        item = self.table.currentItem()
        if not item:
            return

        entry_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

        # Get schedule entry data
        with get_db_context() as db:
            entry = db.query(AnnualSchedule).filter(AnnualSchedule.id == entry_id).first()
            if not entry:
                return

            staff_id = entry.staff_id
            planned_start = entry.planned_start
            planned_end = entry.planned_end

        # Перемикаємось на вкладку конструктора
        main_window = self.parent().parent()
        main_window.setCurrentIndex(2)  # Builder tab

        # Передаємо дані в конструктор
        builder_tab = main_window.builder_tab
        builder_tab.new_document(staff_id)
        builder_tab.set_vacation_dates(planned_start, planned_end)

    def refresh(self):
        """Оновлює дані вкладки."""
        self._load_data()


class ScheduleEntryDialog(QDialog):
    """Діалог для створення/редагування запису графіку."""

    def __init__(
        self,
        year: int,
        entry_id: int | None = None,
        parent=None,
    ):
        """Ініціалізує діалог."""
        super().__init__(parent)
        self.year = year
        self.entry_id = entry_id
        self._setup_ui()
        if entry_id:
            self._load_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("Запис графіку" if self.entry_id is None else "Редагування")
        self.setMinimumWidth(500)

        layout = QFormLayout(self)

        # Вибір співробітника
        self.staff_input = QComboBox()
        self._load_staff()
        layout.addRow("Співробітник:", self.staff_input)

        self.start_input = QDateEdit()
        self.start_input.setCalendarPopup(True)
        layout.addRow("Початок:", self.start_input)

        self.end_input = QDateEdit()
        self.end_input.setCalendarPopup(True)
        layout.addRow("Кінець:", self.end_input)

        # Кнопки
        from PyQt6.QtWidgets import QDialogButtonBox

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

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

            for staff in staff_list:
                self.staff_input.addItem(staff.pib_nom, staff.id)

    def _load_data(self):
        """Завантажує дані запису."""
        from backend.models.schedule import AnnualSchedule
        from backend.core.database import get_db_context

        with get_db_context() as db:
            entry = db.query(AnnualSchedule).filter(AnnualSchedule.id == self.entry_id).first()
            if entry:
                idx = self.staff_input.findData(entry.staff_id)
                if idx >= 0:
                    self.staff_input.setCurrentIndex(idx)
                self.start_input.setDate(entry.planned_start)
                self.end_input.setDate(entry.planned_end)

    def accept(self):
        """Зберігає дані."""
        from backend.models.schedule import AnnualSchedule
        from backend.core.database import get_db_context

        staff_id = self.staff_input.currentData()
        start = self.start_input.date().toPyDate()
        end = self.end_input.date().toPyDate()

        with get_db_context() as db:
            if self.entry_id is None:
                # Створення
                entry = AnnualSchedule(
                    year=self.year,
                    staff_id=staff_id,
                    planned_start=start,
                    planned_end=end,
                )
                db.add(entry)
            else:
                # Оновлення
                entry = db.query(AnnualSchedule).filter(AnnualSchedule.id == self.entry_id).first()
                if entry:
                    entry.staff_id = staff_id
                    entry.planned_start = start
                    entry.planned_end = end

            db.commit()
        super().accept()
