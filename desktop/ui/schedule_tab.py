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
    QCheckBox,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QRadioButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from datetime import date

from shared.enums import EmploymentType


class AutoDistributeSettings:
    """Налаштування для авторозподілу."""

    def __init__(self):
        # Days per period
        self.min_days_per_period = 7
        self.max_days_per_period = 14
        self.use_balance_days = True  # Use vacation_balance from staff
        self.custom_days = 24  # If not using balance

        # Number of periods
        self.max_periods = 2  # Max number of vacation periods per employee
        self.use_all_balance = True  # Split all balance into periods

        # Document creation
        self.create_documents = True
        self.doc_type = "vacation_main"

        # Month selection
        self.all_year = True
        self.summer_only = False  # June-September
        self.winter_only = False  # December-February
        self.custom_months = []  # List of months

        # Other options
        self.skip_existing = True
        self.random_distribution = True


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
        self.settings = AutoDistributeSettings()
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

        self.settings_btn = QPushButton("Налаштування...")
        self.settings_btn.clicked.connect(self._show_settings)
        control_layout.addWidget(self.settings_btn)

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

    def _show_settings(self):
        """Показує діалог налаштувань авторозподілу."""
        dialog = AutoDistributeSettingsDialog(self.settings, parent=self)
        if dialog.exec():
            # Settings already updated in dialog
            pass

    def _auto_distribute(self):
        """Автоматично розподіляє відпустки."""
        from backend.core.database import get_db_context
        from backend.services.schedule_service import ScheduleService

        with get_db_context() as db:
            service = ScheduleService(db)
            result = service.auto_distribute(
                self.current_year,
                settings=self.settings
            )

        # Показуємо результат
        msg = f"Створено записів графіку: {result['entries_created']}\n"
        msg += f"Створено документів: {result.get('documents_created', 0)}\n"
        msg += f"Попереджень: {len(result['warnings'])}"

        if result['warnings']:
            msg += "\n\nПопередження:\n"
            for w in result['warnings'][:10]:  # Показуємо перші 10
                msg += f"• {w}\n"
            if len(result['warnings']) > 10:
                msg += f"... та ще {len(result['warnings']) - 10}"

            QMessageBox.warning(self, "Авторозподіл", msg)
        else:
            QMessageBox.information(self, "Авторозподіл", msg)

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

        # Знаходимо головне вікно
        from desktop.ui.main_window import MainWindow
        main_window = self.window()
        if not isinstance(main_window, MainWindow):
            # Спробуємо інший спосіб
            main_window = self.parent().parent()
            if not isinstance(main_window, MainWindow):
                QMessageBox.warning(self, "Помилка", "Не вдалося знайти головне вікно")
                return

        # Перемикаємось на вкладку конструктора
        main_window.navigate_to_builder(staff_id)

        # Встановлюємо дати
        builder_tab = main_window.builder_tab
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


