"""Вкладка налаштувань системи."""

import json
from typing import Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QTextEdit,
    QPushButton,
    QLabel,
    QGroupBox,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QCheckBox,
)
from PyQt6.QtCore import Qt

from backend.models.settings import SystemSettings, Approvers
from backend.models.staff import Staff
from backend.core.database import get_db_context


class SettingsDialog(QDialog):
    """
    Діалог налаштувань системи.

    Дозволяє налаштовувати:
    - Управління установою (ректор, назва)
    - Налаштування підрозділу (кафедра, завідувач)
    - Матрицю підписантів
    - Глобальні параметри форматування
    """

    def __init__(self, parent=None):
        """Ініціалізує діалог налаштувань."""
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("⚙️ Налаштування системи - VacationManager")
        self.setMinimumSize(900, 650)

        layout = QVBoxLayout(self)

        # Tab widget для розділів налаштувань
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Вкладка "Установа"
        institution_tab = self._create_institution_tab()
        self.tabs.addTab(institution_tab, "🏛 Установа")

        # Вкладка "Підрозділ"
        department_tab = self._create_department_tab()
        self.tabs.addTab(department_tab, "🏢 Підрозділ")

        # Вкладка "Погоджувачі"
        approvers_tab = self._create_approvers_tab()
        self.tabs.addTab(approvers_tab, "✍️ Погоджувачі")

        # Вкладка "Форматування"
        formatting_tab = self._create_formatting_tab()
        self.tabs.addTab(formatting_tab, "📐 Форматування")

        # Кнопки збереження
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("💾 Зберегти")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрити")
        buttons.accepted.connect(self._save_all_settings)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)

    def set_tab(self, tab: str):
        """
        Встановлює активну вкладку.

        Args:
            tab: Ідентифікатор вкладки ("institution", "department", "approvers", "formatting")
        """
        tab_map = {
            "institution": 0,
            "department": 1,
            "approvers": 2,
            "formatting": 3,
        }
        if tab in tab_map:
            self.tabs.setCurrentIndex(tab_map[tab])

    def _create_institution_tab(self) -> QWidget:
        """Створює вкладку налаштувань установи."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Група "Ректор"
        rector_group = QGroupBox("👔 Ректор університету")
        rector_layout = QFormLayout()

        self.rector_name_input = QLineEdit()
        self.rector_name_input.setPlaceholderText(
            "ПІБ ректора у давальному відмінку\n"
            "Наприклад: Ганні ОЛІЙНИК"
        )
        rector_layout.addRow("ПІБ (давальний відмінок):", self.rector_name_input)

        self.rector_title_input = QLineEdit()
        self.rector_title_input.setPlaceholderText(
            "Науковий ступінь та вчене звання\n"
            "Наприклад: д.е.н., проф."
        )
        rector_layout.addRow("Ступінь та звання:", self.rector_title_input)

        self.rector_name_nom_input = QLineEdit()
        self.rector_name_input.setPlaceholderText(
            "ПІБ ректура у називному відмінку\n"
            "Наприклад: Ганна ОЛІЙНИК"
        )
        rector_layout.addRow("ПІБ (називний відмінок):", self.rector_name_nom_input)

        rector_group.setLayout(rector_layout)
        layout.addWidget(rector_group)

        # Група "Університет"
        university_group = QGroupBox("🎓 Університет")
        university_layout = QFormLayout()

        self.university_name_input = QLineEdit()
        self.university_name_input.setPlaceholderText(
            "Повна назва університету\n"
            "Наприклад: Полтавський державний аграрний університет"
        )
        university_layout.addRow("Назва:", self.university_name_input)

        university_group.setLayout(university_layout)
        layout.addWidget(university_group)

        # Підказка
        help_label = QLabel(
            "💡 Ці дані використовуються для автоматичного заповнення "
            "шапки документів (заяв, наказів тощо)."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(help_label)

        layout.addStretch()
        return widget

    def _create_department_tab(self) -> QWidget:
        """Створює вкладку налаштувань підрозділу."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Група "Кафедра/Підрозділ"
        dept_group = QGroupBox("🏢 Кафедра / Підрозділ")
        dept_layout = QFormLayout()

        self.dept_name_input = QLineEdit()
        self.dept_name_input.setPlaceholderText(
            "Офіційна назва кафедри або підрозділу\n"
            "Наприклад: кафедри менеджменту, маркетингу та логістики"
        )
        dept_layout.addRow("Назва:", self.dept_name_input)

        dept_group.setLayout(dept_layout)
        layout.addWidget(dept_group)

        # Група "Завідувач кафедри"
        head_group = QGroupBox("👤 Завідувач кафедри")
        head_layout = QFormLayout()

        self.dept_head_input = QComboBox()
        self.dept_head_input.setEditable(True)
        head_layout.addRow("Завідувач:", self.dept_head_input)

        self.dept_head_is_acting_cb = QCheckBox(
            "Виконуючий обов'язки завідувача (в.о.)"
        )
        head_layout.addRow("", self.dept_head_is_acting_cb)

        head_group.setLayout(head_layout)
        layout.addWidget(head_group)

        # Група "Секретар"
        secretary_group = QGroupBox("📋 Секретар кафедри")
        secretary_layout = QFormLayout()

        self.dept_secretary_input = QComboBox()
        self.dept_secretary_input.setEditable(True)
        secretary_layout.addRow("Секретар:", self.dept_secretary_input)

        secretary_group.setLayout(secretary_layout)
        layout.addWidget(secretary_group)

        # Підказка
        help_label = QLabel(
            "💡 Завідувач кафедри та секретар обираються зі списку співробітників. "
            "Можна ввести ПІБ вручну, якщо співробітника немає в базі."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(help_label)

        layout.addStretch()
        return widget

    def _create_approvers_tab(self) -> QWidget:
        """Створює вкладку матриці підписантів."""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Ліва панель - список
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        left_layout.addWidget(QLabel("📜 Список погоджувачів:"))

        self.approvers_list = QListWidget()
        self.approvers_list.itemDoubleClicked.connect(self._edit_approver)
        left_layout.addWidget(self.approvers_list)

        # Кнопки
        buttons_layout = QHBoxLayout()

        add_btn = QPushButton("➕ Додати")
        add_btn.clicked.connect(self._add_approver)
        buttons_layout.addWidget(add_btn)

        edit_btn = QPushButton("✏️ Редагувати")
        edit_btn.clicked.connect(self._edit_approver)
        buttons_layout.addWidget(edit_btn)

        remove_btn = QPushButton("🗑 Видалити")
        remove_btn.clicked.connect(self._remove_approver)
        buttons_layout.addWidget(remove_btn)

        left_layout.addLayout(buttons_layout)

        layout.addWidget(left_panel, 1)

        # Права панель - опис
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        right_layout.addWidget(QLabel("📖 Інструкція:"))

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setHtml("""
        <h3>Матриця підписантів</h3>
        <p>Матриця підписантів дозволяє визначити порядок погодження документів.</p>

        <h4>Як працює:</h4>
        <ul>
            <li>Кожен погоджувач має <b>посаду</b> та <b>ПІБ</b> у давальному відмінку</li>
            <li>Порядок визначається полем <b>Порядок</b> (менше число = вище в документі)</li>
            <li>Погоджувачі відображаються в футері заяви у визначеному порядку</li>
        </ul>

        <h4>Приклади використання:</h4>
        <ul>
            <li><b>Директор ННІ</b> - директор Науково-навчального інституту</li>
            <li><b>Начальник департаменту</b> - керівник структурного підрозділу</li>
            <li><b>Голова Бюджетної комісії</b> - для погодження фінансових документів</li>
        </ul>

        <h4>Вимоги до оформлення:</h4>
        <ul>
            <li>ПІБ вказується у <b>давальному відмінку</b> (кому? 给кому?)</li>
            <li>Наприклад: <i>директору ННІ Іванову І.І.</i></li>
        </ul>
        """)
        right_layout.addWidget(info_text)

        layout.addWidget(right_panel, 1)

        return widget

    def _create_formatting_tab(self) -> QWidget:
        """Створює вкладку налаштувань форматування."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Група "Порядок виводу ПІБ"
        name_order_group = QGroupBox("👤 Порядок виводу ПІБ у підписі")
        name_order_layout = QFormLayout()

        self.name_order_input = QComboBox()
        self.name_order_input.addItems([
            "Ім'я Прізвище",
            "Прізвище Ім'я",
        ])
        name_order_layout.addRow("Формат:", self.name_order_input)

        name_order_group.setLayout(name_order_layout)
        layout.addWidget(name_order_group)

        # Група "Попередження"
        warnings_group = QGroupBox("⚠️ Попередження про завершення контракту")
        warnings_layout = QFormLayout()

        self.contract_warning_days_input = QSpinBox()
        self.contract_warning_days_input.setRange(1, 365)
        self.contract_warning_days_input.setValue(30)
        self.contract_warning_days_input.setSuffix(" днів")
        warnings_layout.addRow("Попереджати за:", self.contract_warning_days_input)

        warnings_group.setLayout(warnings_layout)
        layout.addWidget(warnings_group)

        # Група "Бібліотека причин"
        reasons_group = QGroupBox("📚 Типові причини для неоплачуваної відпустки")
        reasons_layout = QVBoxLayout()

        self.unpaid_reasons_input = QTextEdit()
        self.unpaid_reasons_input.setPlaceholderText(
            "Введіть типові причини, кожну з нового рядка:\n\n"
            "Приклади:\n"
            "- сімейні обставини\n"
            "- догляд за хворим родичем\n"
            "- навчальні цілі\n"
            "- інші поважні причини"
        )
        self.unpaid_reasons_input.setMaximumHeight(150)
        reasons_layout.addWidget(self.unpaid_reasons_input)

        reasons_group.setLayout(reasons_layout)
        layout.addWidget(reasons_group)

        # Підказка
        help_label = QLabel(
            "💡 Типові причини будуть доступні для вибору при створенні "
            "заяви на неоплачувану відпустку."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(help_label)

        layout.addStretch()
        return widget

    def _load_settings(self):
        """Завантажує налаштування з бази даних."""
        with get_db_context() as db:
            # Установа
            self.rector_name_input.setText(
                SystemSettings.get_value(db, "rector_name_dative", "")
            )
            self.rector_title_input.setText(
                SystemSettings.get_value(db, "rector_title", "")
            )
            self.rector_name_nom_input.setText(
                SystemSettings.get_value(db, "rector_name_nominative", "")
            )
            self.university_name_input.setText(
                SystemSettings.get_value(db, "university_name", "")
            )

            # Підрозділ
            self.dept_name_input.setText(
                SystemSettings.get_value(db, "dept_name", "")
            )

            # Завантажуємо список співробітників для випадаючих списків
            self._load_staff_for_combos(db)

            # Встановлюємо завідувача
            dept_head_id = SystemSettings.get_value(db, "dept_head_id", None)
            if dept_head_id:
                index = self.dept_head_input.findData(dept_head_id)
                if index >= 0:
                    self.dept_head_input.setCurrentIndex(index)

            # Встановлюємо секретаря
            secretary_id = SystemSettings.get_value(db, "dept_secretary_id", None)
            if secretary_id:
                index = self.dept_secretary_input.findData(secretary_id)
                if index >= 0:
                    self.dept_secretary_input.setCurrentIndex(index)

            # В.о. завідувача
            is_acting = SystemSettings.get_value(db, "dept_head_is_acting", False)
            self.dept_head_is_acting_cb.setChecked(is_acting)

            # Погогоджувачі
            self._load_approvers(db)

            # Форматування
            name_order = SystemSettings.get_value(db, "name_order", "first_last")
            index = 0 if name_order == "first_last" else 1
            self.name_order_input.setCurrentIndex(index)

            self.contract_warning_days_input.setValue(
                SystemSettings.get_value(db, "contract_warning_days", 30)
            )

            unpaid_reasons = SystemSettings.get_value(db, "unpaid_vacation_reasons", [])
            if unpaid_reasons:
                self.unpaid_reasons_input.setPlainText("\n".join(unpaid_reasons))

    def _load_staff_for_combos(self, db):
        """Завантажує співробітників у випадаючі списки."""
        staff_list = (
            db.query(Staff)
            .filter(Staff.is_active == True)
            .order_by(Staff.pib_nom)
            .all()
        )

        # Зберігаємо поточні значення
        current_head = self.dept_head_input.currentText()
        current_secretary = self.dept_secretary_input.currentText()

        # Очищаємо та заповнюємо
        self.dept_head_input.clear()
        self.dept_secretary_input.clear()

        for staff in staff_list:
            # Додаємо з ID як data
            self.dept_head_input.addItem(staff.pib_nom, staff.id)
            self.dept_secretary_input.addItem(staff.pib_nom, staff.id)

        # Відновлюємо значення, якщо є
        if current_head:
            index = self.dept_head_input.findText(current_head)
            if index >= 0:
                self.dept_head_input.setCurrentIndex(index)

        if current_secretary:
            index = self.dept_secretary_input.findText(current_secretary)
            if index >= 0:
                self.dept_secretary_input.setCurrentIndex(index)

    def _load_approvers(self, db):
        """Завантажує список погоджувачів."""
        self.approvers_list.clear()

        approvers = (
            db.query(Approvers)
            .order_by(Approvers.order_index)
            .all()
        )

        for approver in approvers:
            item = QListWidgetItem(
                f"{approver.order_index + 1}. {approver.position_name} - {approver.full_name_dav}"
            )
            item.setData(Qt.ItemDataRole.UserRole, approver.id)
            self.approvers_list.addItem(item)

    def _add_approver(self):
        """Додає нового погоджувача."""
        dialog = ApproverDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            with get_db_context() as db:
                approver = Approvers(
                    position_name=dialog.position_input.text(),
                    full_name_dav=dialog.name_input.text(),
                    order_index=dialog.order_input.value(),
                )
                db.add(approver)
                db.commit()

                self._load_approvers(db)

    def _edit_approver(self):
        """Редагує погоджувача."""
        current_item = self.approvers_list.currentItem()
        if not current_item:
            return

        approver_id = current_item.data(Qt.ItemDataRole.UserRole)

        with get_db_context() as db:
            approver = db.query(Approvers).filter(Approvers.id == approver_id).first()
            if not approver:
                return

            dialog = ApproverDialog(self, approver)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                approver.position_name = dialog.position_input.text()
                approver.full_name_dav = dialog.name_input.text()
                approver.order_index = dialog.order_input.value()
                db.commit()

                self._load_approvers(db)

    def _remove_approver(self):
        """Видаляє погоджувача."""
        current_item = self.approvers_list.currentItem()
        if not current_item:
            return

        reply = QMessageBox.question(
            self,
            "Підтвердження видалення",
            "Видалити цього погоджувача?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            approver_id = current_item.data(Qt.ItemDataRole.UserRole)

            with get_db_context() as db:
                approver = db.query(Approvers).filter(Approvers.id == approver_id).first()
                if approver:
                    db.delete(approver)
                    db.commit()

                    self._load_approvers(db)

    def _save_all_settings(self):
        """Зберігає всі налаштування."""
        with get_db_context() as db:
            # Установа
            SystemSettings.set_value(
                db, "rector_name_dative",
                self.rector_name_input.text().strip()
            )
            SystemSettings.set_value(
                db, "rector_title",
                self.rector_title_input.text().strip()
            )
            SystemSettings.set_value(
                db, "rector_name_nominative",
                self.rector_name_nom_input.text().strip()
            )
            SystemSettings.set_value(
                db, "university_name",
                self.university_name_input.text().strip()
            )

            # Підрозділ
            SystemSettings.set_value(
                db, "dept_name",
                self.dept_name_input.text().strip()
            )

            dept_head_id = self.dept_head_input.currentData()
            SystemSettings.set_value(db, "dept_head_id", dept_head_id)

            secretary_id = self.dept_secretary_input.currentData()
            SystemSettings.set_value(db, "dept_secretary_id", secretary_id)

            SystemSettings.set_value(
                db, "dept_head_is_acting",
                self.dept_head_is_acting_cb.isChecked()
            )

            # Форматування
            name_order = "first_last" if self.name_order_input.currentIndex() == 0 else "last_first"
            SystemSettings.set_value(db, "name_order", name_order)

            SystemSettings.set_value(
                db, "contract_warning_days",
                self.contract_warning_days_input.value()
            )

            unpaid_reasons = [
                line.strip()
                for line in self.unpaid_reasons_input.toPlainText().split("\n")
                if line.strip()
            ]
            SystemSettings.set_value(db, "unpaid_vacation_reasons", unpaid_reasons)

        # Показуємо повідомлення і закриваємо діалог
        QMessageBox.information(
            self,
            "Успішно",
            "Налаштування збережено!"
        )
        self.accept()


class ApproverDialog(QDialog):
    """Діалог для додавання/редагування погоджувача."""

    def __init__(self, parent, approver=None):
        """
        Ініціалізує діалог.

        Args:
            parent: Батьківський віджет
            approver: Об'єкт Approvers для редагування (опціонально)
        """
        super().__init__(parent)
        self.approver = approver
        self._setup_ui()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle(
            "Редагування погоджувача" if self.approver else "Новий погоджувач"
        )
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Форма
        form_layout = QFormLayout()

        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("Наприклад: директора ННІ")
        form_layout.addRow("Посада (називний):", self.position_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            "ПІБ у давальному відмінку\nНаприклад: Іванову І.І."
        )
        form_layout.addRow("ПІБ (давальний):", self.name_input)

        self.order_input = QSpinBox()
        self.order_input.setRange(0, 100)
        self.order_input.setValue(0)
        form_layout.addRow("Порядок:", self.order_input)

        layout.addLayout(form_layout)

        # Підказка
        help_label = QLabel(
            "💵 <b>Давальний відмінок</b> відповідає на питання \"кому?\"\n"
            "Наприклад: директору <b>Іванову Івану Івановичу</b>"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(help_label)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Заповнюємо якщо редагування
        if self.approver:
            self.position_input.setText(self.approver.position_name)
            self.name_input.setText(self.approver.full_name_dav)
            self.order_input.setValue(self.approver.order_index)
