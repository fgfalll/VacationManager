"""Діалог для завантаження сканованих документів."""

import os
from datetime import date
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.enums import DocumentStatus, DocumentType


class ScanUploadDialog(QDialog):
    """
    Діалог для завантаження сканованих документів, створених співробітником самостійно.

    Дозволяє ввести дані про документ та прикріпити скан без генерації нового документа.
    """

    def __init__(self, parent=None, staff_id: int = None):
        """
        Ініціалізує діалог.

        Args:
            parent: Батьківський віджет
            staff_id: ID працівника (опціонально, можна обрати потім)
        """
        super().__init__(parent)
        self.staff_id = staff_id
        self._scan_path: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("Завантаження скану документа")
        self.setMinimumWidth(450)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)

        # Форма для введення даних
        form = QFormLayout()

        # Тип документа
        self.doc_type_combo = QComboBox()
        self._populate_doc_types()
        form.addRow("Тип документа:", self.doc_type_combo)

        # Дата початку
        self.date_start_edit = QDateEdit()
        self.date_start_edit.setCalendarPopup(True)
        self.date_start_edit.setDate(QDate.currentDate())
        form.addRow("Дата початку:", self.date_start_edit)

        # Дата закінчення
        self.date_end_edit = QDateEdit()
        self.date_end_edit.setCalendarPopup(True)
        self.date_end_edit.setDate(QDate.currentDate())
        form.addRow("Дата закінчення:", self.date_end_edit)

        # Кількість днів
        self.days_count_edit = QLineEdit()
        self.days_count_edit.setPlaceholderText("Автоматично")
        form.addRow("Кількість днів:", self.days_count_edit)

        # Вибір скану
        scan_layout = QHBoxLayout()
        self.scan_path_edit = QLineEdit()
        self.scan_path_edit.setReadOnly(True)
        self.scan_path_edit.setPlaceholderText("Оберіть файл...")
        scan_layout.addWidget(self.scan_path_edit)

        self.browse_btn = QPushButton("Огляд...")
        self.browse_btn.clicked.connect(self._browse_scan)
        scan_layout.addWidget(self.browse_btn)

        form.addRow("Скан документа:", scan_layout)

        layout.addLayout(form)

        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accepted)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_doc_types(self):
        """Заповнює список типів документів."""
        doc_types = [
            # Оплачувані відпустки
            ("vacation_paid", "Відпустка оплачувана"),
            ("vacation_main", "Основна відпустка (В)"),
            ("vacation_additional", "Додаткова відпустка (Д)"),
            ("vacation_study", "Навчальна відпустка (Н)"),
            ("vacation_children", "Відпустка з дітьми (ДО)"),
            # Неоплачувані відпустки
            ("vacation_unpaid", "Відпустка без збереження"),
            ("vacation_unpaid_study", "Навч. без збереження (НБ)"),
            ("vacation_unpaid_mandatory", "Відпустка обов'язкова (ДБ)"),
            ("vacation_unpaid_agreement", "За згодою сторін (НА)"),
            ("vacation_unpaid_other", "Інша без збереження (БЗ)"),
            # Продовження контракту
            ("term_extension", "Продовження контракту"),
            ("term_extension_contract", "Продовження (контракт)"),
            ("term_extension_competition", "Продовження (конкурс)"),
            ("term_extension_pdf", "Продовження (сумісництво)"),
            ("other", "Інший документ"),
        ]

        for value, label in doc_types:
            self.doc_type_combo.addItem(label, value)

    def _browse_scan(self):
        """Відкриває діалог вибору файлу."""
        file_filter = "Документи (*.pdf *.png *.jpg *.jpeg *.tiff);;PDF (*.pdf);;Зображення (*.png *.jpg *.jpeg *.tiff);;Усі файли (*.*)"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Оберіть скан документа",
            "",
            file_filter,
        )

        if file_path:
            self._scan_path = file_path
            self.scan_path_edit.setText(file_path)

    def _on_accepted(self):
        """Обробляє натискання OK."""
        # Перевіряємо обов'язкові поля
        if not self._scan_path:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Помилка", "Оберіть файл скану документа")
            return

        self.accept()

    def get_data(self) -> dict:
        """
        Повертає введені дані.

        Returns:
            Словник з даними документа
        """
        date_start = self.date_start_edit.date().toPyDate()
        date_end = self.date_end_edit.date().toPyDate()

        days_text = self.days_count_edit.text().strip()
        if days_text:
            days_count = int(days_text)
        else:
            # Автоматичний підрахунок
            days_count = (date_end - date_start).days + 1

        doc_type_value = self.doc_type_combo.currentData()

        return {
            "staff_id": self.staff_id,
            "doc_type": doc_type_value,
            "date_start": date_start,
            "date_end": date_end,
            "days_count": days_count,
            "scan_path": self._scan_path,
        }

    @property
    def scan_path(self) -> Optional[str]:
        """Повертає шлях до скану."""
        return self._scan_path
