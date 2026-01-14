import sys
import os
from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QSplitter,
    QLineEdit, QMessageBox, QComboBox, QHeaderView, QFileDialog,
    QDialog, QDialogButtonBox, QDateEdit, QRadioButton, QButtonGroup,
    QGroupBox, QCheckBox, QProgressBar, QStatusBar, QFormLayout,
    QSpinBox, QDoubleSpinBox, QTextEdit, QScrollArea, QFrame,
    QTabWidget, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap

class VacationPeriodWidget(QFrame):
    """Widget for managing a single vacation period"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # Create a frame with border for better visual separation
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(5)

        # Checkbox for one day
        self.one_day_checkbox = QCheckBox("Один день")
        self.one_day_checkbox.setChecked(False)
        layout.addWidget(self.one_day_checkbox)

        # Date layout
        self.date_layout = QHBoxLayout()

        # From date
        self.date_layout.addWidget(QLabel("З:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setMinimumDate(QDate.currentDate())  # Не можна вибрати дату в минулому
        self.date_layout.addWidget(self.start_date)

        # To date
        self.date_layout.addWidget(QLabel("По:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addDays(3))
        self.end_date.setMinimumDate(QDate.currentDate())  # Не можна вибрати дату в минулому
        self.date_layout.addWidget(self.end_date)

        layout.addLayout(self.date_layout)

        # Days count
        self.days_label = QLabel("4 дні")
        layout.addWidget(self.days_label)

        # Remove button
        self.remove_btn = QPushButton("Видалити")
        self.remove_btn.setMaximumWidth(80)
        layout.addWidget(self.remove_btn)

        self.setLayout(layout)

        # Connect signals
        self.one_day_checkbox.toggled.connect(self.on_one_day_toggled)
        self.start_date.dateChanged.connect(self.on_start_date_changed)
        self.end_date.dateChanged.connect(self.update_days)
        self.remove_btn.clicked.connect(self.remove_requested)

    def on_one_day_toggled(self, checked):
        """Handle one day checkbox toggle"""
        # Показуємо або приховуємо елементи для вибору дати "По"
        self.date_layout.itemAt(2).widget().setVisible(not checked)  # Label "Po:"
        self.end_date.setVisible(not checked)

        if checked:
            # Якщо вибрано один день, встановлюємо кінцеву дату = початковій
            self.end_date.setDate(self.start_date.date())

        self.update_days()

    def on_start_date_changed(self, date):
        """Handle start date change"""
        # Перевіряємо, що кінцева дата не менша за нову початкову
        if self.end_date.date() < date:
            self.end_date.setDate(date)
        self.update_days()

    def update_days(self):
        """Update days count"""
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()

        # Перевіряємо, що кінцева дата не менша за початкову
        if end < start:
            # Автоматично виправляємо дату
            self.end_date.setDate(self.start_date.date())
            end = start

        # Перевіряємо, що дати не в минулому
        today = date.today()
        if start < today:
            # Встановлюємо початкову дату на сьогодні
            self.start_date.setDate(QDate(today))
            start = today
            if end < start:
                self.end_date.setDate(QDate(today))
                end = start

        days = (end - start).days + 1
        days_text = f"{days} {'день' if days == 1 else 'дні' if days in [2, 3, 4] else 'днів'}"
        self.days_label.setText(days_text)

        if hasattr(self.parent(), 'update_total_days'):
            self.parent().update_total_days()

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
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)

        # Add period button
        self.add_period_btn = QPushButton("Додати період")
        self.add_period_btn.clicked.connect(self.add_period)
        layout.addWidget(self.add_period_btn)

        # Scroll area for periods
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.periods_container = QWidget()
        self.periods_layout = QVBoxLayout(self.periods_container)
        self.periods_layout.setContentsMargins(3, 3, 3, 3)
        self.periods_layout.setSpacing(3)
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
        # Встановлюємо дату наступного дня після останнього періоду
        if len(self.periods) > 1:
            last_period = self.periods[-2]
            last_end = last_period.end_date.date().toPyDate()
            next_day = last_end + timedelta(days=1)
            # Перевіряємо, що дата не в минулому
            if next_day < date.today():
                next_day = date.today()
            period.start_date.setDate(QDate(next_day))
            period.end_date.setDate(QDate(next_day))
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
            # Перевіряємо, що дати коректні
            if end >= start:
                total += (end - start).days + 1

        if hasattr(self.parent(), 'update_total_days_label'):
            self.parent().update_total_days_label(total)

    def get_all_periods(self):
        """Get all vacation periods"""
        return [period.get_period_data() for period in self.periods]

class CreateVacationDialogEnhancedSimple(QDialog):
    """Enhanced dialog for creating new vacation requests with complex date support"""
    def __init__(self, parent=None, staff_id=None):
        super().__init__(parent)
        self.setWindowTitle("Створити заяву на відпустку (Розширений режим)")
        self.setMinimumWidth(700)
        # Initialize staff_id with default value
        self.staff_id = staff_id if staff_id is not None else 1
        print(f"Debug: CreateVacationDialogEnhancedSimple initialized with staff_id={self.staff_id}")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # Зменшити відступи
        layout.setSpacing(5)  # Зменшити відстань між елементами

        # Vacation payment type selection
        payment_group = QGroupBox("Тип відпустки")
        payment_layout = QVBoxLayout()
        payment_layout.setContentsMargins(5, 5, 5, 5)  # Зменшити відступи в групі

        self.payment_type_group = QButtonGroup()
        self.paid_radio = QRadioButton("За збереженням зарплати")
        self.unpaid_radio = QRadioButton("За власний рахунок")
        self.payment_type_group.addButton(self.paid_radio, 0)
        self.payment_type_group.addButton(self.unpaid_radio, 1)
        self.paid_radio.setChecked(True)

        payment_layout.addWidget(self.paid_radio)
        payment_layout.addWidget(self.unpaid_radio)
        payment_group.setLayout(payment_layout)
        layout.addWidget(payment_group)

        # Tab widget for different input methods
        self.tab_widget = QTabWidget()
        self.tab_widget.setContentsMargins(0, 0, 0, 0)

        # Continuous period tab
        self.continuous_tab = QWidget()
        continuous_layout = QVBoxLayout()
        continuous_layout.setContentsMargins(5, 5, 5, 5)
        continuous_layout.setSpacing(5)

        # Checkbox for one day
        self.cont_one_day_checkbox = QCheckBox("Один день")
        self.cont_one_day_checkbox.setChecked(False)
        continuous_layout.addWidget(self.cont_one_day_checkbox)

        continuous_dates = QHBoxLayout()
        self.cont_from_label = QLabel("З:")
        continuous_dates.addWidget(self.cont_from_label)
        self.cont_start_date = QDateEdit()
        self.cont_start_date.setCalendarPopup(True)
        self.cont_start_date.setDate(QDate.currentDate())
        self.cont_start_date.setMinimumDate(QDate.currentDate())  # Не можна вибрати дату в минулому
        continuous_dates.addWidget(self.cont_start_date)

        self.cont_to_label = QLabel("По:")
        continuous_dates.addWidget(self.cont_to_label)
        self.cont_end_date = QDateEdit()
        self.cont_end_date.setCalendarPopup(True)
        self.cont_end_date.setDate(QDate.currentDate().addDays(14))
        self.cont_end_date.setMinimumDate(QDate.currentDate())  # Не можна вибрати дату в минулому
        continuous_dates.addWidget(self.cont_end_date)

        continuous_layout.addLayout(continuous_dates)
        self.cont_days_label = QLabel("Загальна кількість днів: 15")
        continuous_layout.addWidget(self.cont_days_label)
        self.continuous_tab.setLayout(continuous_layout)

        # Split periods tab
        self.split_tab = QWidget()
        split_layout = QVBoxLayout()
        split_layout.setContentsMargins(5, 5, 5, 5)
        split_layout.setSpacing(5)
        self.periods_list = VacationPeriodsList(self.split_tab)
        split_layout.addWidget(self.periods_list)
        self.split_tab.setLayout(split_layout)

        # Custom description tab
        self.custom_tab = QWidget()
        custom_layout = QVBoxLayout()
        custom_layout.setContentsMargins(5, 5, 5, 5)
        custom_layout.setSpacing(5)
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
        self.cont_one_day_checkbox.toggled.connect(self.on_cont_one_day_toggled)
        self.cont_start_date.dateChanged.connect(self.on_cont_start_date_changed)
        self.cont_end_date.dateChanged.connect(self.update_continuous_days)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.custom_days_spin.valueChanged.connect(self.update_total_days_label)

        # staff_id should already be set in constructor, no need to override
        print(f"Debug: Final staff_id in setup_ui: {self.staff_id}")

    def on_cont_one_day_toggled(self, checked):
        """Handle one day checkbox toggle for continuous period"""
        # Показуємо або приховуємо елементи для вибору дати "По"
        self.cont_to_label.setVisible(not checked)
        self.cont_end_date.setVisible(not checked)

        if checked:
            # Якщо вибрано один день, встановлюємо кінцеву дату = початковій
            self.cont_end_date.setDate(self.cont_start_date.date())

        self.update_continuous_days()

    def on_cont_start_date_changed(self, date):
        """Handle start date change for continuous period"""
        # Перевіряємо, що кінцева дата не менша за нову початкову
        if self.cont_end_date.date() < date:
            self.cont_end_date.setDate(date)
        self.update_continuous_days()

    def on_tab_changed(self, index):
        """Handle tab change"""
        self.update_total_days_label()

    def update_continuous_days(self):
        """Update days count for continuous period"""
        start = self.cont_start_date.date().toPyDate()
        end = self.cont_end_date.date().toPyDate()

        # Перевіряємо, що кінцева дата не менша за початкову
        if end < start:
            # Автоматично виправляємо дату
            self.cont_end_date.setDate(self.cont_start_date.date())
            end = start

        # Перевіряємо, що дати не в минулому
        today = date.today()
        if start < today:
            # Встановлюємо початкову дату на сьогодні
            self.cont_start_date.setDate(QDate(today))
            start = today
            if end < start:
                self.cont_end_date.setDate(QDate(today))
                end = start

        days = (end - start).days + 1
        self.cont_days_label.setText(f"Загальна кількість днів: {days}")
        if self.tab_widget.currentIndex() == 0:  # First tab is continuous
            self.update_total_days_label(days)

    def update_total_days_label(self, days=None):
        """Update total days label"""
        if days is None:
            current_tab = self.tab_widget.currentIndex()
            if current_tab == 0:  # Continuous period
                start = self.cont_start_date.date().toPyDate()
                end = self.cont_end_date.date().toPyDate()
                days = (end - start).days + 1
            elif current_tab == 1:  # Split periods
                total = 0
                for period in self.periods_list.periods:
                    start = period.start_date.date().toPyDate()
                    end = period.end_date.date().toPyDate()
                    total += (end - start).days + 1
                days = total
            elif current_tab == 2:  # Custom
                days = self.custom_days_spin.value()

        self.total_days_label.setText(f"Всього днів відпустки: {days}")

    def get_data(self):
        """Get form data"""
        # Determine vacation periods based on current tab
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # Continuous period
            periods = [{
                'start_date': self.cont_start_date.date().toPyDate(),
                'end_date': self.cont_end_date.date().toPyDate()
            }]
            description = f"з {self.cont_start_date.date().toString('dd.MM.yyyy')} по {self.cont_end_date.date().toString('dd.MM.yyyy')}"
            vacation_type = 'continuous'
        elif current_tab == 1:  # Split periods
            periods = self.periods_list.get_all_periods()
            descriptions = []
            for period in periods:
                descriptions.append(
                    f"з {period['start_date'].strftime('%d.%m.%Y')} по {period['end_date'].strftime('%d.%m.%Y')}"
                )
            description = ", ".join(descriptions)
            vacation_type = 'split'
        else:  # custom (tab 2)
            periods = []
            description = self.custom_description.toPlainText().strip()
            vacation_type = 'custom'

        # Calculate total days
        if periods:
            total_days = sum((p['end_date'] - p['start_date']).days + 1 for p in periods)
        else:
            total_days = self.custom_days_spin.value()

        # Ensure staff_id is not None
        staff_id = self.staff_id if self.staff_id is not None else 1

        data = {
            'staff_id': staff_id,
            'periods': periods,
            'total_days': total_days,
            'description': description,
            'vacation_type': vacation_type,
            'vacation_payment_type': 'paid' if self.paid_radio.isChecked() else 'unpaid'
        }
        return data