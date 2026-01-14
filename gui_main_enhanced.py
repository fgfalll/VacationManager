import sys
import os
from datetime import datetime, date
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QSplitter,
    QLineEdit, QMessageBox, QComboBox, QHeaderView, QFileDialog,
    QDialog, QDialogButtonBox, QDateEdit, QRadioButton, QButtonGroup,
    QGroupBox, QCheckBox, QProgressBar, QStatusBar, QFormLayout,
    QSpinBox, QDoubleSpinBox, QTextEdit, QScrollArea, QFrame,
    QTabWidget, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QTimer, QObject, QThread
from PyQt6.QtGui import QFont, QIcon, QPixmap

from sqlalchemy.orm import Session
from app.models import Staff, VacationRequest, LeaveReason, create_tables, init_default_data, get_db
from app.logic import generate_vacation_document, calculate_vacation_days, get_payment_phrase, format_display_name
try:
    from app.logic_enhanced import generate_vacation_document_enhanced, format_vacation_description
except ImportError:
    # If not in app package, try direct import
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from logic_enhanced import generate_vacation_document_enhanced, format_vacation_description
from config import SIGNATORIES, EMPLOYMENT_TYPES, POSITIONS, ACADEMIC_DEGREES, LEAVE_TYPES, STATUSES

class VacationPeriodWidget(QWidget):
    """Widget for managing a single vacation period"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()

        # From date
        layout.addWidget(QLabel("З:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        layout.addWidget(self.start_date)

        # To date
        layout.addWidget(QLabel("По:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addDays(3))
        layout.addWidget(self.end_date)

        # Days count
        self.days_label = QLabel("4 днів")
        layout.addWidget(self.days_label)

        # Remove button
        self.remove_btn = QPushButton("Видалити")
        self.remove_btn.setMaximumWidth(80)
        layout.addWidget(self.remove_btn)

        self.setLayout(layout)

        # Connect signals
        self.start_date.dateChanged.connect(self.update_days)
        self.end_date.dateChanged.connect(self.update_days)
        self.remove_btn.clicked.connect(self.remove_requested)

    def update_days(self):
        """Update days count"""
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        days = (end - start).days + 1
        self.days_label.setText(f"{days} днів")
        self.parent().parent().update_total_days()

    def remove_requested(self):
        """Emit signal to remove this period"""
        self.parent().remove_period(self)

    def get_period_data(self):
        """Get period data"""
        return {
            'start_date': self.start_date.date().toPyDate(),
            'end_date': self.end_date.date().toPyDate()
        }

class VacationPeriodsList(QWidget):
    """Widget for managing multiple vacation periods"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.periods = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Add period button
        self.add_period_btn = QPushButton("Додати період")
        self.add_period_btn.clicked.connect(self.add_period)
        layout.addWidget(self.add_period_btn)

        # Scroll area for periods
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.AsNeeded)
        self.periods_container = QWidget()
        self.periods_layout = QVBoxLayout(self.periods_container)
        scroll.setWidget(self.periods_container)
        layout.addWidget(scroll)

        self.setLayout(layout)

        # Add initial period
        self.add_period()

    def add_period(self):
        """Add a new vacation period"""
        period = VacationPeriodWidget(self)
        self.periods.append(period)
        self.periods_layout.addWidget(period)
        self.update_total_days()

    def remove_period(self, period):
        """Remove a vacation period"""
        if len(self.periods) > 1:  # Keep at least one period
            self.periods.remove(period)
            self.periods_layout.removeWidget(period)
            period.deleteLater()
            self.update_total_days()
        else:
            QMessageBox.warning(self, "Помилка", "Повинен бути хоча б один період відпустки")

    def update_total_days(self):
        """Update total days count"""
        total = 0
        for period in self.periods:
            start = period.start_date.date().toPyDate()
            end = period.end_date.date().toPyDate()
            total += (end - start).days + 1

        if hasattr(self.parent(), 'update_total_days_label'):
            self.parent().update_total_days_label(total)

    def get_all_periods(self):
        """Get all vacation periods"""
        return [period.get_period_data() for period in self.periods]