class AutoDistributeSettingsDialog(QDialog):
    """Діалог налаштувань авторозподілу відпусток."""

    def __init__(self, settings: AutoDistributeSettings, parent=None):
        """Ініціалізує діалог."""
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Налаштування авторозподілу")
        self.setMinimumWidth(450)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        layout = QVBoxLayout(self)

        # Період відпустки
        period_group = QGroupBox("Тривалість відпустки")
        period_layout = QGridLayout()

        period_layout.addWidget(QLabel("Мін. днів у періоді:"), 0, 0)
        self.min_days_spin = QSpinBox()
        self.min_days_spin.setRange(1, 30)
        self.min_days_spin.setValue(7)
        period_layout.addWidget(self.min_days_spin, 0, 1)

        period_layout.addWidget(QLabel("Макс. днів у періоді:"), 1, 0)
        self.max_days_spin = QSpinBox()
        self.max_days_spin.setRange(1, 30)
        self.max_days_spin.setValue(14)
        period_layout.addWidget(self.max_days_spin, 1, 1)

        self.use_balance_check = QCheckBox("Використовувати баланс відпустки працівника")
        self.use_balance_check.setChecked(True)
        period_layout.addWidget(self.use_balance_check, 2, 0, 1, 2)

        self.custom_days_spin = QSpinBox()
        self.custom_days_spin.setRange(1, 60)
        self.custom_days_spin.setValue(24)
        period_layout.addWidget(QLabel("Або фіксована кількість днів:"), 3, 0)
        period_layout.addWidget(self.custom_days_spin, 3, 1)

        period_group.setLayout(period_layout)
        layout.addWidget(period_group)

        # Кількість періодів
        periods_group = QGroupBox("Кількість періодів")
        periods_layout = QVBoxLayout()

        self.max_periods_spin = QSpinBox()
        self.max_periods_spin.setRange(1, 10)
        self.max_periods_spin.setValue(2)
        periods_layout.addWidget(QLabel("Максимум періодів на працівника:"))
        periods_layout.addWidget(self.max_periods_spin)

        self.use_all_balance_check = QCheckBox("Розбити всі дні на періоди")
        self.use_all_balance_check.setChecked(True)
        periods_layout.addWidget(self.use_all_balance_check)

        periods_group.setLayout(periods_layout)
        layout.addWidget(periods_group)

        # Створення документів
        docs_group = QGroupBox("Документи")
        docs_layout = QVBoxLayout()

        self.create_docs_check = QCheckBox("Створювати документи (чернетки)")
        self.create_docs_check.setChecked(True)
        docs_layout.addWidget(self.create_docs_check)

        self.doc_type_combo = QComboBox()
        doc_types = [
            ("vacation_main", "Основна відпустка (В)"),
            ("vacation_paid", "Відпустка оплачувана"),
            ("vacation_additional", "Додаткова відпустка (Д)"),
        ]
        for value, label in doc_types:
            self.doc_type_combo.addItem(label, value)
        docs_layout.addWidget(QLabel("Тип документа:"))
        docs_layout.addWidget(self.doc_type_combo)

        docs_group.setLayout(docs_layout)
        layout.addWidget(docs_group)

        # Місяці
        months_group = QGroupBox("Місяці")
        months_layout = QVBoxLayout()

        self.all_year_radio = QRadioButton("Весь рік")
        self.all_year_radio.setChecked(True)
        months_layout.addWidget(self.all_year_radio)

        self.summer_radio = QRadioButton("Літо (червень-вересень)")
        months_layout.addWidget(self.summer_radio)

        self.winter_radio = QRadioButton("Зима (грудень-лютий)")
        months_layout.addWidget(self.winter_radio)

        months_group.setLayout(months_layout)
        layout.addWidget(months_group)

        # Інші налаштування
        other_group = QGroupBox("Інші")
        other_layout = QVBoxLayout()

        self.skip_existing_check = QCheckBox("Пропускати працівників з існуючими записами")
        self.skip_existing_check.setChecked(True)
        other_layout.addWidget(self.skip_existing_check)

        self.random_check = QCheckBox("Випадковий розподіл дат")
        self.random_check.setChecked(True)
        other_layout.addWidget(self.random_check)

        other_group.setLayout(other_layout)
        layout.addWidget(other_group)

        # Кнопки
        from PyQt6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_settings(self):
        """Завантажує поточні налаштування."""
        self.min_days_spin.setValue(self.settings.min_days_per_period)
        self.max_days_spin.setValue(self.settings.max_days_per_period)
        self.use_balance_check.setChecked(self.settings.use_balance_days)
        self.custom_days_spin.setValue(self.settings.custom_days)
        self.max_periods_spin.setValue(self.settings.max_periods)
        self.use_all_balance_check.setChecked(self.settings.use_all_balance)
        self.create_docs_check.setChecked(self.settings.create_documents)

        idx = self.doc_type_combo.findData(self.settings.doc_type)
        if idx >= 0:
            self.doc_type_combo.setCurrentIndex(idx)

        if self.settings.all_year:
            self.all_year_radio.setChecked(True)
        elif self.settings.summer_only:
            self.summer_radio.setChecked(True)
        else:
            self.winter_radio.setChecked(True)

        self.skip_existing_check.setChecked(self.settings.skip_existing)
        self.random_check.setChecked(self.settings.random_distribution)

    def _save_settings(self):
        """Зберігає налаштування."""
        self.settings.min_days_per_period = self.min_days_spin.value()
        self.settings.max_days_per_period = self.max_days_spin.value()
        self.settings.use_balance_days = self.use_balance_check.isChecked()
        self.settings.custom_days = self.custom_days_spin.value()
        self.settings.max_periods = self.max_periods_spin.value()
        self.settings.use_all_balance = self.use_all_balance_check.isChecked()
        self.settings.create_documents = self.create_docs_check.isChecked()
        self.settings.doc_type = self.doc_type_combo.currentData()

        self.settings.all_year = self.all_year_radio.isChecked()
        self.settings.summer_only = self.summer_radio.isChecked()
        self.settings.winter_only = self.winter_radio.isChecked()

        self.settings.skip_existing = self.skip_existing_check.isChecked()
        self.settings.random_distribution = self.random_check.isChecked()

        self.accept()
