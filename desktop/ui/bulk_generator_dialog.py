"""Bulk Document Generator Dialog - Generate vacation documents for multiple employees."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import joinedload

from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QDoubleSpinBox, QProgressBar, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout, QListWidget, QListWidgetItem,
    QAbstractItemView, QRadioButton, QButtonGroup, QFrame, QScrollArea,
    QApplication, QCalendarWidget, QDateEdit, QTextEdit
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
        pos_edit.setPlaceholderText("напр., завідувача кафедри журналістики")
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("ПІБ")

        layout.addRow("Посада:", pos_edit)
        layout.addRow("ПІБ:", name_edit)

        info_label = QLabel("Рядок буде автоматично розбито, якщо текст занадто довгий")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addRow(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if pos_edit.text() and name_edit.text():
                # Format name as "Василь САВИК" (first name + surname uppercase)
                full_name = name_edit.text()
                name_parts = full_name.split()
                if len(name_parts) >= 3:
                    formatted_name = f"{name_parts[1]} {name_parts[0].upper()}"
                elif len(name_parts) == 2:
                    formatted_name = f"{name_parts[0]} {name_parts[1].upper()}"
                else:
                    formatted_name = full_name

                self._signatories.append({
                    'position': pos_edit.text(),
                    'position_multiline': '',  # Will be calculated automatically when rendering
                    'name': formatted_name
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
        self._approvers = []  # Alias for signatories (used in generation)
        self._apply_signatories_all = True
        self._setup_ui()
        self._load_staff()
        # Initialize approvers from default signatories
        self._approvers = self._get_default_signatories()

    def _setup_ui(self):
        """Set up the UI."""
        self.setWindowTitle("Масова генерація документів")
        self.setMinimumSize(1100, 750)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Filters in a single horizontal line
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(15)

        # Employment type checkboxes - all checked by default
        filter_layout.addWidget(QLabel("<b>Тип працевлаштування:</b>"))
        self.main_check = QCheckBox("Основне")
        self.main_check.setChecked(True)
        self.external_check = QCheckBox("Зовнішнє")
        self.external_check.setChecked(True)
        self.internal_check = QCheckBox("Внутрішнє")
        self.internal_check.setChecked(True)
        filter_layout.addWidget(self.main_check)
        filter_layout.addWidget(self.external_check)
        filter_layout.addWidget(self.internal_check)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        filter_layout.addWidget(separator)

        # Rate filter
        filter_layout.addWidget(QLabel("<b>Ставка:</b>"))
        rate_btn_group = QButtonGroup()
        self.rate_all_radio = QRadioButton("Всі")
        self.rate_all_radio.setChecked(True)
        self.rate_full_radio = QRadioButton("Повна")
        self.rate_partial_radio = QRadioButton("Часткова")
        rate_btn_group.addButton(self.rate_all_radio)
        rate_btn_group.addButton(self.rate_full_radio)
        rate_btn_group.addButton(self.rate_partial_radio)
        filter_layout.addWidget(self.rate_all_radio)
        filter_layout.addWidget(self.rate_full_radio)
        filter_layout.addWidget(self.rate_partial_radio)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Staff Selection Table
        staff_group = QGroupBox("Вибір співробітників")
        staff_layout = QVBoxLayout()

        self.staff_table = QTableWidget()
        self.staff_table.setColumnCount(10)
        self.staff_table.setHorizontalHeaderLabels([
            "", "ПІБ", "Посада", "Ставка", "Баланс", "Тип", "Закінчення контракту", "", "Обрані дати", "Погоджувачі"
        ])
        self.staff_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.staff_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.staff_table.setAlternatingRowColors(True)
        self.staff_table.itemChanged.connect(self._on_table_item_changed)
        self.staff_table.cellDoubleClicked.connect(self._on_table_item_double_clicked)
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
        layout.addWidget(staff_group)

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

        # Per-staff approvers button
        self.staff_approvers_btn = QPushButton("Налаштувати для окремого співробітника...")
        self.staff_approvers_btn.setStyleSheet("padding: 8px;")
        self.staff_approvers_btn.clicked.connect(self._configure_staff_approvers)
        approvers_layout.addWidget(self.staff_approvers_btn)

        staff_approvers_hint = QLabel("(Оберіть співробітника у таблиці спочатку)")
        staff_approvers_hint.setStyleSheet("color: #888; font-size: 10px;")
        approvers_layout.addWidget(staff_approvers_hint)

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
                .options(joinedload(Staff.documents))
                .filter(Staff.is_active == True)
                .order_by(Staff.pib_nom)
                .all()
            )

            self._staff_data = []
            for staff in staff_list:
                # Calculate locked dates
                locked_dates = set()
                locked_docs_count = 0
                for doc in staff.documents:
                    if doc.status in ('on_signature', 'signed', 'processed'):
                        locked_docs_count += 1
                        current = doc.date_start
                        while current <= doc.date_end:
                            locked_dates.add(current)
                            current += timedelta(days=1)

                # Debug output
                if locked_dates:
                    print(f"[DEBUG] {staff.pib_nom}: {len(locked_dates)} locked dates from {locked_docs_count} docs, e.g. {sorted(list(locked_dates))[:3]}")

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

    def _apply_filters(self, preserve_selection: bool = True):
        """Apply filters and update table."""
        # Get filter values
        main = self.main_check.isChecked()
        external = self.external_check.isChecked()
        internal = self.internal_check.isChecked()

        rate_all = self.rate_all_radio.isChecked()
        rate_full = self.rate_full_radio.isChecked()

        # Save currently selected staff data to preserve custom approvers
        selected_ids = set()
        selected_approvers = {}  # staff_id -> custom approvers
        if preserve_selection:
            for staff in self._selected_staff:
                selected_ids.add(staff['id'])
                if '_approvers' in staff:
                    selected_approvers[staff['id']] = staff['_approvers']

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

        # Restore custom approvers for selected staff
        if preserve_selection:
            for staff in filtered:
                if staff['id'] in selected_approvers:
                    staff['_approvers'] = selected_approvers[staff['id']]

        # Update table
        self.staff_table.setRowCount(len(filtered))
        for row, staff in enumerate(filtered):
            # Make all items non-editable by default
            flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

            # Checkbox (column 0) - already has its own flags
            checkbox = QTableWidgetItem()
            # Restore checked state if this staff was selected
            if preserve_selection and staff['id'] in selected_ids:
                checkbox.setCheckState(Qt.CheckState.Checked)
            else:
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
            print(f"[DEBUG TABLE] Row {row}, {staff['pib_nom']}: _selected_dates = '{date_text}', id={staff['id']}")
            self._set_cell_readonly(row, 8, date_text)

            # Approvers indicator (column 9)
            approvers_item = QTableWidgetItem()
            if staff.get('_approvers'):
                approvers_item.setText("✓ Індивідуальні")
                approvers_item.setToolTip(f"Індивідуальні погоджувачі: {len(staff['_approvers'])}")
            elif self._approvers:
                approvers_item.setText("✓")
                approvers_item.setToolTip(f"Погоджувачі налаштовані: {len(self._approvers)}")
            approvers_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.staff_table.setItem(row, 9, approvers_item)

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
        self.staff_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        self.staff_table.setColumnWidth(9, 120)

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

    def _on_table_item_changed(self, item):
        """Handle table item change - update selection."""
        if item.column() == 0:  # Only checkbox column
            self._on_selection_changed()

    def _on_table_item_double_clicked(self, row, column):
        """Handle double-click - open approvers dialog for per-staff override."""
        if column == 9:  # Approvers column
            # Get row and staff info
            checkbox = self.staff_table.item(row, 0)
            if not checkbox:
                return

            staff_info = checkbox.data(Qt.ItemDataRole.UserRole)
            if not staff_info:
                return

            # Check if per-staff override is allowed
            if self._apply_signatories_all:
                # Using same approvers for all - no override allowed
                return

            # Open approvers dialog for this staff
            current_approvers = staff_info.get('_approvers', self._approvers.copy())

            dialog = BulkApproversDialog(self, current_approvers)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_approvers = dialog.get_signatories()

                # Update staff info
                staff_info['_approvers'] = new_approvers

                # Update in _selected_staff
                for staff in self._selected_staff:
                    if staff['id'] == staff_info['id']:
                        staff['_approvers'] = new_approvers
                        break

                # Refresh table
                self._apply_filters(preserve_selection=True)

    def _on_selection_changed(self):
        """Handle selection change."""
        selected = []
        for row in range(self.staff_table.rowCount()):
            item = self.staff_table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
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

        # Ask for minimum vacation days (actual days will be adjusted per employee)
        days_dialog = QDialog(self)
        days_dialog.setWindowTitle("Автоматичний підбір дат")
        days_dialog.setMinimumSize(350, 200)
        days_layout = QVBoxLayout(days_dialog)

        days_layout.addWidget(QLabel("<b>Мінімальна кількість днів відпустки:</b>"))
        days_layout.addWidget(QLabel("<small>Буде підібрано для кожного співробітника індивідуально (враховуючи баланс та контракт)</small>"))

        days_spinbox = QSpinBox()
        days_spinbox.setMinimum(1)
        days_spinbox.setMaximum(30)
        days_spinbox.setValue(14)
        days_layout.addWidget(days_spinbox)

        # Admin override checkbox
        self.admin_override_check = QCheckBox("Admin override (ігнорувати баланс)")
        self.admin_override_check.setToolTip("Дозволити генерацію навіть якщо недостатньо днів відпустки")
        days_layout.addWidget(self.admin_override_check)

        # Earliest start date
        days_layout.addWidget(QLabel("Початок пошуку не раніше:"))
        start_date_edit = QDateEdit()
        start_date_edit.setCalendarPopup(True)
        start_date_edit.setDate(QDate.currentDate().addDays(14))
        days_layout.addWidget(start_date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(days_dialog.accept)
        buttons.rejected.connect(days_dialog.reject)
        days_layout.addWidget(buttons)

        if days_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        min_days = days_spinbox.value()
        admin_override = self.admin_override_check.isChecked()
        min_start_date = start_date_edit.date().toPyDate()

        # Process each employee individually
        self._auto_find_dates_for_all(min_days, admin_override, min_start_date)

    def _auto_find_dates_for_all(self, min_days: int, admin_override: bool, min_start_date: date):
        """Automatically find dates for all selected employees."""
        # Debug: check for duplicates in _selected_staff
        print(f"[DEBUG] _selected_staff count: {len(self._selected_staff)}")
        seen_ids = set()
        for s in self._selected_staff:
            if s['id'] in seen_ids:
                print(f"[DEBUG DUPLICATE] Found duplicate in _selected_staff: {s['pib_nom']} id={s['id']} position={s['position']}")
            seen_ids.add(s['id'])

        results = []
        errors = []  # List of tuples (staff_info, error_msg)

        for staff_info in self._selected_staff:
            # Adjust days based on balance if not admin override
            if admin_override:
                days_to_find = min_days
            else:
                days_to_find = min(min_days, staff_info['balance'])

            staff_details = f"{staff_info['pib_nom']} ({staff_info['position']}, {staff_info['rate']:.2f} ст.)"

            if days_to_find <= 0:
                errors.append((staff_info, f"{staff_details}: недостатній баланс ({staff_info['balance']} дн.)"))
                continue

            # Find available dates
            date_range = self._find_available_dates(staff_info, min_start_date, days_to_find)

            if date_range:
                start, end = date_range
                staff_info['_date_ranges'] = [date_range]
                staff_info['_selected_dates'] = f"{start.strftime('%d.%m')}-{end.strftime('%d.%m')}"
                print(f"[DEBUG AUTO] Found dates for {staff_info['pib_nom']}: {staff_info['_selected_dates']}")

                # Sync to _staff_data so filters can see the updates
                for staff in self._staff_data:
                    if staff['id'] == staff_info['id']:
                        staff['_date_ranges'] = staff_info['_date_ranges']
                        staff['_selected_dates'] = staff_info['_selected_dates']
                        break

                results.append({
                    'pib': staff_info['pib_nom'],
                    'dates': f"{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}",
                    'days': (end - start).days + 1
                })
            else:
                errors.append((staff_info, f"{staff_details}: немає доступних дат для {days_to_find} днів (баланс: {staff_info['balance']}, контракт: {staff_info['term_end'].strftime('%d.%m.%Y')})"))

        # Show summary - dates are already populated for successful ones
        self._show_auto_dates_summary(results, errors)

    def _show_auto_dates_summary(self, results: list, errors: list):
        """Show summary of automatic date selection."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Результат автоматичного підбору")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        # Success count
        success_count = len(results)
        if success_count > 0:
            layout.addWidget(QLabel(f"<h3>Успішно підібрано: {success_count}</h3>"))

        # Results list with regenerate buttons
        if results:
            results_group = QGroupBox("Підібрані дати:")
            results_layout = QVBoxLayout(results_group)
            results_layout.setSpacing(5)

            for r in results:
                row_layout = QHBoxLayout()

                text = f"{r['pib']}: {r['dates']} ({r['days']} дн.)"
                result_label = QLabel(text)
                result_label.setStyleSheet("color: #059669; font-size: 12px;")
                row_layout.addWidget(result_label, stretch=1)

                # Find staff_info by pib (use name that matches)
                staff_info = next((s for s in self._selected_staff if s['pib_nom'] == r['pib']), None)

                # Always add regenerate button for results
                regen_btn = QPushButton("🔄")
                regen_btn.setFixedWidth(40)
                regen_btn.setToolTip("Змінити параметри та перегенерувати")
                if staff_info:
                    regen_btn.clicked.connect(lambda checked, s=staff_info: self._regenerate_for_staff(s, dialog))
                else:
                    # If staff not found, try to find by position/rate combo
                    regen_btn.clicked.connect(lambda checked, p=r['pib']: self._regenerate_by_name(p, dialog))
                row_layout.addWidget(regen_btn)

                results_layout.addLayout(row_layout)

            layout.addWidget(results_group)

        # Errors with regenerate buttons
        if errors:
            errors_group = QGroupBox("Помилки:")
            errors_layout = QVBoxLayout(errors_group)
            errors_layout.setSpacing(5)

            for staff_info, error_msg in errors:
                error_row = QHBoxLayout()

                err_label = QLabel(error_msg)
                err_label.setStyleSheet("color: #DC2626; font-size: 12px;")
                error_row.addWidget(err_label, stretch=1)

                regen_btn = QPushButton("🔄")
                regen_btn.setFixedWidth(40)
                regen_btn.setToolTip("Змінити параметри та спробувати ще раз")
                regen_btn.clicked.connect(lambda checked, s=staff_info: self._regenerate_for_staff(s, dialog))
                error_row.addWidget(regen_btn)

                errors_layout.addLayout(error_row)

            layout.addWidget(errors_group)

        # If no results
        if not results and not errors:
            layout.addWidget(QLabel("Нічого не підібрано."))

        # Buttons
        buttons_layout = QHBoxLayout()

        # Regenerate All button (including successful)
        regenerate_all_btn = QPushButton("🔄 Перегенерувати всіх")
        regenerate_all_btn.setStyleSheet("padding: 8px 16px;")
        regenerate_all_btn.setToolTip("Перегенерувати для всіх обраних, включаючи успішні")
        regenerate_all_btn.clicked.connect(lambda: self._regenerate_all(dialog, include_successful=True))
        buttons_layout.addWidget(regenerate_all_btn)

        buttons_layout.addStretch()

        # Apply button
        apply_btn = QPushButton("✅ Застосувати")
        apply_btn.setStyleSheet("padding: 8px 16px; font-weight: bold;")
        apply_btn.setEnabled(success_count > 0)  # Enable only if there are results
        apply_btn.clicked.connect(lambda: self._apply_auto_dates(dialog))
        buttons_layout.addWidget(apply_btn)

        close_btn = QPushButton("Скасувати")
        close_btn.setStyleSheet("padding: 8px 16px;")
        close_btn.clicked.connect(dialog.reject)
        buttons_layout.addWidget(close_btn)

        layout.addLayout(buttons_layout)

        dialog.exec()

    def _regenerate_all(self, parent_dialog: QDialog = None, include_successful: bool = False):
        """Open regeneration dialog for all employees.

        Args:
            parent_dialog: Parent dialog to close after regeneration
            include_successful: If True, also regenerate for staff who already have dates
        """
        # Get all selected staff
        all_staff = list(self._selected_staff)
        if not all_staff:
            QMessageBox.warning(self, "Попередження", "Немає обраних співробітників!")
            return

        # Clear existing dates if including successful
        if include_successful:
            for staff_info in all_staff:
                staff_info['_date_ranges'] = []
                staff_info['_selected_dates'] = ''

        days_dialog = QDialog(self)
        days_dialog.setWindowTitle("Перегенерувати для всіх")
        days_dialog.setMinimumSize(400, 280)
        days_layout = QVBoxLayout(days_dialog)

        # Days count
        days_layout.addWidget(QLabel("<b>Кількість днів відпустки:</b>"))

        days_spinbox = QSpinBox()
        days_spinbox.setMinimum(1)
        days_spinbox.setMaximum(30)
        days_spinbox.setValue(14)
        days_layout.addWidget(days_spinbox)

        # Admin override checkbox
        admin_override_check = QCheckBox("Admin override (ігнорувати баланс)")
        days_layout.addWidget(admin_override_check)

        # Mode selection
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(QLabel("<b>Режим вибору дат:</b>"))
        mode_btn_group = QButtonGroup()

        single_range_radio = QRadioButton("Один безперервний діапазон")
        single_range_radio.setChecked(True)
        mode_layout.addWidget(single_range_radio)
        mode_btn_group.addButton(single_range_radio, 1)

        multiple_ranges_radio = QRadioButton("Кілька окремих діапазонів")
        mode_layout.addWidget(multiple_ranges_radio)
        mode_btn_group.addButton(multiple_ranges_radio, 2)

        single_dates_radio = QRadioButton("Окремі дні")
        mode_layout.addWidget(single_dates_radio)
        mode_btn_group.addButton(single_dates_radio, 3)

        mixed_radio = QRadioButton("Змішано (діапазони + окремі дні)")
        mode_layout.addWidget(mixed_radio)
        mode_btn_group.addButton(mixed_radio, 4)

        days_layout.addLayout(mode_layout)

        # Earliest start date
        days_layout.addWidget(QLabel("Початок пошуку не раніше:"))
        start_date_edit = QDateEdit()
        start_date_edit.setCalendarPopup(True)
        start_date_edit.setDate(QDate.currentDate().addDays(14))
        days_layout.addWidget(start_date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(days_dialog.accept)
        buttons.rejected.connect(days_dialog.reject)
        days_layout.addWidget(buttons)

        if days_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        min_days = days_spinbox.value()
        admin_override = admin_override_check.isChecked()
        min_start_date = start_date_edit.date().toPyDate()
        mode = mode_btn_group.checkedId()

        # Process all staff
        results = []
        errors = []

        for staff_info in all_staff:
            # Adjust days based on balance if not admin override
            if admin_override:
                days_to_find = min_days
            else:
                days_to_find = min(min_days, staff_info['balance'])

            staff_details = f"{staff_info['pib_nom']} ({staff_info['position']}, {staff_info['rate']:.2f} ст.)"

            if days_to_find <= 0:
                errors.append((staff_info, f"{staff_details}: недостатній баланс ({staff_info['balance']} дн.)"))
                continue

            # Find available dates based on mode
            if mode == 1:  # Single range
                date_range = self._find_available_dates(staff_info, min_start_date, days_to_find)
                date_ranges = [date_range] if date_range else []
            elif mode == 2:  # Multiple ranges
                date_ranges = self._find_multiple_ranges(staff_info, min_start_date, days_to_find)
            elif mode == 3:  # Single dates
                date_ranges = self._find_single_dates(staff_info, min_start_date, days_to_find)
            elif mode == 4:  # Mixed
                date_ranges = self._find_mixed_dates(staff_info, min_start_date, days_to_find)
            else:
                date_range = self._find_available_dates(staff_info, min_start_date, days_to_find)
                date_ranges = [date_range] if date_range else []

            if date_ranges:
                staff_info['_date_ranges'] = date_ranges
                # Format for display
                date_str_parts = []
                for start, end in date_ranges:
                    if start == end:
                        date_str_parts.append(start.strftime('%d.%m'))
                    else:
                        date_str_parts.append(f"{start.strftime('%d.%m')}-{end.strftime('%d.%m')}")
                staff_info['_selected_dates'] = ", ".join(date_str_parts)

                # Sync to _staff_data so filters can see the updates
                for staff in self._staff_data:
                    if staff['id'] == staff_info['id']:
                        staff['_date_ranges'] = staff_info['_date_ranges']
                        staff['_selected_dates'] = staff_info['_selected_dates']
                        break

                total_days = sum((end - start).days + 1 for start, end in date_ranges)
                results.append({
                    'pib': staff_info['pib_nom'],
                    'dates': staff_info['_selected_dates'],
                    'days': total_days
                })
            else:
                errors.append((staff_info, f"{staff_details}: немає доступних дат для {days_to_find} днів"))

        # Close parent dialog and show new summary
        if parent_dialog:
            parent_dialog.accept()

        self._show_auto_dates_summary(results, errors)

    def _find_multiple_ranges(self, staff_info: dict, start_from: date, days_needed: int) -> list:
        """Find multiple separate ranges (e.g., 2 weeks of 5 days each)."""
        ranges = []
        remaining_days = days_needed
        current_start = start_from
        max_search = 180  # 6 months max search
        locked = staff_info['locked_dates']

        while remaining_days > 0 and (current_start - start_from).days < max_search:
            # Skip locked dates and weekends
            while current_start.weekday() >= 5 or current_start in locked:
                current_start += timedelta(days=1)
                if (current_start - start_from).days >= max_search:
                    return ranges

            # Try to find a range of 5 days
            range_days = min(5, remaining_days)
            date_range = self._find_available_dates(staff_info, current_start, range_days)

            if date_range:
                ranges.append(date_range)
                remaining_days -= range_days
                current_start = date_range[1] + timedelta(days=2)  # Gap of 1 day between ranges
            else:
                current_start += timedelta(days=1)

        return ranges

    def _find_single_dates(self, staff_info: dict, start_from: date, days_needed: int) -> list:
        """Find separate individual days."""
        dates = []
        locked = staff_info['locked_dates']
        contract_end = staff_info['term_end']
        current = start_from
        max_search = 180

        while len(dates) < days_needed and (current - start_from).days < max_search:
            # Skip locked dates, weekends, and contract end
            if current <= contract_end and current.weekday() < 5 and current not in locked:
                dates.append((current, current))
                remaining_days = days_needed - len(dates)
                if remaining_days > 0:
                    # Skip next day to have at least 1 day gap
                    current += timedelta(days=2)
                    continue
            current += timedelta(days=1)

        return dates

    def _find_mixed_dates(self, staff_info: dict, start_from: date, days_needed: int) -> list:
        """Find mixed: ranges and single days."""
        # Use 70% for main range, 30% for single days
        range_days = max(1, int(days_needed * 0.7))
        single_days = max(1, days_needed - range_days)

        ranges = []
        locked = staff_info['locked_dates']

        # Skip to first available date
        current = start_from
        while current.weekday() >= 5 or current in locked:
            current += timedelta(days=1)

        # Find main range
        date_range = self._find_available_dates(staff_info, current, range_days)
        if date_range:
            ranges.append(date_range)

        # Find single days after the range
        if date_range:
            search_from = date_range[1] + timedelta(days=2)
        else:
            search_from = current

        # Skip to next available for single days
        while search_from.weekday() >= 5 or search_from in locked:
            search_from += timedelta(days=1)

        single_dates = self._find_single_dates(staff_info, search_from, single_days)
        ranges.extend(single_dates)

        return ranges[:days_needed]

    def _regenerate_for_staff(self, staff_info: dict, parent_dialog: QDialog = None):
        """Open regeneration dialog for a specific staff member."""
        # Clear existing dates first
        staff_info['_date_ranges'] = []
        staff_info['_selected_dates'] = ''

        # Sync to _staff_data so filters can see the updates
        for staff in self._staff_data:
            if staff['id'] == staff_info['id']:
                staff['_date_ranges'] = staff_info['_date_ranges']
                staff['_selected_dates'] = staff_info['_selected_dates']
                break

        # Get current parameters
        days_dialog = QDialog(self)
        days_dialog.setWindowTitle(f"Перегенерувати для {staff_info['pib_nom']}")
        days_dialog.setMinimumSize(400, 280)
        days_layout = QVBoxLayout(days_dialog)

        days_layout.addWidget(QLabel(f"<b>Кількість днів відпустки:</b> (баланс: {staff_info['balance']} дн.)"))

        days_spinbox = QSpinBox()
        days_spinbox.setMinimum(1)
        days_spinbox.setMaximum(30)
        days_spinbox.setValue(14)
        days_layout.addWidget(days_spinbox)

        # Admin override checkbox
        admin_override_check = QCheckBox("Admin override (ігнорувати баланс)")
        days_layout.addWidget(admin_override_check)

        # Mode selection
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(QLabel("<b>Режим вибору дат:</b>"))
        mode_btn_group = QButtonGroup()

        single_range_radio = QRadioButton("Один безперервний діапазон")
        single_range_radio.setChecked(True)
        mode_layout.addWidget(single_range_radio)
        mode_btn_group.addButton(single_range_radio, 1)

        multiple_ranges_radio = QRadioButton("Кілька окремих діапазонів")
        mode_layout.addWidget(multiple_ranges_radio)
        mode_btn_group.addButton(multiple_ranges_radio, 2)

        single_dates_radio = QRadioButton("Окремі дні")
        mode_layout.addWidget(single_dates_radio)
        mode_btn_group.addButton(single_dates_radio, 3)

        mixed_radio = QRadioButton("Змішано (діапазони + окремі дні)")
        mode_layout.addWidget(mixed_radio)
        mode_btn_group.addButton(mixed_radio, 4)

        days_layout.addLayout(mode_layout)

        # Earliest start date
        days_layout.addWidget(QLabel("Початок пошуку не раніше:"))
        start_date_edit = QDateEdit()
        start_date_edit.setCalendarPopup(True)
        start_date_edit.setDate(QDate.currentDate())
        days_layout.addWidget(start_date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(days_dialog.accept)
        buttons.rejected.connect(days_dialog.reject)
        days_layout.addWidget(buttons)

        if days_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        days_count = days_spinbox.value()
        admin_override = admin_override_check.isChecked()
        min_start_date = start_date_edit.date().toPyDate()
        mode = mode_btn_group.checkedId()

        # Adjust days based on balance if not admin override
        if not admin_override:
            days_count = min(days_count, staff_info['balance'])

        # Find dates based on mode
        if mode == 1:  # Single range
            date_range = self._find_available_dates(staff_info, min_start_date, days_count)
            date_ranges = [date_range] if date_range else []
        elif mode == 2:  # Multiple ranges
            date_ranges = self._find_multiple_ranges(staff_info, min_start_date, days_count)
        elif mode == 3:  # Single dates
            date_ranges = self._find_single_dates(staff_info, min_start_date, days_count)
        elif mode == 4:  # Mixed
            date_ranges = self._find_mixed_dates(staff_info, min_start_date, days_count)
        else:
            date_range = self._find_available_dates(staff_info, min_start_date, days_count)
            date_ranges = [date_range] if date_range else []

        if date_ranges:
            staff_info['_date_ranges'] = date_ranges
            # Format for display
            date_str_parts = []
            for start, end in date_ranges:
                if start == end:
                    date_str_parts.append(start.strftime('%d.%m'))
                else:
                    date_str_parts.append(f"{start.strftime('%d.%m')}-{end.strftime('%d.%m')}")
            staff_info['_selected_dates'] = ", ".join(date_str_parts)
            print(f"[DEBUG] Applied dates for {staff_info['pib_nom']}: {staff_info['_selected_dates']}")

            # Sync to _staff_data so filters can see the updates
            for staff in self._staff_data:
                if staff['id'] == staff_info['id']:
                    staff['_date_ranges'] = staff_info['_date_ranges']
                    staff['_selected_dates'] = staff_info['_selected_dates']
                    print(f"[DEBUG] Synced dates to _staff_data for {staff['pib_nom']}")
                    break

            # Close parent dialog if provided and refresh summary
            if parent_dialog:
                parent_dialog.accept()
                # Refresh the summary with new data
                self._refresh_auto_dates_summary()
        else:
            QMessageBox.warning(self, "Не вдалося", "Немає доступних дат для вказаних параметрів.")

    def _refresh_auto_dates_summary(self):
        """Refresh and show the summary with current staff data."""
        results = []
        errors = []

        for staff_info in self._selected_staff:
            date_ranges = staff_info.get('_date_ranges', [])
            if date_ranges:
                # Format for display
                date_str_parts = []
                for start, end in date_ranges:
                    if start == end:
                        date_str_parts.append(start.strftime('%d.%m'))
                    else:
                        date_str_parts.append(f"{start.strftime('%d.%m')}-{end.strftime('%d.%m')}")
                staff_info['_selected_dates'] = ", ".join(date_str_parts)

                total_days = sum((end - start).days + 1 for start, end in date_ranges)
                results.append({
                    'pib': staff_info['pib_nom'],
                    'dates': staff_info['_selected_dates'],
                    'days': total_days
                })
            else:
                staff_details = f"{staff_info['pib_nom']} ({staff_info['position']}, {staff_info['rate']:.2f} ст.)"
                errors.append((staff_info, f"{staff_details}: не підібрано дати"))

        self._show_auto_dates_summary(results, errors)

    def _regenerate_by_name(self, pib_name: str, parent_dialog: QDialog = None):
        """Find staff by name and regenerate dates."""
        staff_info = next((s for s in self._selected_staff if s['pib_nom'] == pib_name), None)
        if staff_info:
            self._regenerate_for_staff(staff_info, parent_dialog)
        else:
            QMessageBox.warning(self, "Помилка", f"Не знайдено співробітника: {pib_name}")

    def _apply_auto_dates(self, parent_dialog: QDialog = None):
        """Apply selected dates and close the dialog."""
        print(f"[DEBUG APPLY] Applying auto dates for {len(self._selected_staff)} staff")
        print(f"[DEBUG APPLY] Checking dates in staff_data:")
        for staff in self._staff_data:
            dates = staff.get('_selected_dates', '')
            if dates:
                print(f"  - {staff['pib_nom']}: {dates}")

        # Refresh table to ensure all dates are displayed
        self._apply_filters()

        # Close parent dialog
        if parent_dialog:
            parent_dialog.accept()
        else:
            # Find and close the summary dialog
            for child in self.findChildren(QDialog):
                if child.windowTitle() == "Результат автоматичного підбору":
                    child.accept()
                    break

    def _configure_approvers(self):
        """Configure approvers for bulk generation."""
        default_signatories = self._get_default_signatories()

        dialog = BulkApproversDialog(self, default_signatories)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._signatories = dialog.get_signatories()
            self._approvers = self._signatories  # Sync for generation
            # apply_all_check = True means use same approvers for ALL staff
            # apply_all_check = False means allow per-staff overrides
            self._apply_signatories_all = dialog.get_apply_all()

            if self._signatories:
                count = len(self._signatories)
                self.approvers_info.setText(f"Налаштовано: {count} погоджувачів")
            else:
                self.approvers_info.setText("Буде використано системні налаштування")

            # Refresh table to show approvers indicator
            self._apply_filters(preserve_selection=True)

    def _configure_staff_approvers(self):
        """Configure custom approvers for selected staff member."""
        # Get selected rows
        selected_rows = set()
        for index in range(self.staff_table.rowCount()):
            checkbox = self.staff_table.item(index, 0)
            if checkbox.checkState() == Qt.CheckState.Checked:
                selected_rows.add(index)

        if not selected_rows:
            QMessageBox.warning(self, "Увага", "Спочатку оберіть співробітника у таблиці")
            return

        if len(selected_rows) > 1:
            QMessageBox.warning(self, "Увага", "Оберіть лише одного співробітника для налаштування погоджувачів")
            return

        # Get the staff info
        row = list(selected_rows)[0]
        staff_info = self.staff_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not staff_info:
            return

        # Get current approvers for this staff or use default
        current_approvers = staff_info.get('_approvers', self._approvers.copy())

        dialog = BulkApproversDialog(self, current_approvers)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_approvers = dialog.get_signatories()

            # Apply to selected staff
            for index in selected_rows:
                checkbox = self.staff_table.item(index, 0)
                staff_data = checkbox.data(Qt.ItemDataRole.UserRole)
                if staff_data:
                    staff_data['_approvers'] = new_approvers

            # Update selected_staff list
            for staff in self._selected_staff:
                if staff['id'] == staff_info['id']:
                    staff['_approvers'] = new_approvers
                    break

            QMessageBox.information(self, "Успішно", f"Погоджувачі оновлені для {staff_info['pib_nom']}")

    def _get_default_signatories(self) -> list[dict]:
        """Get default signatories from settings."""
        signatories = []
        with get_db_context() as db:
            approvers = db.query(Approvers).order_by(Approvers.order_index).all()

            for a in approvers:
                # Format name as "Василь САВИК" (first name + surname uppercase)
                full_name = a.full_name_nom or ''
                name_parts = full_name.split()
                if len(name_parts) >= 3:
                    # "Савик Василь Миколайович" -> "Василь САВИК"
                    formatted_name = f"{name_parts[1]} {name_parts[0].upper()}"
                elif len(name_parts) == 2:
                    # "Василь Савик" -> "Василь САВИК"
                    formatted_name = f"{name_parts[0]} {name_parts[1].upper()}"
                else:
                    formatted_name = full_name

                signatories.append({
                    'position': a.position_name,
                    'position_multiline': '',  # Will be calculated automatically when rendering
                    'name': formatted_name
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

                    # Check for locked date overlap
                    locked_dates = staff_info.get('locked_dates', set())
                    overlap_found = False
                    overlap_msg = ""
                    for d in locked_dates:
                        if date_start <= d <= date_end:
                            overlap_found = True
                            overlap_msg = d.strftime('%d.%m.%Y')
                            break

                    if overlap_found:
                        errors.append(f"{staff_info['pib_nom']}: обрані дати перетинаються з вже заброньованою датою {overlap_msg}")
                        continue

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
                        )

                        db.add(doc)
                        db.commit()
                        db.refresh(doc)

                        # Determine which approvers to use
                        if self._apply_signatories_all:
                            # Use global approvers
                            signatories_for_doc = self._approvers
                        else:
                            # Use per-staff approvers if set, otherwise global
                            signatories_for_doc = staff_info.get('_approvers') or self._approvers

                        # Generate PDF using same method as builder tab
                        doc_service = DocumentService(db, grammar)
                        output_path = doc_service.generate_document_from_template(
                            doc, staff_info, signatories=signatories_for_doc, bulk_mode=True
                        )

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

    def _select_document_type(self) -> tuple[DocumentType, bool]:
        """Select document type."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Тип документа")
        layout = QVBoxLayout(dialog)

        label = QLabel("Оберіть тип документів для генерації:")
        layout.addWidget(label)

        combo = QComboBox()
        combo.addItem("Оплачувана відпустка", DocumentType.VACATION_PAID)
        combo.addItem("Відпустка без збереження", DocumentType.VACATION_UNPAID)
        layout.addWidget(combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return combo.currentData(), True
        return DocumentType.VACATION_PAID, False

    def _find_available_dates(self, staff_info: dict, start_from: date = None, days_needed: int = 14) -> tuple | None:
        """Find available dates for a staff member."""
        if start_from is None:
            start_from = date.today()

        contract_end = staff_info['term_end']
        locked = staff_info['locked_dates']

        # Debug output
        print(f"[DEBUG] _find_available_dates for {staff_info['pib_nom']}: start_from={start_from}, days_needed={days_needed}, locked_count={len(locked)}")
        if locked:
            print(f"[DEBUG] Locked dates: {sorted(list(locked))[:5]}...")

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
                    print(f"[DEBUG] Blocked at {check_date} (locked)")
                    all_available = False
                    break

            if all_available:
                result = (current, current + timedelta(days=days_needed - 1))
                print(f"[DEBUG] Found range: {result[0]} - {result[1]}")
                return result

            current += timedelta(days=1)

        print(f"[DEBUG] No available dates found")
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
        msg.setMinimumSize(500, 300)
        layout = QVBoxLayout(msg)

        # Build full text for copying
        full_text = []

        if generated:
            success_label = QLabel(f"Успішно згенеровано: {len(generated)} документів")
            success_label.setStyleSheet("color: #059669; font-weight: bold;")
            layout.addWidget(success_label)
            full_text.append(f"Успішно згенеровано: {len(generated)} документів")

        if errors:
            error_label = QLabel(f"Помилки ({len(errors)}):")
            error_label.setStyleSheet("color: #DC2626; font-weight: bold;")
            layout.addWidget(error_label)

            error_text = "\n".join(errors)
            error_display = QTextEdit()
            error_display.setPlainText(error_text)
            error_display.setReadOnly(True)
            error_display.setMaximumHeight(150)
            layout.addWidget(error_display)

            full_text.append(f"\nПомилки ({len(errors)}):")
            full_text.append(error_text)

        # Buttons layout
        buttons_layout = QHBoxLayout()

        # Copy button
        if generated or errors:
            copy_btn = QPushButton("📋 Копіювати")
            copy_btn.setStyleSheet("padding: 8px 16px;")
            copy_btn.clicked.connect(lambda: self._copy_results("\n".join(full_text)))
            buttons_layout.addWidget(copy_btn)

        buttons_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet("padding: 8px 16px;")
        ok_btn.clicked.connect(msg.accept)
        buttons_layout.addWidget(ok_btn)

        layout.addLayout(buttons_layout)

        if generated:
            self.document_created.emit()

        msg.exec()

    def _copy_results(self, text: str):
        """Copy results to clipboard."""
        from PyQt6.QtGui import QClipboard
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Скопійовано", "Результати скопійовано до буфера обміну")
