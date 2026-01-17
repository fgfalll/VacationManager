
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QCalendarWidget,
    QDialog,
    QLabel
)

class PickerMode(Enum):
    SINGLE = auto()
    CUSTOM_RANGE = auto()

@dataclass
class DatePickerConfig:
    mode: PickerMode = PickerMode.CUSTOM_RANGE
    initial_date: Optional[QDate] = None
    min_date: Optional[QDate] = None
    max_date: Optional[QDate] = None

class DateRange:
    def __init__(self, start_date: QDate, end_date: QDate):
        self.start_date = start_date
        self.end_date = end_date

class DateRangePicker(QWidget):
    """
    Custom Date Range Picker Widget to replace the missing library.
    """
    range_selected = pyqtSignal(object)  # Emits DateRange object
    date_selected = pyqtSignal(QDate)
    cancelled = pyqtSignal()

    def __init__(self, config: Optional[DatePickerConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config or DatePickerConfig()
        
        # Ranges
        self._start_date: Optional[QDate] = None
        self._end_date: Optional[QDate] = None
        
        self.setWindowTitle("Оберіть період")
        if parent:
            self.setWindowFlags(Qt.WindowType.Dialog)
        
        self._setup_ui()
        self._apply_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info Label
        self.info_label = QLabel("Оберіть дату початку")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-weight: bold; color: #555;")
        layout.addWidget(self.info_label)

        # Calendar
        self.calendar = QCalendarWidget()
        self.calendar.clicked.connect(self._on_calendar_clicked)
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        layout.addWidget(self.calendar)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self._cancel_button = QPushButton("Скасувати")
        self._confirm_button = QPushButton("Підтвердити")
        
        # Styling
        self._confirm_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D4; 
                color: white; 
                border: none; 
                padding: 6px 12px; 
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #106EBE; }
            QPushButton:disabled { background-color: #CCCCCC; }
        """)
        self._cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #E1E1E1; 
                border: none; 
                padding: 6px 12px; 
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #D0D0D0; }
        """)

        # Connect internal signals manually if needed, but builder_tab connects to them directly 
        # (builder_tab connects to clicked signal of these buttons, so we expose them)
        
        # We also need internal handling to emit range_selected signal
        self._confirm_button.clicked.connect(self._on_confirm_internal)
        self._cancel_button.clicked.connect(self._on_cancel_internal)

        btn_layout.addWidget(self._cancel_button)
        btn_layout.addWidget(self._confirm_button)
        layout.addLayout(btn_layout)
        
        # Initial state
        self._confirm_button.setEnabled(False)

    def _apply_config(self):
        if self.config.min_date:
            self.calendar.setMinimumDate(self.config.min_date)
        if self.config.max_date:
            self.calendar.setMaximumDate(self.config.max_date)
        if self.config.initial_date:
            self.calendar.setSelectedDate(self.config.initial_date)

    def _on_calendar_clicked(self, date: QDate):
        if self.config.mode == PickerMode.SINGLE:
            self._start_date = date
            self._end_date = None
            self.date_selected.emit(date)
            self._confirm_button.setEnabled(True)
            self.info_label.setText(f"Обрано: {date.toString('dd.MM.yyyy')}")
            return

        # Range Mode logic
        if self._start_date is None:
            # First click - Start Date
            self._start_date = date
            self._end_date = None
            self._confirm_button.setEnabled(False)
            self.info_label.setText("Оберіть дату завершення")
            self._highlight_range()
        elif self._end_date is None:
            # Second click - End Date
            if date < self._start_date:
                # If clicked before start, reset launch with this as new start
                self._start_date = date
                self.info_label.setText("Оберіть дату завершення")
                self._highlight_range()
            else:
                self._end_date = date
                self._confirm_button.setEnabled(True)
                self.info_label.setText(f"Період: {self._start_date.toString('dd.MM')} - {self._end_date.toString('dd.MM.yyyy')}")
                self._highlight_range()
        else:
            # Reset
            self._start_date = date
            self._end_date = None
            self._confirm_button.setEnabled(False)
            self.info_label.setText("Оберіть дату завершення")
            self._highlight_range()

    def _highlight_range(self):
        # Clear previous formatting
        self.calendar.setDateTextFormat(QDate(), QTextCharFormat())
        
        if not self._start_date:
            return

        fmt_start = QTextCharFormat()
        fmt_start.setBackground(QBrush(QColor("#0078D4")))
        fmt_start.setForeground(QBrush(QColor("white")))
        self.calendar.setDateTextFormat(self._start_date, fmt_start)

        if self._end_date:
            fmt_end = QTextCharFormat()
            fmt_end.setBackground(QBrush(QColor("#0078D4")))
            fmt_end.setForeground(QBrush(QColor("white")))
            self.calendar.setDateTextFormat(self._end_date, fmt_end)
            
            # Highlight in between
            fmt_mid = QTextCharFormat()
            fmt_mid.setBackground(QBrush(QColor("#DEECF9")))
            
            d = self._start_date.addDays(1)
            while d < self._end_date:
                self.calendar.setDateTextFormat(d, fmt_mid)
                d = d.addDays(1)

    def _on_confirm_internal(self):
        if self.config.mode == PickerMode.CUSTOM_RANGE:
            if self._start_date and self._end_date:
                rng = DateRange(self._start_date, self._end_date)
                self.range_selected.emit(rng)
        # Note: Closing/Accepting dialog is handled by the caller or we can do it here. 
        # builder_tab.py calls close_popup in _on_confirmed callback attached to the button.
        # But we also should emit signal before that. 
        # The external code connects to button clicked directly.

    def _on_cancel_internal(self):
        self.cancelled.emit()
