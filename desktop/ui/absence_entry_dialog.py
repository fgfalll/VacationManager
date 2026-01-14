"""Діалог для додавання/редагування запису відсутності."""

from datetime import date
from decimal import Decimal
from typing import Optional

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from shared.absence_types import ABSENCE_TYPE_GROUPS, CODES_REQUIRING_HOURS


class AbsenceEntryDialog(QDialog):
    """
    Діалог для додавання або редагування запису відсутності.

    Атрибути:
        staff_id: ID працівника
        staff_name: ПІБ працівника для відображення
        edit_data: Дані для редагування (None для нового запису)
    """

    def __init__(
        self,
        staff_id: int,
        staff_name: str,
        parent=None,
        edit_data: Optional[dict] = None,
    ):
        """
        Ініціалізує діалог.

        Args:
            staff_id: ID працівника
            staff_name: ПІБ працівника
            parent: Батьківський віджет
            edit_data: Дані для редагування (None для нового запису)
        """
        super().__init__(parent)
        self.staff_id = staff_id
        self.staff_name = staff_name
        self.edit_data = edit_data
        self._setup_ui()
        self._connect_signals()

        if edit_data:
            self._load_edit_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        is_edit = self.edit_data is not None
        title = "Редагування відмітки" if is_edit else "Нова відмітка"
        self.setWindowTitle(f"{title}: {self.staff_name}")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Форма для введення даних
        form = QFormLayout()

        # Тип відсутності
        self.type_combo = QComboBox()
        self.type_combo.addItems(sorted(ABSENCE_TYPE_GROUPS.keys()))
        form.addRow("Тип відмітки:", self.type_combo)

        # Вибір режиму дати: одна дата або період
        date_mode_widget = QWidget()
        date_mode_layout = QHBoxLayout(date_mode_widget)
        date_mode_layout.setContentsMargins(0, 0, 0, 0)

        self.single_date_radio = QRadioButton("Одна дата")
        self.range_date_radio = QRadioButton("Період")
        self.single_date_radio.setChecked(True)

        self.date_mode_group = QButtonGroup(self)
        self.date_mode_group.addButton(self.single_date_radio, 0)
        self.date_mode_group.addButton(self.range_date_radio, 1)

        date_mode_layout.addWidget(self.single_date_radio)
        date_mode_layout.addWidget(self.range_date_radio)
        date_mode_layout.addStretch()

        form.addRow("Режим:", date_mode_widget)

        # Віджет для однієї дати
        self.single_date_widget = QWidget()
        single_date_layout = QHBoxLayout(self.single_date_widget)
        single_date_layout.setContentsMargins(0, 0, 0, 0)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        single_date_layout.addWidget(self.date_edit)
        single_date_layout.addStretch()

        form.addRow("Дата:", self.single_date_widget)

        # Віджет для періоду
        self.range_date_widget = QWidget()
        range_date_layout = QHBoxLayout(self.range_date_widget)
        range_date_layout.setContentsMargins(0, 0, 0, 0)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy")

        range_date_layout.addWidget(self.start_date_edit)
        range_date_layout.addWidget(QLabel("—"))
        range_date_layout.addWidget(self.end_date_edit)
        range_date_layout.addStretch()

        self.range_date_widget.hide()  # Прихований за замовчуванням
        form.addRow("Період:", self.range_date_widget)

        # Години (для надурочних тощо)
        self.hours_widget = QWidget()
        hours_layout = QHBoxLayout(self.hours_widget)
        hours_layout.setContentsMargins(0, 0, 0, 0)

        self.hours_spin = QDoubleSpinBox()
        self.hours_spin.setRange(0.5, 24.0)
        self.hours_spin.setSingleStep(0.5)
        self.hours_spin.setDecimals(1)
        self.hours_spin.setValue(8.0)
        self.hours_spin.setSuffix(" год.")

        hours_layout.addWidget(self.hours_spin)
        hours_layout.addStretch()

        self.hours_widget.hide()  # Прихований за замовчуванням
        form.addRow("Години:", self.hours_widget)

        # Примітки
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Додаткова інформація (необов'язково)")
        form.addRow("Примітки:", self.notes_edit)

        layout.addLayout(form)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Зберегти")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Скасувати")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _connect_signals(self):
        """Підключає сигнали."""
        # Перемикання режиму дати
        self.date_mode_group.buttonClicked.connect(self._on_date_mode_changed)

        # Перевірка чи потрібно показувати години
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        # Оновлюємо видимість годин при старті
        self._on_type_changed(self.type_combo.currentText())

    def _on_date_mode_changed(self):
        """Обробляє зміну режиму дати."""
        is_range = self.range_date_radio.isChecked()
        self.single_date_widget.setVisible(not is_range)
        self.range_date_widget.setVisible(is_range)

    def _on_type_changed(self, type_name: str):
        """Обробляє зміну типу відмітки."""
        code = ABSENCE_TYPE_GROUPS.get(type_name, "")
        show_hours = code in CODES_REQUIRING_HOURS
        self.hours_widget.setVisible(show_hours)

    def _load_edit_data(self):
        """Завантажує дані для редагування."""
        if not self.edit_data:
            return

        # Встановлюємо тип
        code = self.edit_data.get("code", "")
        # Знаходимо назву типу за кодом
        from shared.absence_types import CODE_TO_ABSENCE_NAME
        type_name = CODE_TO_ABSENCE_NAME.get(code, "")
        if type_name:
            index = self.type_combo.findText(type_name)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

        # Встановлюємо дату
        attendance_date = self.edit_data.get("date")
        if attendance_date:
            qdate = QDate(attendance_date.year, attendance_date.month, attendance_date.day)
            self.date_edit.setDate(qdate)

        # Встановлюємо години
        hours = self.edit_data.get("hours", Decimal("8.0"))
        self.hours_spin.setValue(float(hours))

        # Встановлюємо примітки
        notes = self.edit_data.get("notes", "")
        if notes:
            self.notes_edit.setText(notes)

    def get_result(self) -> dict:
        """
        Повертає результат введення.

        Returns:
            dict: Словник з даними:
                - type_name: Назва типу відмітки
                - code: Код відмітки
                - is_range: Чи введено період
                - date: Дата (для одиночної дати)
                - start_date: Початкова дата (для періоду)
                - end_date: Кінцева дата (для періоду)
                - hours: Кількість годин
                - notes: Примітки
        """
        type_name = self.type_combo.currentText()
        code = ABSENCE_TYPE_GROUPS.get(type_name, "")
        is_range = self.range_date_radio.isChecked()

        result = {
            "type_name": type_name,
            "code": code,
            "is_range": is_range,
            "hours": Decimal(str(self.hours_spin.value())),
            "notes": self.notes_edit.text().strip() or None,
        }

        if is_range:
            start_qdate = self.start_date_edit.date()
            end_qdate = self.end_date_edit.date()
            result["start_date"] = date(
                start_qdate.year(), start_qdate.month(), start_qdate.day()
            )
            result["end_date"] = date(
                end_qdate.year(), end_qdate.month(), end_qdate.day()
            )
        else:
            qdate = self.date_edit.date()
            result["date"] = date(qdate.year(), qdate.month(), qdate.day())

        return result
