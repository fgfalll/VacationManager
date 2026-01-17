
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
    QLabel,
    QToolTip,
    QMessageBox
)

from backend.core.database import get_db_context

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

    def __init__(self, config: Optional[DatePickerConfig] = None, staff_id: int = None, parent=None):
        super().__init__(parent)
        self.config = config or DatePickerConfig()
        self.staff_id = staff_id

        # Ranges
        self._start_date: Optional[QDate] = None
        self._end_date: Optional[QDate] = None

        # Locked dates (from documents and attendance)
        self._locked_dates: set[QDate] = set()
        self._locked_ranges: list[tuple[QDate, QDate]] = []

        # Locked date format (saved for restoration)
        self._fmt_locked = None

        self.setWindowTitle("Оберіть період")
        if parent:
            self.setWindowFlags(Qt.WindowType.Dialog)

        self._setup_ui()
        self._apply_config()

        if self.staff_id:
            self._load_locked_dates()
            self._highlight_locked_dates()

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

        # Connect internal signals
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

    def _load_locked_dates(self):
        """Load already occupied dates from database."""
        if not self.staff_id:
            return

        from backend.models.document import Document
        from backend.models.attendance import Attendance

        with get_db_context() as db:
            # Load vacation documents
            docs = db.query(Document).filter(Document.staff_id == self.staff_id).all()
            for doc in docs:
                d = QDate(doc.date_start)
                end = QDate(doc.date_end or doc.date_start)
                self._locked_ranges.append((d, end))
                while d <= end:
                    self._locked_dates.add(QDate(d))
                    d = d.addDays(1)

            # Load attendance records (except "Р" - work)
            atts = db.query(Attendance).filter(
                Attendance.staff_id == self.staff_id,
                Attendance.code != "Р"
            ).all()
            for att in atts:
                d = QDate(att.date)
                end = QDate(att.date_end or att.date)
                self._locked_ranges.append((d, end))
                while d <= end:
                    self._locked_dates.add(QDate(d))
                    d = d.addDays(1)

    def _highlight_locked_dates(self):
        """Highlight dates that are already occupied."""
        self._fmt_locked = QTextCharFormat()
        self._fmt_locked.setBackground(QBrush(QColor("#FFE0E0")))
        self._fmt_locked.setForeground(QBrush(QColor("#CC0000")))

        for locked_date in self._locked_dates:
            self.calendar.setDateTextFormat(locked_date, self._fmt_locked)

    def _on_calendar_clicked(self, date: QDate):
        # Check if date is locked - prevent selection
        if date in self._locked_dates:
            QMessageBox.warning(
                self,
                "Заблокована дата",
                f"Дата {date.toString('dd.MM.yyyy')} вже зайнята!\n\n"
                f"Оберіть іншу дату."
            )
            return  # Don't allow selection of locked dates

        # Show warning if clicking near locked dates
        has_locked_nearby = False
        for locked in self._locked_dates:
            if abs(locked.daysTo(date)) <= 1:
                has_locked_nearby = True
                break

        if has_locked_nearby:
            self.info_label.setText(f"Увага! Поруч є зайняті дати!")
            self.info_label.setStyleSheet("font-weight: bold; color: #FF6600;")
        else:
            self.info_label.setStyleSheet("font-weight: bold; color: #555;")

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
                # Check if any dates in range are locked
                locked_in_range = []
                current = self._start_date
                while current <= date:
                    if current in self._locked_dates:
                        locked_in_range.append(current)
                    current = current.addDays(1)

                if locked_in_range:
                    # Show which dates are locked
                    dates_str = ", ".join([d.toString('dd.MM') for d in locked_in_range])
                    QMessageBox.warning(
                        self,
                        "Заблоковані дати в періоді",
                        f"Обраний період містить {len(locked_in_range)} заблоковану(их) дату(и):\n\n"
                        f"{dates_str}\n\n"
                        f"Оберіть інший період."
                    )
                    # Reset selection
                    self._start_date = None
                    self._end_date = None
                    self._confirm_button.setEnabled(False)
                    self.info_label.setText("Оберіть дату початку")
                    self._highlight_range()
                    return

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
        # First, restore locked date formatting
        if self._fmt_locked:
            for locked_date in self._locked_dates:
                self.calendar.setDateTextFormat(locked_date, self._fmt_locked)

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
                # Double-check for locked dates in range
                locked_in_range = []
                current = self._start_date
                while current <= self._end_date:
                    if current in self._locked_dates:
                        locked_in_range.append(current)
                    current = current.addDays(1)

                if locked_in_range:
                    QMessageBox.warning(
                        self,
                        "Помилка",
                        "Обраний період містить заблоковані дати!"
                    )
                    return

                rng = DateRange(self._start_date, self._end_date)
                self.range_selected.emit(rng)

    def _on_cancel_internal(self):
        self.cancelled.emit()
