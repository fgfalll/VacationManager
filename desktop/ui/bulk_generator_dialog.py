"""Bulk Document Generator Dialog - Generate vacation documents for multiple employees."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QDoubleSpinBox, QProgressBar, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout, QListWidget, QListWidgetItem,
    QAbstractItemView, QRadioButton, QButtonGroup, QFrame, QScrollArea,
    QApplication, QCalendarWidget
)

from backend.core.database import get_db_context
from backend.models.staff import Staff
from backend.models.settings import Approvers
from backend.services.document_service import DocumentService
from backend.services.grammar_service import GrammarService
from shared.enums import DocumentType, DocumentStatus, EmploymentType


class BulkApproversDialog(QDialog):
    """Dialog for customizing approvers for bulk document generation."""

    def __init__(self, parent=None, default_signatories=None):
        """Initialize dialog."""
        super().__init__(parent)
        self.default_signatories = default_signatories or []
        self._signatories = []
        self._per_staff_overrides = {}  # staff_id -> list of signatories
        self._setup_ui()
        self._load_defaults()

    def _setup_ui(self):
        """Set up the UI."""
        self.setWindowTitle("Налаштування погоджувачів")
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)

        # Main approvers list
        group = QGroupBox("Погоджувачі для документів")
        form = QFormLayout(group)

        self.approvers_list = QListWidget()
        self.approvers_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        form.addRow("Список погоджувачів:", self.approvers_list)

        # Add/Remove buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Додати")
        self.add_btn.clicked.connect(self._add_approver)
        self.remove_btn = QPushButton("- Видалити")
        self.remove_btn.clicked.connect(self._remove_approver)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        form.addRow(btn_layout)

        layout.addWidget(group)

        # Options
        options_group = QGroupBox("Опції")
        options_layout = QVBoxLayout(options_group)

        self.apply_all_check = QCheckBox("Застосувати однаковий список до всіх")
        self.apply_all_check.setChecked(True)
        self.apply_all_check.stateChanged.connect(self._on_apply_all_changed)
        options_layout.addWidget(self.apply_all_check)

        self.per_staff_check = QCheckBox("Дозволити перевизначення для окремих співробітників")
        options_layout.addWidget(self.per_staff_check)

        layout.addWidget(options_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_defaults(self):
        """Load default signatories."""
        self._signatories = []
        for s in self.default_signatories:
            self._signatories.append({
                'position': s.get('position', ''),
                'position_multiline': s.get('position_multiline', ''),
                'name': s.get('name', '')
            })
        self._update_list()

    def _update_list(self):
        """Update the list widget."""
        self.approvers_list.clear()
        for s in self._signatories:
            text = f"{s['position']} - {s['name']}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.approvers_list.addItem(item)

    def _add_approver(self):
        """Add a new approver."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Додати погоджувача")
        layout = QFormLayout(dialog)

        pos_edit = QLineEdit()
        pos_multiline = QLineEdit()
        name_edit = QLineEdit()

        layout.addRow("Посада:", pos_edit)
        layout.addRow("Посада (багаторядковий):", pos_multiline)
        layout.addRow("ПІБ:", name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if pos_edit.text() and name_edit.text():
                self._signatories.append({
                    'position': pos_edit.text(),
                    'position_multiline': pos_multiline.text() or pos_edit.text(),
                    'name': name_edit.text()
                })
                self._update_list()

    def _remove_approver(self):
        """Remove selected approver."""
        row = self.approvers_list.currentRow()
        if row >= 0:
            self._signatories.pop(row)
            self._update_list()

    def _on_apply_all_changed(self):
        """Handle apply all checkbox change."""
        self.per_staff_check.setEnabled(not self.apply_all_check.isChecked())

    def _save(self):
        """Save and close."""
        # Update from list
        self._signatories = []
        for i in range(self.approvers_list.count()):
            item = self.approvers_list.item(i)
            self._signatories.append(item.data(Qt.ItemDataRole.UserRole))
        self.accept()

    def get_signatories(self) -> list[dict]:
        """Get the configured signatories."""
        return self._signatories

    def get_apply_all(self) -> bool:
        """Check if apply to all is enabled."""
        return self.apply_all_check.isChecked()

    def get_per_staff_override(self) -> bool:
        """Check if per-staff override is enabled."""
        return self.per_staff_check.isChecked() and not self.apply_all_check.isChecked()


class _SimpleDateRangeDialog(QDialog):
    """Date range selection dialog - single click for date, shift+click for range."""

    def __init__(self, parent=None, staff_name: str = "", locked_dates: set = None, existing_ranges: list = None):
        super().__init__(parent)
        self._locked_dates = locked_dates or set()
        self._selected_ranges = existing_ranges or []  # All selected ranges
        self._range_start = None  # Start date for range selection with shift
        self._setup_ui(staff_name)

    def _setup_ui(self, staff_name: str):
        """Set up the UI."""
        self.setWindowTitle(f"Вибір дат - {staff_name}")
        self.setMinimumSize(480, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel("Клацніть на дату для вибору\nShift+клацніть для вибору діапазону")
        instructions.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        layout.addWidget(instructions)

        # Calendar widget
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.clicked.connect(self._on_date_clicked)
        layout.addWidget(self.calendar)

        # Selected ranges list
        self.ranges_list = QListWidget()
        self.ranges_list.setStyleSheet("background-color: #EFF6FF; border: 1px solid #BFDBFE;")
        layout.addWidget(self.ranges_list)

        # Info label
        self.info_label = QLabel("Обрано: 0 днів")
        self.info_label.setStyleSheet("background-color: #DBEAFE; padding: 8px; border-radius: 4px; font-weight: bold;")
        layout.addWidget(self.info_label)

        # Buttons
        buttons_layout = QHBoxLayout()

        self.clear_btn = QPushButton("Очистити все")
        self.clear_btn.clicked.connect(self._clear_all)
        buttons_layout.addWidget(self.clear_btn)

        buttons_layout.addStretch()

        self.remove_selected_btn = QPushButton("Видалити обране")
        self.remove_selected_btn.clicked.connect(self._remove_selected)
        self.remove_selected_btn.setEnabled(False)
        buttons_layout.addWidget(self.remove_selected_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        buttons_layout.addWidget(buttons)

        layout.addLayout(buttons_layout)

        # Connect list selection
        self.ranges_list.itemSelectionChanged.connect(self._on_list_selection_changed)

        self._format_calendar()
        self._update_ranges_list()

    def _format_calendar(self):
        """Format calendar with locked dates and selections highlighted."""
        from PyQt6.QtGui import QTextCharFormat, QColor

        locked_format = QTextCharFormat()
        locked_format.setBackground(QColor(254, 202, 202))  # Red-200 for locked

        selected_format = QTextCharFormat()
        selected_format.setBackground(QColor(147, 197, 253))  # Blue-300 for selected

        range_start_format = QTextCharFormat()
        range_start_format.setBackground(QColor(59, 130, 246))  # Blue-600 for start

        today = date.today()
        today_format = QTextCharFormat()
        today_format.setBackground(QColor(34, 197, 94))  # Green for today

        # Reset all dates in visible month
        for day in range(1, 32):
            try:
                d = date(self.calendar.yearShown(), self.calendar.monthShown(), day)
                if d in self._locked_dates:
                    self.calendar.setDateTextFormat(d, locked_format)
                elif d == today:
                    self.calendar.setDateTextFormat(d, today_format)
                else:
                    self.calendar.setDateTextFormat(d, QTextCharFormat())
            except ValueError:
                continue

        # Highlight selected ranges (blue)
        for start, end in self._selected_ranges:
            current = start
            while current <= end:
                if current.month == self.calendar.monthShown() and current.year == self.calendar.yearShown():
                    if current == start:
                        self.calendar.setDateTextFormat(current, range_start_format)
                    else:
                        self.calendar.setDateTextFormat(current, selected_format)
                current += timedelta(days=1)

        # Highlight range start marker
        if self._range_start:
            if self._range_start.month == self.calendar.monthShown() and self._range_start.year == self.calendar.yearShown():
                self.calendar.setDateTextFormat(self._range_start, range_start_format)

    def _on_date_clicked(self, qdate):
        """Handle date click - single for date, shift for range."""
        py_date = qdate.toPyDate()

        # Check if locked - still allow selection but warn
        if py_date in self._locked_dates:
            reply = QMessageBox.question(
                self,
                "Підтвердження",
                "Ця дата вже заброньована. Все одно обрати?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Get keyboard modifiers
        modifiers = QApplication.keyboardModifiers()

        if modifiers == Qt.KeyboardModifier.ShiftModifier:
            # Range selection
            if self._range_start is None:
                self._range_start = py_date
            else:
                # Create range from start to current
                if py_date < self._range_start:
                    start, end = py_date, self._range_start
                else:
                    start, end = self._range_start, py_date
                self._selected_ranges.append((start, end))
                self._range_start = None
        else:
            # Single date - treat as single-day range
            self._selected_ranges.append((py_date, py_date))
            self._range_start = None

        self._format_calendar()
        self._update_ranges_list()

    def _update_ranges_list(self):
        """Update the list of selected ranges."""
        self.ranges_list.clear()

        # Calculate total days
        total_days = 0

        for i, (start, end) in enumerate(self._selected_ranges):
            days = (end - start).days + 1
            total_days += days

            if start == end:
                text = f"{start.strftime('%d.%m.%Y')} ({days} день)"
            else:
                text = f"{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')} ({days} дн.)"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setBackground(QColor(219, 234, 254))  # Blue-100
            self.ranges_list.addItem(item)

        # Update info label
        self.info_label.setText(f"Обрано: {total_days} днів у {len(self._selected_ranges)} періоді(ах)")

    def _on_list_selection_changed(self):
        """Enable/disable remove button based on selection."""
        self.remove_selected_btn.setEnabled(len(self.ranges_list.selectedItems()) > 0)

    def _remove_selected(self):
        """Remove selected range from list."""
        # Get selected indices (in reverse order to maintain correctness)
        selected_indices = sorted([item.data(Qt.ItemDataRole.UserRole) for item in self.ranges_list.selectedItems()], reverse=True)

        for idx in selected_indices:
            if 0 <= idx < len(self._selected_ranges):
                self._selected_ranges.pop(idx)

        self._format_calendar()
        self._update_ranges_list()

    def _clear_all(self):
        """Clear all selections."""
        self._selected_ranges = []
        self._range_start = None
        self._format_calendar()
        self._update_ranges_list()

    def _on_accept(self):
        """Accept and return ranges."""
        if not self._selected_ranges:
            QMessageBox.warning(self, "Попередження", "Оберіть хоча б одну дату!")
            return

        self._result_ranges = self._selected_ranges
        self.accept()

    def get_selected_ranges(self) -> list[tuple]:
        """Return all selected date ranges."""
        return getattr(self, '_result_ranges', [])


class BulkGeneratorDialog(QDialog):
    """
    Діалог для масової генерації документів відпусток.

    Дозволяє:
    - Фільтрувати співробітників за типом працевлаштування та ставкою
    - Вибирати співробітників з таблиці
    - Вибирати дати (вручну або автоматично)
    - Налаштовувати погоджувачів
    - Генерувати документи для всіх обраних
    """

    document_created = pyqtSignal()  # Emitted when documents are generated

    def __init__(self, parent=None):
        """Initialize bulk generator dialog."""
        super().__init__(parent)
        self._staff_data = []  # List of dicts with staff info
        self._selected_staff = []  # List of selected staff dicts
        self._date_ranges = []  # List of (start, end) tuples
        self._signatories = []  # List of approver dicts
        self._apply_signatories_all = True
        self._setup_ui()
        self._load_staff()

    def _setup_ui(self):
        """Set up the UI."""
        self.setWindowTitle("Масова генерація документів")
        self.setMinimumSize(1100, 750)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Top section - Filters + Staff Selection
        top_layout = QHBoxLayout()

        # Filter Section (compact)
        filter_group = QGroupBox("Фільтри")
        filter_layout = QVBoxLayout()
        filter_layout.setContentsMargins(5, 5, 5, 5)
        filter_layout.setSpacing(5)

        # Employment type checkboxes - all checked by default
        emp_layout = QHBoxLayout()
        emp_layout.setSpacing(8)
        emp_layout.addWidget(QLabel("Тип:"))
        self.main_check = QCheckBox("Основне")
        self.main_check.setChecked(True)
        self.external_check = QCheckBox("Зовніш.")
        self.external_check.setChecked(True)
        self.internal_check = QCheckBox("Внутр.")
        self.internal_check.setChecked(True)
        emp_layout.addWidget(self.main_check)
        emp_layout.addWidget(self.external_check)
        emp_layout.addWidget(self.internal_check)
        emp_layout.addStretch()
        filter_layout.addLayout(emp_layout)

        # Rate filter
        rate_layout = QHBoxLayout()
        rate_layout.setSpacing(8)
        rate_layout.addWidget(QLabel("Ставка:"))
        rate_btn_group = QButtonGroup()
        self.rate_all_radio = QRadioButton("Всі")
        self.rate_full_radio = QRadioButton("Повна")
        self.rate_partial_radio = QRadioButton("Частк.")
        self.rate_all_radio.setChecked(True)
        rate_btn_group.addButton(self.rate_all_radio)
        rate_btn_group.addButton(self.rate_full_radio)
        rate_btn_group.addButton(self.rate_partial_radio)
        rate_layout.addWidget(self.rate_all_radio)
        rate_layout.addWidget(self.rate_full_radio)
        rate_layout.addWidget(self.rate_partial_radio)
        rate_layout.addStretch()
        filter_layout.addLayout(rate_layout)

        filter_group.setLayout(filter_layout)
        top_layout.addWidget(filter_group)
        top_layout.setStretchFactor(filter_group, 1)

        # Staff Selection Table
        staff_group = QGroupBox("Вибір співробітників")
        staff_layout = QVBoxLayout()

        self.staff_table = QTableWidget()
        self.staff_table.setColumnCount(9)
        self.staff_table.setHorizontalHeaderLabels([
            "", "ПІБ", "Посада", "Ставка", "Баланс", "Тип", "Закінчення контракту", "", "Обрані дати"
        ])
        self.staff_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.staff_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.staff_table.setAlternatingRowColors(True)
        staff_layout.addWidget(self.staff_table)

        # Selection info and select all
        select_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Обрати всіх")
        self.select_all_btn.setStyleSheet("padding: 5px;")
        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn = QPushButton("Зняти всі")
        self.deselect_all_btn.setStyleSheet("padding: 5px;")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        select_layout.addWidget(self.select_all_btn)
        select_layout.addWidget(self.deselect_all_btn)
        select_layout.addStretch()
        self.selection_info = QLabel("Обрано: 0")
        select_layout.addWidget(self.selection_info)
        staff_layout.addLayout(select_layout)

        staff_group.setLayout(staff_layout)
        top_layout.addWidget(staff_group)
        top_layout.setStretchFactor(staff_group, 4)  # Give more space to staff table

        layout.addLayout(top_layout)

        # Approvers Section
        approvers_group = QGroupBox("Погоджувачі")
        approvers_layout = QVBoxLayout()

        self.approvers_btn = QPushButton("Налаштувати погоджувачів...")
        self.approvers_btn.setStyleSheet("padding: 8px;")
        self.approvers_btn.clicked.connect(self._configure_approvers)
        approvers_layout.addWidget(self.approvers_btn)

        self.approvers_info = QLabel("Буде використано системні налаштування")
        self.approvers_info.setStyleSheet("color: #666;")
        approvers_layout.addWidget(self.approvers_info)

        # File suffix option
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("Суфікс імені файлу:"))
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("напр., сумісники")
        suffix_layout.addWidget(self.suffix_edit)
        approvers_layout.addLayout(suffix_layout)

        approvers_group.setLayout(approvers_layout)
        layout.addWidget(approvers_group)

        # Date Selection Section
        date_group = QGroupBox("Вибір дат")
        date_layout = QVBoxLayout()

        # Automatic mode button
        self.auto_date_btn = QPushButton("Автоматичний підбір дат...")
        self.auto_date_btn.setStyleSheet("padding: 8px;")
        self.auto_date_btn.clicked.connect(self._open_auto_date_dialog)
        date_layout.addWidget(self.auto_date_btn)

        # Hint
        hint_label = QLabel("Або натисніть на кнопку 📅 в таблиці для вибору дат вручну для кожного співробітника")
        hint_label.setStyleSheet("color: #666; font-size: 11px;")
        date_layout.addWidget(hint_label)

        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        # Bottom - Progress and Generate
        bottom_layout = QHBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar)

        # Summary
        self.summary_label = QLabel("")
        bottom_layout.addWidget(self.summary_label)

        bottom_layout.addStretch()

        # Generate button
        self.generate_btn = QPushButton("🚀 Згенерувати документи")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #9CA3AF;
            }
        """)
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self._generate_documents)
        bottom_layout.addWidget(self.generate_btn)

        layout.addLayout(bottom_layout)

        # Connect checkbox signals
        self.main_check.stateChanged.connect(self._on_selection_changed)
        self.external_check.stateChanged.connect(self._on_selection_changed)
        self.internal_check.stateChanged.connect(self._on_selection_changed)
        self.rate_all_radio.toggled.connect(self._on_selection_changed)
        self.rate_full_radio.toggled.connect(self._on_selection_changed)
        self.rate_partial_radio.toggled.connect(self._on_selection_changed)

    def _load_staff(self):
        """Load all active staff from database."""
        with get_db_context() as db:
            staff_list = (
                db.query(Staff)
                .filter(Staff.is_active == True)
                .order_by(Staff.pib_nom)
                .all()
            )

            self._staff_data = []
            for staff in staff_list:
                # Calculate locked dates
                locked_dates = set()
                for doc in staff.documents:
                    if doc.status in ('on_signature', 'signed', 'processed'):
                        current = doc.date_start
                        while current <= doc.date_end:
                            locked_dates.add(current)
                            current += timedelta(days=1)

                self._staff_data.append({
                    'id': staff.id,
                    'pib_nom': staff.pib_nom,
                    'position': staff.position,
                    'rate': float(staff.rate),
                    'balance': staff.vacation_balance or 0,
                    'employment_type': staff.employment_type.value,
                    'term_end': staff.term_end,
                    'locked_dates': locked_dates,
                    'staff_obj': staff
                })

        self._apply_filters()

    def _apply_filters(self):
        """Apply filters and update table."""
        # Get filter values
        main = self.main_check.isChecked()
        external = self.external_check.isChecked()
        internal = self.internal_check.isChecked()

        rate_all = self.rate_all_radio.isChecked()
        rate_full = self.rate_full_radio.isChecked()

        # Filter staff
        filtered = []
        for staff in self._staff_data:
            # Employment type filter
            emp_ok = False
            if staff['employment_type'] == 'main' and main:
                emp_ok = True
            elif staff['employment_type'] == 'external' and external:
                emp_ok = True
            elif staff['employment_type'] == 'internal' and internal:
                emp_ok = True

            if not emp_ok:
                continue

            # Rate filter
            if rate_all:
                pass  # Accept all
            elif rate_full:
                if staff['rate'] < 1.0:
                    continue
            else:  # Partial
                if staff['rate'] >= 1.0:
                    continue

            filtered.append(staff)

        # Update table
        self.staff_table.setRowCount(len(filtered))
        for row, staff in enumerate(filtered):
            # Make all items non-editable by default
            flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

            # Checkbox (column 0) - already has its own flags
            checkbox = QTableWidgetItem()
            checkbox.setCheckState(Qt.CheckState.Unchecked)
            checkbox.setData(Qt.ItemDataRole.UserRole, staff)
            # Checkbox needs to be enabled for interaction
            checkbox.setFlags(flags | Qt.ItemFlag.ItemIsUserCheckable)
            self.staff_table.setItem(row, 0, checkbox)

            # Data columns - read-only
            self._set_cell_readonly(row, 1, staff['pib_nom'])
            self._set_cell_readonly(row, 2, staff['position'])
            self._set_cell_readonly(row, 3, f"{staff['rate']:.2f}")
            self._set_cell_readonly(row, 4, str(staff['balance']))

            emp_type_map = {
                'main': 'Основне',
                'external': 'Зовнішній',
                'internal': 'Внутрішній'
            }
            self._set_cell_readonly(row, 5, emp_type_map.get(staff['employment_type'], ''))
            self._set_cell_readonly(row, 6, staff['term_end'].strftime('%d.%m.%Y'))

            # Date picker button (column 7)
            date_btn = QPushButton("📅")
            date_btn.setFixedWidth(40)
            date_btn.setToolTip("Вибрати дати")
            date_btn.clicked.connect(lambda checked, r=row: self._on_date_picker_clicked(r))
            self.staff_table.setCellWidget(row, 7, date_btn)

            # Date display column (column 8) - read-only
            date_text = staff.get('_selected_dates', '')
            self._set_cell_readonly(row, 8, date_text)

            # Locked dates indicator
            if staff['locked_dates']:
                for col in range(1, 8):
                    item = self.staff_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 255, 224))

        # Resize columns
        self.staff_table.resizeColumnsToContents()
        self.staff_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.staff_table.setColumnWidth(0, 30)
        self.staff_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.staff_table.setColumnWidth(7, 45)

        self._on_selection_changed()

    def _set_cell_readonly(self, row: int, col: int, text: str):
        """Set a table cell as read-only with given text."""
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        self.staff_table.setItem(row, col, item)

    def _select_all(self):
        """Select all visible staff."""
        for row in range(self.staff_table.rowCount()):
            item = self.staff_table.item(row, 0)
            item.setCheckState(Qt.CheckState.Checked)
        self._on_selection_changed()

    def _deselect_all(self):
        """Deselect all staff."""
        for row in range(self.staff_table.rowCount()):
            item = self.staff_table.item(row, 0)
            item.setCheckState(Qt.CheckState.Unchecked)
        self._on_selection_changed()

    def _on_selection_changed(self):
        """Handle selection change."""
        selected = []
        for row in range(self.staff_table.rowCount()):
            item = self.staff_table.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))

        self._selected_staff = selected
        count = len(selected)
        self.selection_info.setText(f"Обрано: {count}")

        # Update summary
        total_balance = sum(s['balance'] for s in selected)
        self.summary_label.setText(f"Обрано: {count} співробітників | Загальний баланс: {total_balance} днів")

        # Enable/disable generate button
        self.generate_btn.setEnabled(count > 0)

    def _on_date_picker_clicked(self, row: int):
        """Open date picker dialog for manual date selection."""
        # Get staff data for this row
        item = self.staff_table.item(row, 0)
        if not item:
            return

        staff = item.data(Qt.ItemDataRole.UserRole)
        if not staff:
            return

        # Get existing ranges if any
        existing_ranges = staff.get('_date_ranges', [])

        # Create date range dialog with existing ranges
        dialog = _SimpleDateRangeDialog(
            self,
            staff['pib_nom'],
            staff['locked_dates'],
            existing_ranges
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            ranges = dialog.get_selected_ranges()
            self._on_popup_selection_complete(row, ranges)

    def _on_popup_selection_complete(self, row: int, ranges: list[tuple]):
        """Handle date selection from popup."""
        # Get staff data for this row
        item = self.staff_table.item(row, 0)
        if not item:
            return

        staff = item.data(Qt.ItemDataRole.UserRole)

        # Format dates for display
        if ranges:
            date_str_parts = []
            for start, end in ranges:
                if start == end:
                    date_str_parts.append(start.strftime('%d.%m'))
                else:
                    date_str_parts.append(f"{start.strftime('%d.%m')}-{end.strftime('%d.%m')}")
            date_text = ", ".join(date_str_parts)

            # Store in staff data
            staff['_selected_dates'] = date_text
            staff['_date_ranges'] = ranges

            # Update display column
            self._set_cell_readonly(row, 8, date_text)
        else:
            staff['_selected_dates'] = ''
            staff['_date_ranges'] = []
            self._set_cell_readonly(row, 8, '')

    def _open_auto_date_dialog(self):
        """Open automatic date selection dialog for all selected staff."""
        if not self._selected_staff:
            QMessageBox.warning(self, "Попередження", "Спочатку оберіть співробітників!")
            return

        # Get first selected staff for demo - in bulk mode we need a different approach
        # For bulk mode, we'll use a simplified dialog that sets the same dates for all
        staff = self._selected_staff[0]

        # Import AutoDateRangeDialog
        from desktop.ui.builder_tab import AutoDateRangeDialog

        dialog = AutoDateRangeDialog(staff['id'], self)
        dialog.selection_complete.connect(self._on_auto_date_complete)
        dialog.exec()

    def _on_auto_date_complete(self, ranges: list[tuple]):
        """Apply auto-selected dates to all selected staff."""
        if not ranges:
            return

        # Apply the same dates to all selected staff
        for row in range(self.staff_table.rowCount()):
            checkbox = self.staff_table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.CheckState.Checked:
                staff = checkbox.data(Qt.ItemDataRole.UserRole)
                if staff:
                    # Format dates for display
                    date_str_parts = []
                    for start, end in ranges:
                        if start == end:
                            date_str_parts.append(start.strftime('%d.%m'))
                        else:
                            date_str_parts.append(f"{start.strftime('%d.%m')}-{end.strftime('%d.%m')}")
                    date_text = ", ".join(date_str_parts)

                    # Store in staff data
                    staff['_selected_dates'] = date_text
                    staff['_date_ranges'] = ranges

                    # Update display column
                    self._set_cell_readonly(row, 8, date_text)

    def _configure_approvers(self):
        """Configure approvers for bulk generation."""
        default_signatories = self._get_default_signatories()

        dialog = BulkApproversDialog(self, default_signatories)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._signatories = dialog.get_signatories()
            self._apply_signatories_all = dialog.get_apply_all()

            if self._signatories:
                count = len(self._signatories)
                self.approvers_info.setText(f"Налаштовано: {count} погоджувачів")
            else:
                self.approvers_info.setText("Буде використано системні налаштування")

    def _get_default_signatories(self) -> list[dict]:
        """Get default signatories from settings."""
        signatories = []
        with get_db_context() as db:
            approvers = db.query(Approvers).order_by(Approvers.order_index).all()

            for a in approvers:
                signatories.append({
                    'position': a.position_name,
                    'position_multiline': a.position_name.replace('завідувача ', 'завідувача\n'),
                    'name': a.full_name_nom
                })

        return signatories

    def _generate_documents(self):
        """Generate documents for selected staff."""
        if not self._selected_staff:
            return

        # Check all selected staff have dates
        for staff_info in self._selected_staff:
            if not staff_info.get('_date_ranges'):
                QMessageBox.warning(self, "Попередження", f"Спочатку оберіть дати для {staff_info['pib_nom']}!")
                return

        # Get document type
        doc_type, ok = self._select_document_type()
        if not ok:
            return

        # Confirm generation
        count = len(self._selected_staff)
        result = QMessageBox.question(
            self,
            "Підтвердження",
            f"Згенерувати {count} документ(ів)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.generate_btn.setEnabled(False)

        generated = []
        errors = []

        try:
            from backend.services.document_service import DocumentService
            from backend.services.grammar_service import GrammarService
            from backend.models.document import Document

            grammar = GrammarService()
            file_suffix = self.suffix_edit.text().strip()

            for i, staff_info in enumerate(self._selected_staff):
                self.progress_bar.setValue(int((i / count) * 100))
                QApplication.processEvents()

                try:
                    staff = staff_info['staff_obj']

                    # Get dates from staff data (set by date picker or auto dialog)
                    date_ranges = staff_info.get('_date_ranges', [])
                    if not date_ranges:
                        errors.append(f"{staff_info['pib_nom']}: не обрано дати")
                        continue

                    # Use first date range
                    date_start, date_end = date_ranges[0]
                    days_count = (date_end - date_start).days + 1

                    # Create document
                    with get_db_context() as db:
                        doc = Document(
                            staff_id=staff.id,
                            doc_type=doc_type,
                            date_start=date_start,
                            date_end=date_end,
                            days_count=days_count,
                            payment_period=self._get_payment_period(date_start, date_end),
                            editor_content='',
                            status=DocumentStatus.DRAFT,
                            created_by='bulk'
                        )

                        db.add(doc)
                        db.commit()
                        db.refresh(doc)

                        # Generate PDF
                        doc_service = DocumentService(db, grammar)
                        output_path = doc_service.generate_document(doc)

                        generated.append({
                            'staff': staff_info['pib_nom'],
                            'doc_id': doc.id,
                            'path': str(output_path)
                        })

                except Exception as e:
                    errors.append(f"{staff_info['pib_nom']}: {str(e)}")

            self.progress_bar.setValue(100)

        finally:
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)

        # Show results
        self._show_generation_results(generated, errors)

    def _select_document_type(self) -> tuple[str, bool]:
        """Select document type."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Тип документа")
        layout = QVBoxLayout(dialog)

        label = QLabel("Оберіть тип документів для генерації:")
        layout.addWidget(label)

        combo = QComboBox()
        combo.addItem("Оплачувана відпустка", "vacation_paid")
        combo.addItem("Відпустка без збереження", "vacation_unpaid")
        layout.addWidget(combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return combo.currentData(), True
        return "", False

    def _find_available_dates(self, staff_info: dict, doc_type: str, start_from: date = None, days_needed: int = 14) -> tuple | None:
        """Find available dates for a staff member."""
        if start_from is None:
            start_from = date.today()

        contract_end = staff_info['term_end']
        locked = staff_info['locked_dates']

        # Look ahead up to 3 months or contract end
        max_date = min(start_from + timedelta(days=90), contract_end - timedelta(days=days_needed))

        current = start_from
        while current <= max_date:
            # Check if days_needed days are available from this date
            all_available = True
            for offset in range(days_needed):
                check_date = current + timedelta(days=offset)
                if check_date > contract_end:
                    all_available = False
                    break
                if check_date.weekday() >= 5:  # Weekend
                    continue
                if check_date in locked:
                    all_available = False
                    break

            if all_available:
                return (current, current + timedelta(days=days_needed - 1))

            current += timedelta(days=1)

        return None

    def _get_payment_period(self, date_start: date, date_end: date) -> str:
        """Determine payment period."""
        if date_start.day <= 15:
            return "перша половина"
        else:
            return "друга половина"

    def _show_generation_results(self, generated: list, errors: list):
        """Show generation results."""
        msg = QDialog(self)
        msg.setWindowTitle("Результат генерації")
        layout = QVBoxLayout(msg)

        if generated:
            layout.addWidget(QLabel(f"Успішно згенеровано: {len(generated)} документів"))

        if errors:
            error_text = "\n".join(errors[:10])
            if len(errors) > 10:
                error_text += f"\n... та ще {len(errors) - 10} помилок"
            error_label = QLabel(f"Помилки:\n{error_text}")
            error_label.setStyleSheet("color: #DC2626;")
            layout.addWidget(error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(msg.accept)
        layout.addWidget(buttons)

        if generated:
            self.document_created.emit()

        msg.exec()