class DocGenWorker(QObject):
    """Worker for generating documents in a separate thread"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, request_id, data, parent=None):
        super().__init__(parent)
        self.request_id = request_id
        self.data = data

    def generate(self):
        """Generate the vacation document"""
        try:
            file_path = generate_vacation_document_enhanced(
                request_id=self.request_id,
                staff_info=self.data['staff_info'],
                periods=self.data['periods'],
                total_days=self.data['total_days'],
                leave_type=self.data['leave_type'],
                reason_text=self.data.get('reason_text'),
                custom_description=self.data['description'] if not self.data['periods'] else ""
            )
            self.finished.emit(file_path)
        except Exception as e:
            import traceback
            self.error.emit(f"Помилка у фоновому режимі: {e}\n{traceback.format_exc()}")

class CreateVacationDialogEnhanced(QDialog):
    """Enhanced dialog for creating new vacation requests with complex date support"""
    def __init__(self, parent=None, staff_id=None):
        super().__init__(parent)
        self.setWindowTitle("Створити заяву на відпустку")
        self.setMinimumWidth(700)
        self.staff_id = staff_id
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Staff selection
        staff_group = QGroupBox("Співробітник")
        staff_layout = QHBoxLayout()

        self.staff_combo = QComboBox()
        self.staff_combo.setMinimumWidth(400)
        staff_layout.addWidget(QLabel("Оберіть співробітника:"))
        staff_layout.addWidget(self.staff_combo)
        staff_group.setLayout(staff_layout)
        layout.addWidget(staff_group)

        # Vacation type selection
        type_group = QGroupBox("Тип відпустки")
        type_layout = QVBoxLayout()

        self.vacation_type_group = QButtonGroup()
        self.continuous_radio = QRadioButton("Неперервний період")
        self.split_radio = QRadioButton("Розділені періоди")
        self.custom_radio = QRadioButton("Користувацький опис")
        self.vacation_type_group.addButton(self.continuous_radio, 0)
        self.vacation_type_group.addButton(self.split_radio, 1)
        self.vacation_type_group.addButton(self.custom_radio, 2)
        self.continuous_radio.setChecked(True)

        type_layout.addWidget(self.continuous_radio)
        type_layout.addWidget(self.split_radio)
        type_layout.addWidget(self.custom_radio)

        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # Tab widget for different input methods
        self.tab_widget = QTabWidget()

        # Continuous period tab
        self.continuous_tab = QWidget()
        continuous_layout = QVBoxLayout()

        continuous_dates = QHBoxLayout()
        continuous_dates.addWidget(QLabel("З:"))
        self.cont_start_date = QDateEdit()
        self.cont_start_date.setCalendarPopup(True)
        self.cont_start_date.setDate(QDate.currentDate())
        continuous_dates.addWidget(self.cont_start_date)

        continuous_dates.addWidget(QLabel("По:"))
        self.cont_end_date = QDateEdit()
        self.cont_end_date.setCalendarPopup(True)
        self.cont_end_date.setDate(QDate.currentDate().addDays(14))
        continuous_dates.addWidget(self.cont_end_date)

        continuous_layout.addLayout(continuous_dates)
        self.cont_days_label = QLabel("Загальна кількість днів: 15")
        continuous_layout.addWidget(self.cont_days_label)
        self.continuous_tab.setLayout(continuous_layout)

        # Split periods tab
        self.split_tab = QWidget()
        split_layout = QVBoxLayout()
        self.periods_list = VacationPeriodsList(self.split_tab)
        split_layout.addWidget(self.periods_list)
        self.split_tab.setLayout(split_layout)

        # Custom description tab
        self.custom_tab = QWidget()
        custom_layout = QVBoxLayout()
        custom_layout.addWidget(QLabel("Опишіть періоди відпустки:"))
        self.custom_description = QTextEdit()
        self.custom_description.setMaximumHeight(150)
        self.custom_description.setPlaceholderText(
            "Наприклад:\n"
            "з 29.12.2025 по 31.12.2025 (3 дні)\n"
            "з 05.01.2026 по 09.01.2026 (5 днів)\n"
            "з 12.01.2026 по 16.01.2026 (5 днів)"
        )
        custom_layout.addWidget(self.custom_description)

        self.custom_days_spin = QSpinBox()
        self.custom_days_spin.setRange(1, 365)
        self.custom_days_spin.setValue(13)
        custom_days_layout = QHBoxLayout()
        custom_days_layout.addWidget(QLabel("Загальна кількість днів:"))
        custom_days_layout.addWidget(self.custom_days_spin)
        custom_days_layout.addStretch()
        custom_layout.addLayout(custom_days_layout)

        self.custom_tab.setLayout(custom_layout)

        # Add tabs to widget
        self.tab_widget.addTab(self.continuous_tab, "Неперервний період")
        self.tab_widget.addTab(self.split_tab, "Розділені періоди")
        self.tab_widget.addTab(self.custom_tab, "Користувацький")

        layout.addWidget(self.tab_widget)

        # Leave type (paid/unpaid)
        leave_group = QGroupBox("Тип відпустки (оплачувана/неоплачувана)")
        leave_layout = QVBoxLayout()

        self.leave_type_group = QButtonGroup()
        self.paid_radio = QRadioButton("Оплачувана відпустка")
        self.unpaid_radio = QRadioButton("Відпустка без збереження заробітної плати")
        self.leave_type_group.addButton(self.paid_radio, 0)
        self.leave_type_group.addButton(self.unpaid_radio, 1)
        self.paid_radio.setChecked(True)

        leave_layout.addWidget(self.paid_radio)
        leave_layout.addWidget(self.unpaid_radio)

        # Payment info (for paid leave)
        self.payment_label = QLabel("")
        self.payment_label.setStyleSheet("color: blue; font-weight: bold;")
        leave_layout.addWidget(self.payment_label)

        # Reason selection (for unpaid leave)
        reason_layout = QHBoxLayout()
        reason_layout.addWidget(QLabel("Причина:"))
        self.reason_combo = QComboBox()
        self.reason_combo.setEditable(True)
        reason_layout.addWidget(self.reason_combo)
        leave_layout.addLayout(reason_layout)

        leave_group.setLayout(leave_layout)
        layout.addWidget(leave_group)

        # Total days summary
        self.total_days_label = QLabel("Всього днів відпустки: 15")
        self.total_days_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.total_days_label)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # Connect signals
        self.cont_start_date.dateChanged.connect(self.update_continuous_days)
        self.cont_end_date.dateChanged.connect(self.update_continuous_days)
        self.vacation_type_group.buttonClicked.connect(self.on_vacation_type_changed)
        self.leave_type_group.buttonClicked.connect(self.update_leave_type)
        self.reason_combo.editTextChanged.connect(self.on_reason_changed)
        self.custom_days_spin.valueChanged.connect(self.update_total_days_label)

    def load_data(self):
        """Load staff and leave reasons data"""
        db = next(get_db())
        try:
            # Load staff
            staff = db.query(Staff).all()
            self.staff_combo.clear()
            for s in staff:
                display_text = format_display_name({
                    'full_name': s.full_name,
                    'academic_degree': s.academic_degree,
                    'position': s.position
                })
                self.staff_combo.addItem(display_text, s.id)

            # Select staff if provided
            if self.staff_id:
                for i in range(self.staff_combo.count()):
                    if self.staff_combo.itemData(i) == self.staff_id:
                        self.staff_combo.setCurrentIndex(i)
                        break

            # Load leave reasons
            reasons = db.query(LeaveReason).all()
            self.reason_combo.clear()
            for r in reasons:
                self.reason_combo.addItem(r.reason_text)
        finally:
            db.close()

        # Update UI
        self.update_continuous_days()
        self.update_leave_type()

    def on_vacation_type_changed(self):
        """Handle vacation type change"""
        button_id = self.vacation_type_group.checkedId()
        self.tab_widget.setCurrentIndex(button_id)
        self.update_total_days_label()

    def update_continuous_days(self):
        """Update days count for continuous period"""
        start = self.cont_start_date.date().toPyDate()
        end = self.cont_end_date.date().toPyDate()
        days = (end - start).days + 1
        self.cont_days_label.setText(f"Загальна кількість днів: {days}")
        if self.continuous_radio.isChecked():
            self.update_total_days_label(days)

    def update_total_days_label(self, days=None):
        """Update total days label"""
        if days is None:
            if self.continuous_radio.isChecked():
                start = self.cont_start_date.date().toPyDate()
                end = self.cont_end_date.date().toPyDate()
                days = (end - start).days + 1
            elif self.split_radio.isChecked():
                total = 0
                for period in self.periods_list.periods:
                    start = period.start_date.date().toPyDate()
                    end = period.end_date.date().toPyDate()
                    total += (end - start).days + 1
                days = total
            elif self.custom_radio.isChecked():
                days = self.custom_days_spin.value()

        self.total_days_label.setText(f"Всього днів відпустки: {days}")

    def update_leave_type(self):
        """Update UI based on leave type selection"""
        is_paid = self.paid_radio.isChecked()

        if is_paid:
            self.reason_combo.setEnabled(False)
            self.payment_label.setVisible(True)
            # Calculate payment phrase
            if self.continuous_radio.isChecked():
                start = self.cont_start_date.date().toPyDate()
            else:
                start = QDate.currentDate().toPyDate()
            payment = get_payment_phrase(start)
            self.payment_label.setText(f"Виплата зарплати: {payment}")
        else:
            self.reason_combo.setEnabled(True)
            self.payment_label.setVisible(False)

    def on_reason_changed(self, text):
        """Handle reason text change"""
        pass

    def get_data(self):
        """Get form data"""
        db = next(get_db())
        try:
            staff_id = self.staff_combo.currentData()
            staff = db.query(Staff).filter_by(id=staff_id).first()

            # Determine vacation periods
            if self.continuous_radio.isChecked():
                periods = [{
                    'start_date': self.cont_start_date.date().toPyDate(),
                    'end_date': self.cont_end_date.date().toPyDate()
                }]
                description = f"з {self.cont_start_date.date().toString('dd.MM.yyyy')} по {self.cont_end_date.date().toString('dd.MM.yyyy')}"
            elif self.split_radio.isChecked():
                periods = self.periods_list.get_all_periods()
                descriptions = []
                for period in periods:
                    descriptions.append(
                        f"з {period['start_date'].strftime('%d.%m.%Y')} по {period['end_date'].strftime('%d.%m.%Y')}"
                    )
                description = ", ".join(descriptions)
            else:  # custom
                periods = []  # Will be handled differently in document generation
                description = self.custom_description.toPlainText().strip()

            # Calculate total days
            if periods:
                total_days = sum((p['end_date'] - p['start_date']).days + 1 for p in periods)
            else:
                total_days = self.custom_days_spin.value()

            data = {
                'staff_id': staff_id,
                'staff_info': {
                    'full_name': staff.full_name,
                    'position': staff.position,
                    'academic_degree': staff.academic_degree
                },
                'periods': periods,
                'total_days': total_days,
                'description': description,
                'leave_type': 'PAID' if self.paid_radio.isChecked() else 'UNPAID',
                'reason_text': self.reason_combo.currentText().strip()
            }
            return data
        finally:
            db.close()