"""Вкладка налаштувань системи."""

import json
from typing import Any

from PyQt6.QtGui import QColor
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
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QInputDialog,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from backend.models.settings import SystemSettings, Approvers
from backend.models.staff import Staff
from backend.core.database import get_db_context
from shared.enums import StaffPosition, STAFF_POSITION_LABELS, get_position_label
from shared.constants import (
    SETTING_MARTIAL_LAW_ENABLED,
    SETTING_MARTIAL_LAW_VACATION_LIMIT,
    SETTING_VACATION_DAYS_SCIENTIFIC_PEDAGOGICAL,
    SETTING_VACATION_DAYS_PEDAGOGICAL,
    SETTING_VACATION_DAYS_ADMINISTRATIVE,
    DEFAULT_VACATION_DAYS,
    DEFAULT_MARTIAL_LAW_VACATION_LIMIT,
)


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
        self.setWindowTitle("Налаштування системи - VacationManager")
        self.setMinimumSize(900, 650)

        layout = QVBoxLayout(self)

        # Tab widget для розділів налаштувань
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Вкладка "Установа"
        institution_tab = self._create_institution_tab()
        self.tabs.addTab(institution_tab, "Установа")

        # Вкладка "Підрозділ"
        department_tab = self._create_department_tab()
        self.tabs.addTab(department_tab, "Підрозділ")

        # Вкладка "Погоджувачі"
        approvers_tab = self._create_approvers_tab()
        self.tabs.addTab(approvers_tab, "Погоджувачі")

        # Вкладка "Табель" - поєднує форматування, відпустки та табель
        tabel_tab = self._create_tabel_tab()
        self.tabs.addTab(tabel_tab, "Табель")

        # Вкладка "Debug" - для перегляду та редагування БД
        debug_tab = self._create_debug_tab()
        self.tabs.addTab(debug_tab, "Debug")

        # Вкладка "Telegram" - для налаштування Telegram бота
        telegram_tab = self._create_telegram_tab()
        self.tabs.addTab(telegram_tab, "Telegram")

        # Кнопки збереження
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Зберегти")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрити")
        buttons.accepted.connect(self._save_all_settings)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)

    def set_tab(self, tab: str):
        """
        Встановлює активну вкладку.

        Args:
            tab: Ідентифікатор вкладки ("institution", "department", "approvers", "formatting", "vacation")
        """
        tab_map = {
            "institution": 0,
            "department": 1,
            "approvers": 2,
            "formatting": 3,
            "vacation": 4,
            "tabel": 5,
            "debug": 6,
            "telegram": 7,
        }
        if tab in tab_map:
            self.tabs.setCurrentIndex(tab_map[tab])

    def _create_institution_tab(self) -> QWidget:
        """Створює вкладку налаштувань установи."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Група "Ректор"
        rector_group = QGroupBox("Ректор університету")
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
        university_group = QGroupBox("Університет")
        university_layout = QFormLayout()

        self.university_name_input = QLineEdit()
        self.university_name_input.setPlaceholderText(
            "Повна назва університету\n"
            "Наприклад: Полтавський державний аграрний університет"
        )
        university_layout.addRow("Назва (називний):", self.university_name_input)

        self.university_name_dav_input = QLineEdit()
        self.university_name_dav_input.setPlaceholderText(
            "Назва установи у давальному відмінку\n"
            "Наприклад: Полтавському державному аграрному університету"
        )
        university_layout.addRow("Назва (давальний):", self.university_name_dav_input)

        self.edrpou_code_input = QLineEdit()
        self.edrpou_code_input.setPlaceholderText(
            "Код ЄДРПОУ\n"
            "Наприклад: 00493014"
        )
        self.edrpou_code_input.setMaxLength(8)
        university_layout.addRow("Код ЄДРПОУ:", self.edrpou_code_input)

        university_group.setLayout(university_layout)
        layout.addWidget(university_group)

        # Підказка
        help_label = QLabel(
            "Ці дані використовуються для автоматичного заповнення "
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
        dept_group = QGroupBox("Кафедра / Підрозділ")
        dept_layout = QFormLayout()

        self.dept_name_input = QLineEdit()
        self.dept_name_input.setPlaceholderText(
            "Офіційна назва кафедри або підрозділу\n"
            "Наприклад: кафедри менеджменту, маркетингу та логістики"
        )
        dept_layout.addRow("Назва:", self.dept_name_input)

        self.dept_abbr_input = QLineEdit()
        self.dept_abbr_input.setPlaceholderText(
            "Скорочена назва для документів\n"
            "Наприклад: НГІТ, КММЛ"
        )
        dept_layout.addRow("Скорочення:", self.dept_abbr_input)

        dept_group.setLayout(dept_layout)
        layout.addWidget(dept_group)

        # Група "Завідувач кафедри"
        head_group = QGroupBox("Завідувач кафедри")
        head_layout = QFormLayout()

        self.dept_head_input = QComboBox()
        self.dept_head_input.setEditable(True)
        head_layout.addRow("Завідувач:", self.dept_head_input)

        head_group.setLayout(head_layout)
        layout.addWidget(head_group)

        # Група "Фахівець"
        specialist_group = QGroupBox("Фахівець кафедри")
        specialist_layout = QFormLayout()

        self.dept_specialist_input = QComboBox()
        self.dept_specialist_input.setEditable(True)
        specialist_layout.addRow("Фахівець:", self.dept_specialist_input)

        specialist_group.setLayout(specialist_layout)
        layout.addWidget(specialist_group)

        # Підказка
        help_label = QLabel(
            "Завідувач кафедри та фахівець обираються зі списку співробітників. "
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

        left_layout.addWidget(QLabel("Список погоджувачів:"))

        self.approvers_list = QListWidget()
        self.approvers_list.itemDoubleClicked.connect(self._edit_approver)
        left_layout.addWidget(self.approvers_list)

        # Кнопки
        buttons_layout = QHBoxLayout()

        add_btn = QPushButton("Додати")
        add_btn.clicked.connect(self._add_approver)
        buttons_layout.addWidget(add_btn)

        edit_btn = QPushButton("Редагувати")
        edit_btn.clicked.connect(self._edit_approver)
        buttons_layout.addWidget(edit_btn)

        remove_btn = QPushButton("Видалити")
        remove_btn.clicked.connect(self._remove_approver)
        buttons_layout.addWidget(remove_btn)

        left_layout.addLayout(buttons_layout)

        layout.addWidget(left_panel, 1)

        # Права панель - опис
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        right_layout.addWidget(QLabel("Інструкція:"))

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
        name_order_group = QGroupBox("Порядок виводу ПІБ у підписі")
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
        warnings_group = QGroupBox("Попередження про завершення контракту")
        warnings_layout = QFormLayout()

        self.contract_warning_days_input = QSpinBox()
        self.contract_warning_days_input.setRange(1, 365)
        self.contract_warning_days_input.setValue(30)
        self.contract_warning_days_input.setSuffix(" днів")
        warnings_layout.addRow("Попереджати за:", self.contract_warning_days_input)

        warnings_group.setLayout(warnings_layout)
        layout.addWidget(warnings_group)

        # Група "Бібліотека причин"
        reasons_group = QGroupBox("Типові причини для неоплачуваної відпустки")
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
            "Типові причини будуть доступні для вибору при створенні "
            "заяви на неоплачувану відпустку."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(help_label)

        layout.addStretch()
        return widget

    def _create_vacation_tab(self) -> QWidget:
        """Створює вкладку налаштувань відпусток та воєнного стану."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Група "Воєнний стан"
        martial_group = QGroupBox("Воєнний стан")
        martial_layout = QVBoxLayout()

        self.martial_law_checkbox = QCheckBox(
            "Увімкнути режим воєнного стану\n"
            "(всі дні рахуються як відпускні, включаючи вихідні та свята)"
        )
        self.martial_law_checkbox.setStyleSheet("font-weight: bold; color: #B91C1C;")
        self.martial_law_checkbox.toggled.connect(self._on_martial_law_toggled)
        martial_layout.addWidget(self.martial_law_checkbox)

        # Ліміт відпустки під час воєнного стану
        martial_limit_layout = QFormLayout()
        self.martial_limit_input = QSpinBox()
        self.martial_limit_input.setRange(1, 365)
        self.martial_limit_input.setValue(DEFAULT_MARTIAL_LAW_VACATION_LIMIT)
        self.martial_limit_input.setSuffix(" днів")
        self.martial_limit_input.setToolTip(
            "Закон № 2136 дозволяє обмежувати відпустку до 24 днів під час воєнного стану"
        )
        martial_limit_layout.addRow("Ліміт днів відпустки:", self.martial_limit_input)
        martial_layout.addLayout(martial_limit_layout)

        martial_info = QLabel(
            "Під час воєнного стану:\n"
            "• Всі календарні дні рахуються як відпускні\n"
            "• Вихідні та свята НЕ додають додаткових днів\n"
            "• Діє обмеження на максимальну кількість днів"
        )
        martial_info.setWordWrap(True)
        martial_info.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        martial_layout.addWidget(martial_info)

        martial_group.setLayout(martial_layout)
        layout.addWidget(martial_group)

        # Група "Норми днів відпустки"
        norms_group = QGroupBox("📅 Норми днів відпустки на рік")
        norms_layout = QFormLayout()

        # Науково-педагогічні працівники
        self.scientific_days_input = QSpinBox()
        self.scientific_days_input.setRange(0, 365)
        self.scientific_days_input.setValue(DEFAULT_VACATION_DAYS["scientific_pedagogical"])
        self.scientific_days_input.setSuffix(" днів")
        self.scientific_days_input.setToolTip(
            "Професори, доценти, старші викладачі, викладачі, асистенти, завідувачі кафедри"
        )
        norms_layout.addRow("Науково-педагогічні:", self.scientific_days_input)

        # Педагогічні працівники
        self.pedagogical_days_input = QSpinBox()
        self.pedagogical_days_input.setRange(0, 365)
        self.pedagogical_days_input.setValue(DEFAULT_VACATION_DAYS["pedagogical"])
        self.pedagogical_days_input.setSuffix(" днів")
        self.pedagogical_days_input.setToolTip(
            "Педагоги, вихователі, методисти"
        )
        norms_layout.addRow("Педагогічні:", self.pedagogical_days_input)

        # Адміністративний персонал
        self.admin_days_input = QSpinBox()
        self.admin_days_input.setRange(0, 365)
        self.admin_days_input.setValue(DEFAULT_VACATION_DAYS["administrative"])
        self.admin_days_input.setSuffix(" днів")
        self.admin_days_input.setToolTip(
            "Секретарі, лаборанти, інший адміністративний персонал"
        )
        norms_layout.addRow("Адміністративний персонал:", self.admin_days_input)

        norms_group.setLayout(norms_layout)
        layout.addWidget(norms_group)

        # Підказка
        help_label = QLabel(
            "Ці налаштування визначають річну норму днів відпустки для різних категорій працівників. "
            "Під час воєнного стану норми можуть бути обмежені законом № 2136."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(help_label)

        layout.addStretch()
        return widget

    def _create_tabel_tab(self) -> QWidget:
        """Створює комбіновану вкладку Табель (форматування + відпустки + табель)."""
        from PyQt6.QtWidgets import QScrollArea

        # Create scroll area for all sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        # ==================== ФОРМАТУВАННЯ ====================
        formatting_label = QLabel("<b>ФОРМАТУВАННЯ</b>")
        formatting_label.setStyleSheet("font-size: 14px; padding: 5px; color: #1e40af;")
        layout.addWidget(formatting_label)

        # Група "Порядок виводу ПІБ"
        name_order_group = QGroupBox("Порядок виводу ПІБ у підписі")
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
        warnings_group = QGroupBox("Попередження про завершення контракту")
        warnings_layout = QFormLayout()

        self.contract_warning_days_input = QSpinBox()
        self.contract_warning_days_input.setRange(1, 365)
        self.contract_warning_days_input.setValue(30)
        self.contract_warning_days_input.setSuffix(" днів")
        warnings_layout.addRow("Попереджати за:", self.contract_warning_days_input)

        warnings_group.setLayout(warnings_layout)
        layout.addWidget(warnings_group)

        # Група "Бібліотека причин"
        reasons_group = QGroupBox("Типові причини для неоплачуваної відпустки")
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
        self.unpaid_reasons_input.setMaximumHeight(100)
        reasons_layout.addWidget(self.unpaid_reasons_input)

        reasons_group.setLayout(reasons_layout)
        layout.addWidget(reasons_group)

        # ==================== ВІДПУСТКИ ====================
        vacation_label = QLabel("<b>ВІДПУСТКИ</b>")
        vacation_label.setStyleSheet("font-size: 14px; padding: 15px 5px 5px; color: #1e40af;")
        layout.addWidget(vacation_label)

        # Група "Воєнний стан"
        martial_group = QGroupBox("Воєнний стан")
        martial_layout = QVBoxLayout()

        self.martial_law_checkbox = QCheckBox(
            "Увімкнути режим воєнного стану\n"
            "(всі дні рахуються як відпускні, включаючи вихідні та свята)"
        )
        self.martial_law_checkbox.setStyleSheet("font-weight: bold; color: #B91C1C;")
        self.martial_law_checkbox.toggled.connect(self._on_martial_law_toggled)
        martial_layout.addWidget(self.martial_law_checkbox)

        # Ліміт відпустки під час воєнного стану
        martial_limit_layout = QFormLayout()
        self.martial_limit_input = QSpinBox()
        self.martial_limit_input.setRange(1, 365)
        self.martial_limit_input.setValue(DEFAULT_MARTIAL_LAW_VACATION_LIMIT)
        self.martial_limit_input.setSuffix(" днів")
        self.martial_limit_input.setToolTip(
            "Закон № 2136 дозволяє обмежувати відпустку до 24 днів під час воєнного стану"
        )
        martial_limit_layout.addRow("Ліміт днів відпустки:", self.martial_limit_input)
        martial_layout.addLayout(martial_limit_layout)

        martial_info = QLabel(
            "Під час воєнного стану:\n"
            "• Всі календарні дні рахуються як відпускні\n"
            "• Вихідні та свята НЕ додають додаткових днів\n"
            "• Діє обмеження на максимальну кількість днів"
        )
        martial_info.setWordWrap(True)
        martial_info.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        martial_layout.addWidget(martial_info)

        martial_group.setLayout(martial_layout)
        layout.addWidget(martial_group)

        # Група "Норми днів відпустки"
        norms_group = QGroupBox("📅 Норми днів відпустки на рік")
        norms_layout = QFormLayout()

        # Науково-педагогічні працівники
        self.scientific_days_input = QSpinBox()
        self.scientific_days_input.setRange(0, 365)
        self.scientific_days_input.setValue(DEFAULT_VACATION_DAYS["scientific_pedagogical"])
        self.scientific_days_input.setSuffix(" днів")
        self.scientific_days_input.setToolTip(
            "Професори, доценти, старші викладачі, викладачі, асистенти, завідувачі кафедри"
        )
        norms_layout.addRow("Науково-педагогічні:", self.scientific_days_input)

        # Педагогічні працівники
        self.pedagogical_days_input = QSpinBox()
        self.pedagogical_days_input.setRange(0, 365)
        self.pedagogical_days_input.setValue(DEFAULT_VACATION_DAYS["pedagogical"])
        self.pedagogical_days_input.setSuffix(" днів")
        self.pedagogical_days_input.setToolTip(
            "Педагоги, вихователі, методисти"
        )
        norms_layout.addRow("Педагогічні:", self.pedagogical_days_input)

        # Адміністративний персонал
        self.admin_days_input = QSpinBox()
        self.admin_days_input.setRange(0, 365)
        self.admin_days_input.setValue(DEFAULT_VACATION_DAYS["administrative"])
        self.admin_days_input.setSuffix(" днів")
        self.admin_days_input.setToolTip(
            "Секретарі, лаборанти, інший адміністративний персонал"
        )
        norms_layout.addRow("Адміністративний персонал:", self.admin_days_input)

        norms_group.setLayout(norms_layout)
        layout.addWidget(norms_group)

        # ==================== ТАБЕЛЬ ====================
        tabel_label = QLabel("<b>ТАБЕЛЬ</b>")
        tabel_label.setStyleSheet("font-size: 14px; padding: 15px 5px 5px; color: #1e40af;")
        layout.addWidget(tabel_label)

        # Група "Підсумки"
        totals_group = QGroupBox("Підсумки табеля")
        totals_layout = QVBoxLayout()

        self.show_monthly_totals_checkbox = QCheckBox(
            "Показувати підсумки за місяць\n"
            "(рядок 'Всього' з підрахованими днями та годинами)"
        )
        totals_layout.addWidget(self.show_monthly_totals_checkbox)

        self.limit_hours_calc_checkbox = QCheckBox(
            "Обмежити розрахунок годин лише обраними посадами\n"
            "(години за півмісяця рахувати тільки для працівників у списку нижче)"
        )
        totals_layout.addWidget(self.limit_hours_calc_checkbox)

        totals_group.setLayout(totals_layout)
        layout.addWidget(totals_group)

        # Група "Години для коду 'Р'"
        work_hours_group = QGroupBox("Години для коду 'Р' (робочий день)")
        work_hours_layout = QFormLayout()

        self.work_hours_per_day_edit = QLineEdit()
        self.work_hours_per_day_edit.setPlaceholderText("Наприклад: 8 або 8:15")
        self.work_hours_per_day_edit.setText("8")
        self.work_hours_per_day_edit.setToolTip(
            "Кількість годин роботи за один робочий день (код 'Р'). Формат: 8 або 8:15"
        )
        work_hours_layout.addRow("Годин на день:", self.work_hours_per_day_edit)

        work_hours_group.setLayout(work_hours_layout)
        layout.addWidget(work_hours_group)

        # Група "Працівники для підрахунку годин"
        hours_calc_group = QGroupBox("Працівники, для яких рахувати години")
        hours_calc_layout = QVBoxLayout()

        # Підказка
        hint_label = QLabel(
            "Оберіть посади, для яких у табелі буде відображатися підрахунок годин:"
        )
        hint_label.setWordWrap(True)
        hours_calc_layout.addWidget(hint_label)

        # Список обраних посад
        self.hours_calc_positions_list = QListWidget()
        self.hours_calc_positions_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self.hours_calc_positions_list.setMaximumHeight(100)
        hours_calc_layout.addWidget(self.hours_calc_positions_list)

        # Кнопки Add/Remove
        buttons_layout = QHBoxLayout()
        add_position_btn = QPushButton("Додати")
        add_position_btn.clicked.connect(self._add_position)
        buttons_layout.addWidget(add_position_btn)

        remove_position_btn = QPushButton("Видалити")
        remove_position_btn.clicked.connect(self._remove_position)
        buttons_layout.addWidget(remove_position_btn)
        hours_calc_layout.addLayout(buttons_layout)

        hours_calc_group.setLayout(hours_calc_layout)
        layout.addWidget(hours_calc_group)

        # Група "HR (Кадри)"
        hr_group = QGroupBox("Підписант табеля")
        hr_layout = QFormLayout()

        self.hr_employee_input = QComboBox()
        self.hr_employee_input.setEditable(True)
        hr_layout.addRow("Працівник кадрової служби:", self.hr_employee_input)

        hr_group.setLayout(hr_layout)
        layout.addWidget(hr_group)

        # Підказка
        help_label = QLabel(
            "Години підраховуються лише для обраних посад. "
            "Для інших працівників у табелі відображатимуться лише коди днів ('Р', 'В', тощо)."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(help_label)

        layout.addStretch()
        scroll_content.setLayout(layout)

        scroll.setWidget(scroll_content)
        return scroll

    def _create_debug_tab(self) -> QWidget:
        """Створює вкладку Debug для перегляду/редагування БД."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Warning label
        warning = QLabel(
            "УВАГА: Цей розділ призначений для розробників. "
            "Зміни в базі даних можуть призвести до некоректної роботи програми!"
        )
        warning.setStyleSheet("color: #B91C1C; font-weight: bold; padding: 10px; background: #FEE2E2; border-radius: 5px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Table selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Таблиця:"))

        self.debug_table_combo = QComboBox()
        self._populate_table_combo()
        self.debug_table_combo.currentIndexChanged.connect(self._load_debug_table)
        selector_layout.addWidget(self.debug_table_combo)

        load_btn = QPushButton("Завантажити")
        load_btn.clicked.connect(self._load_debug_table)
        selector_layout.addWidget(load_btn)

        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # Filter for attendance/tabel_approval
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Фільтр (staff_id):"))
        self.debug_filter_staff = QLineEdit()
        self.debug_filter_staff.setPlaceholderText("Залиште порожнім для всіх")
        self.debug_filter_staff.setMaximumWidth(100)
        filter_layout.addWidget(self.debug_filter_staff)

        filter_layout.addWidget(QLabel("is_correction:"))
        self.debug_filter_correction = QComboBox()
        self.debug_filter_correction.addItems(["Всі", "True", "False"])
        self.debug_filter_correction.setMaximumWidth(100)
        filter_layout.addWidget(self.debug_filter_correction)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Data table
        self.debug_table = QTableWidget()
        self.debug_table.setAlternatingRowColors(True)
        self.debug_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.debug_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.debug_table.horizontalHeader().setStretchLastSection(True)
        self.debug_table.cellDoubleClicked.connect(self._edit_debug_cell)
        layout.addWidget(self.debug_table)

        # Action buttons
        actions_layout = QHBoxLayout()

        edit_btn = QPushButton("Редагувати обране")
        edit_btn.clicked.connect(self._edit_selected_record)
        actions_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Видалити обране")
        delete_btn.clicked.connect(self._delete_selected_record)
        delete_btn.setStyleSheet("background-color: #FEE2E2;")
        actions_layout.addWidget(delete_btn)

        actions_layout.addStretch()

        copy_btn = QPushButton("Копіювати")
        copy_btn.clicked.connect(self._copy_selected_record)
        actions_layout.addWidget(copy_btn)

        sql_btn = QPushButton("SQL запит")
        sql_btn.clicked.connect(self._run_sql_query)
        actions_layout.addWidget(sql_btn)

        layout.addLayout(actions_layout)

        # Record count label
        self.debug_record_count = QLabel("Записів: 0")
        layout.addWidget(self.debug_record_count)

        return widget

    def _populate_table_combo(self):
        """Заповнює dropdown списком таблиць з бази даних."""
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).parent.parent.parent / "vacation_manager.db"

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_%' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            self.debug_table_combo.clear()
            self.debug_table_combo.addItems(tables)

        except Exception as e:
            # Fallback to common tables if DB query fails
            self.debug_table_combo.addItems([
                "attendance", "staff", "documents", "tabel_approval", "settings"
            ])

    def _load_debug_table(self):
        """Завантажує дані обраної таблиці."""
        import sqlite3
        from pathlib import Path

        table_name = self.debug_table_combo.currentText()
        db_path = Path(__file__).parent.parent.parent / "vacation_manager.db"

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query with filters
            query = f"SELECT * FROM {table_name}"
            params = []

            filters = []
            staff_filter = self.debug_filter_staff.text().strip()
            if staff_filter and table_name in ["attendance", "documents"]:
                filters.append("staff_id = ?")
                params.append(int(staff_filter))

            correction_filter = self.debug_filter_correction.currentText()
            if correction_filter != "Всі" and table_name in ["attendance", "tabel_approval"]:
                filters.append("is_correction = ?")
                params.append(1 if correction_filter == "True" else 0)

            if filters:
                query += " WHERE " + " AND ".join(filters)

            query += " ORDER BY id DESC LIMIT 100"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            if rows:
                columns = rows[0].keys()
                self.debug_table.setColumnCount(len(columns))
                self.debug_table.setHorizontalHeaderLabels(list(columns))
                self.debug_table.setRowCount(len(rows))

                for row_idx, row in enumerate(rows):
                    for col_idx, col_name in enumerate(columns):
                        value = row[col_name]
                        item = QTableWidgetItem(str(value) if value is not None else "NULL")
                        item.setData(Qt.ItemDataRole.UserRole, {"column": col_name, "value": value})
                        self.debug_table.setItem(row_idx, col_idx, item)

                self.debug_record_count.setText(f"Записів: {len(rows)}")
            else:
                self.debug_table.setRowCount(0)
                self.debug_table.setColumnCount(0)
                self.debug_record_count.setText("Записів: 0")

            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити таблицю: {e}")

    def _edit_debug_cell(self, row: int, col: int):
        """Редагує вибрану комірку."""
        item = self.debug_table.item(row, col)
        if not item:
            return

        column_name = self.debug_table.horizontalHeaderItem(col).text()
        current_value = item.text()

        new_value, ok = QInputDialog.getText(
            self, "Редагувати значення",
            f"Стовпець: {column_name}\nНове значення:",
            text=current_value
        )

        if ok:
            # Get ID from first column
            id_item = self.debug_table.item(row, 0)
            record_id = int(id_item.text())
            table_name = self.debug_table_combo.currentText()

            self._update_record(table_name, record_id, column_name, new_value)

    def _edit_selected_record(self):
        """Редагує обраний запис."""
        current_row = self.debug_table.currentRow()
        current_col = self.debug_table.currentColumn()
        if current_row >= 0 and current_col >= 0:
            self._edit_debug_cell(current_row, current_col)

    def _update_record(self, table_name: str, record_id: int, column: str, value: str):
        """Оновлює запис у базі даних."""
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).parent.parent.parent / "vacation_manager.db"

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Convert value types
            if value.lower() == "null":
                sql_value = None
            elif value.lower() in ("true", "false"):
                sql_value = 1 if value.lower() == "true" else 0
            else:
                try:
                    sql_value = int(value)
                except ValueError:
                    sql_value = value

            cursor.execute(
                f"UPDATE {table_name} SET {column} = ? WHERE id = ?",
                (sql_value, record_id)
            )
            conn.commit()
            conn.close()

            QMessageBox.information(self, "Успіх", f"Запис оновлено: {column} = {value}")
            self._load_debug_table()

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося оновити запис: {e}")

    def _copy_selected_record(self):
        """Копіює обраний запис у буфер обміну."""
        from PyQt6.QtWidgets import QApplication

        current_row = self.debug_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть запис для копіювання")
            return

        # Collect all column values for the row
        values = []
        headers = []
        for col in range(self.debug_table.columnCount()):
            header_item = self.debug_table.horizontalHeaderItem(col)
            if header_item:
                headers.append(header_item.text())
            item = self.debug_table.item(current_row, col)
            if item:
                values.append(item.text())
            else:
                values.append("")

        # Format as both header: value pairs and tab-separated
        pairs = [f"{h}: {v}" for h, v in zip(headers, values)]
        text = "\n".join(pairs) + "\n\n" + "\t".join(values)

        clipboard = QApplication.clipboard()
        clipboard.setText(text)

        QMessageBox.information(self, "Скопійовано", f"Запис скопійовано в буфер обміну")

    def _delete_selected_record(self):
        """Видаляє обрані записи."""
        import sqlite3
        from pathlib import Path

        # Get all selected rows
        selected_rows = set()
        for item in self.debug_table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "Увага", "Оберіть записи для видалення")
            return

        # Collect IDs from selected rows
        record_ids = []
        for row in selected_rows:
            id_item = self.debug_table.item(row, 0)
            if id_item:
                record_ids.append(int(id_item.text()))

        if not record_ids:
            return

        table_name = self.debug_table_combo.currentText()

        # Confirmation message
        if len(record_ids) == 1:
            msg = f"Видалити запис ID={record_ids[0]} з таблиці {table_name}?"
        else:
            msg = f"Видалити {len(record_ids)} записів (ID: {', '.join(map(str, record_ids[:5]))}" \
                  f"{'...' if len(record_ids) > 5 else ''}) з таблиці {table_name}?"

        reply = QMessageBox.question(
            self, "Підтвердження", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        db_path = Path(__file__).parent.parent.parent / "vacation_manager.db"

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Delete all selected records
            placeholders = ",".join("?" * len(record_ids))
            cursor.execute(f"DELETE FROM {table_name} WHERE id IN ({placeholders})", record_ids)
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()

            QMessageBox.information(self, "Успіх", f"Видалено записів: {deleted_count}")
            self._load_debug_table()

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося видалити записи: {e}")

    def _run_sql_query(self):
        """Відкриває конструктор SQL запитів."""
        dialog = SQLQueryBuilderDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            query = dialog.get_query()
            if query:
                self._execute_sql_query(query)

    def _execute_sql_query(self, query: str):
        """Виконує SQL запит."""
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).parent.parent.parent / "vacation_manager.db"

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query.strip())

            if query.strip().upper().startswith("SELECT"):
                rows = cursor.fetchall()
                if rows:
                    columns = rows[0].keys()
                    self.debug_table.setColumnCount(len(columns))
                    self.debug_table.setHorizontalHeaderLabels(list(columns))
                    self.debug_table.setRowCount(len(rows))

                    for row_idx, row in enumerate(rows):
                        for col_idx, col_name in enumerate(columns):
                            value = row[col_name]
                            item = QTableWidgetItem(str(value) if value is not None else "NULL")
                            self.debug_table.setItem(row_idx, col_idx, item)

                    self.debug_record_count.setText(f"Записів: {len(rows)}")
                else:
                    self.debug_table.setRowCount(0)
                    self.debug_record_count.setText("Записів: 0")
            else:
                conn.commit()
                QMessageBox.information(
                    self, "Успіх",
                    f"Запит виконано. Змінено рядків: {cursor.rowcount}"
                )
                self._load_debug_table()

            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Помилка SQL", f"Помилка виконання запиту:\n{e}")

    def _add_position(self):
        """Відкриває діалог для додавання посади."""
        dialog = PositionSelectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_position = dialog.selected_position()
            if selected_position:
                # Перевіряємо, чи посада вже є в списку
                existing_items = [
                    self.hours_calc_positions_list.item(i).text()
                    for i in range(self.hours_calc_positions_list.count())
                ]
                if selected_position not in existing_items:
                    self.hours_calc_positions_list.addItem(selected_position)

    def _remove_position(self):
        """Видаляє обрану посаду зі списку."""
        current_item = self.hours_calc_positions_list.currentItem()
        if current_item:
            row = self.hours_calc_positions_list.row(current_item)
            self.hours_calc_positions_list.takeItem(row)

    def _on_martial_law_toggled(self, checked: bool):
        """Обробляє зміну прапорця воєнного стану."""
        if checked:
            self.martial_limit_input.setEnabled(True)
        else:
            self.martial_limit_input.setEnabled(False)

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
            self.university_name_dav_input.setText(
                SystemSettings.get_value(db, "university_name_dative", "")
            )
            self.edrpou_code_input.setText(
                SystemSettings.get_value(db, "edrpou_code", "")
            )

            # Підрозділ
            self.dept_name_input.setText(
                SystemSettings.get_value(db, "dept_name", "")
            )
            self.dept_abbr_input.setText(
                SystemSettings.get_value(db, "dept_abbr", "")
            )

            # Завантажуємо список співробітників для випадаючих списків
            self._load_staff_for_combos(db)

            # Встановлюємо завідувача
            dept_head_id = SystemSettings.get_value(db, "dept_head_id", None)
            if dept_head_id:
                index = self.dept_head_input.findData(dept_head_id)
                if index >= 0:
                    self.dept_head_input.setCurrentIndex(index)

            # Встановлюємо фахівця
            specialist_id = SystemSettings.get_value(db, "dept_specialist_id", None)
            if specialist_id:
                index = self.dept_specialist_input.findData(specialist_id)
                if index >= 0:
                    self.dept_specialist_input.setCurrentIndex(index)

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

            # Відпустки та воєнний стан
            martial_law_raw = SystemSettings.get_value(db, SETTING_MARTIAL_LAW_ENABLED, False)
            # Конвертуємо рядок у булеве значення
            martial_law = str(martial_law_raw).lower() in ("true", "1", "yes")
            self.martial_law_checkbox.setChecked(martial_law)
            self.martial_limit_input.setEnabled(martial_law)

            self.martial_limit_input.setValue(
                SystemSettings.get_value(db, SETTING_MARTIAL_LAW_VACATION_LIMIT, DEFAULT_MARTIAL_LAW_VACATION_LIMIT)
            )

            self.scientific_days_input.setValue(
                SystemSettings.get_value(db, SETTING_VACATION_DAYS_SCIENTIFIC_PEDAGOGICAL, DEFAULT_VACATION_DAYS["scientific_pedagogical"])
            )
            self.pedagogical_days_input.setValue(
                SystemSettings.get_value(db, SETTING_VACATION_DAYS_PEDAGOGICAL, DEFAULT_VACATION_DAYS["pedagogical"])
            )
            self.admin_days_input.setValue(
                SystemSettings.get_value(db, SETTING_VACATION_DAYS_ADMINISTRATIVE, DEFAULT_VACATION_DAYS["administrative"])
            )

            # Налаштування табеля
            tabel_show_totals_raw = SystemSettings.get_value(db, "tabel_show_monthly_totals", True)
            tabel_show_totals = str(tabel_show_totals_raw).lower() in ("true", "1", "yes") if isinstance(tabel_show_totals_raw, str) else tabel_show_totals_raw
            self.show_monthly_totals_checkbox.setChecked(tabel_show_totals)

            limit_hours_raw = SystemSettings.get_value(db, "tabel_limit_hours_calc", False)
            limit_hours = str(limit_hours_raw).lower() in ("true", "1", "yes") if isinstance(limit_hours_raw, str) else limit_hours_raw
            self.limit_hours_calc_checkbox.setChecked(limit_hours)

            work_hours_raw = SystemSettings.get_value(db, "tabel_work_hours_per_day", 8)
            self.work_hours_per_day_edit.setText(str(work_hours_raw) if work_hours_raw else "8")

            # Завантажуємо унікальні посади для вибору
            self._load_positions_for_hours_calc(db)

            # Telegram налаштування
            telegram_enabled_raw = SystemSettings.get_value(db, "telegram_enabled", False)
            telegram_enabled = str(telegram_enabled_raw).lower() in ("true", "1", "yes") if isinstance(telegram_enabled_raw, str) else telegram_enabled_raw
            self.telegram_enabled_checkbox.setChecked(telegram_enabled)

            self.telegram_token_input.setText(
                SystemSettings.get_value(db, "telegram_bot_token", "")
            )
            
            # Telegram mode (polling or webhook)
            telegram_mode = SystemSettings.get_value(db, "telegram_mode", "polling")
            mode_index = 1 if telegram_mode == "webhook" else 0
            self.telegram_mode_combo.setCurrentIndex(mode_index)
            self._on_telegram_mode_changed(mode_index)  # Update UI state
            
            self.telegram_webhook_input.setText(
                SystemSettings.get_value(db, "telegram_webhook_url", "")
            )
            self.telegram_mini_app_url_input.setText(
                SystemSettings.get_value(db, "telegram_mini_app_url", "")
            )

    def _load_staff_for_combos(self, db):
        """Завантажує співробітників у випадаючі списки."""
        # Тільки завідувачі для завідувача кафедри
        head_list = (
            db.query(Staff)
            .filter(Staff.is_active == True)
            .filter(Staff.position.in_([StaffPosition.HEAD_OF_DEPARTMENT, StaffPosition.ACTING_HEAD_OF_DEPARTMENT]))
            .order_by(Staff.pib_nom)
            .all()
        )

        # Тільки фахівці для фахівця кафедри
        specialist_list = (
            db.query(Staff)
            .filter(Staff.is_active == True, Staff.position == StaffPosition.SPECIALIST)
            .order_by(Staff.pib_nom)
            .all()
        )

        # Зберігаємо поточні значення
        current_head = self.dept_head_input.currentText()
        current_specialist = self.dept_specialist_input.currentText()

        # Очищаємо та заповнюємо
        self.dept_head_input.clear()
        self.dept_specialist_input.clear()

        for staff in head_list:
            # Додаємо з ID як data
            self.dept_head_input.addItem(staff.pib_nom, staff.id)

        for staff in specialist_list:
            # Додаємо з ID як data
            self.dept_specialist_input.addItem(staff.pib_nom, staff.id)

        # Відновлюємо значення, якщо є
        if current_head:
            index = self.dept_head_input.findText(current_head)
            if index >= 0:
                self.dept_head_input.setCurrentIndex(index)

        if current_specialist:
            index = self.dept_specialist_input.findText(current_specialist)
            if index >= 0:
                self.dept_specialist_input.setCurrentIndex(index)

    def _load_positions_for_hours_calc(self, db):
        """Завантажує збережені посади для підрахунку годин."""
        # Отримуємо збережений вибір з налаштувань
        saved_positions_raw = SystemSettings.get_value(db, "tabel_hours_calc_positions", [])
        # Handle case where value might be stored as JSON string
        if isinstance(saved_positions_raw, str):
            import json
            try:
                saved_positions = json.loads(saved_positions_raw)
            except (json.JSONDecodeError, TypeError):
                saved_positions = []
        else:
            saved_positions = saved_positions_raw or []

        # Очищаємо та заповнюємо список
        self.hours_calc_positions_list.clear()
        for position in saved_positions:
            # Convert enum values to Ukrainian labels
            label = get_position_label(position) if position in STAFF_POSITION_LABELS else position
            self.hours_calc_positions_list.addItem(label)

        # If nothing selected, add "Фахівець" as default
        if self.hours_calc_positions_list.count() == 0:
            self.hours_calc_positions_list.addItem(STAFF_POSITION_LABELS[StaffPosition.SPECIALIST])

        # Load HR employees for the combo box
        hr_list = (
            db.query(Staff)
            .filter(Staff.is_active == True)
            .all()
        )
        hr_filtered = [
            s for s in hr_list
            if any(k in s.position.lower() for k in ['кадр', 'персонал', 'інспектор', 'hr'])
        ]

        # Отримуємо збережене значення підписанта
        saved_hr = SystemSettings.get_value(db, "hr_signature_id", None)

        self.hr_employee_input.clear()
        for staff in hr_filtered:
            self.hr_employee_input.addItem(staff.pib_nom, staff.id)

        # Відновлюємо збережене значення
        if saved_hr and saved_hr not in ("None", "none", ""):
            if str(saved_hr).startswith("custom:"):
                # Користувач ввів ім'я вручну
                custom_name = str(saved_hr)[7:]  # Видаляємо "custom:"
                self.hr_employee_input.setEditText(custom_name)
            else:
                # Збережено ID співробітника
                try:
                    index = self.hr_employee_input.findData(int(saved_hr))
                except ValueError:
                    index = -1
                if index >= 0:
                    self.hr_employee_input.setCurrentIndex(index)
                else:
                    # Якщо не знайдено за ID, шукаємо за текстом
                    index = self.hr_employee_input.findText(saved_hr)
                    if index >= 0:
                        self.hr_employee_input.setCurrentIndex(index)

        # Зберігаємо всі доступні посади для діалогу вибору (as Ukrainian labels)
        self._all_positions = []
        raw_positions = db.query(Staff.position).filter(
            Staff.position != None, Staff.position != ""
        ).distinct().order_by(Staff.position).all()
        for pos in raw_positions:
            label = get_position_label(pos[0]) if pos[0] in STAFF_POSITION_LABELS else pos[0]
            self._all_positions.append(label)

    def _load_approvers(self, db):
        """Завантажує список погоджувачів."""
        self.approvers_list.clear()

        approvers = (
            db.query(Approvers)
            .order_by(Approvers.order_index)
            .all()
        )

        for approver in approvers:
            display_name = approver.full_name_nom or approver.full_name_dav
            item = QListWidgetItem(
                f"{approver.order_index}. {approver.position_name} - {display_name}"
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
                    full_name_nom=dialog.name_nom_input.text() or None,
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
                approver.full_name_nom = dialog.name_nom_input.text() or None
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
            SystemSettings.set_value(
                db, "university_name_dative",
                self.university_name_dav_input.text().strip()
            )
            SystemSettings.set_value(
                db, "edrpou_code",
                self.edrpou_code_input.text().strip()
            )

            # Підрозділ
            SystemSettings.set_value(
                db, "dept_name",
                self.dept_name_input.text().strip()
            )
            SystemSettings.set_value(
                db, "dept_abbr",
                self.dept_abbr_input.text().strip()
            )

            dept_head_id = self.dept_head_input.currentData()
            SystemSettings.set_value(db, "dept_head_id", dept_head_id)

            specialist_id = self.dept_specialist_input.currentData()
            SystemSettings.set_value(db, "dept_specialist_id", specialist_id)

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

            # Відпустки та воєнний стан
            SystemSettings.set_value(
                db, SETTING_MARTIAL_LAW_ENABLED,
                self.martial_law_checkbox.isChecked()
            )

            SystemSettings.set_value(
                db, SETTING_MARTIAL_LAW_VACATION_LIMIT,
                self.martial_limit_input.value()
            )

            SystemSettings.set_value(
                db, SETTING_VACATION_DAYS_SCIENTIFIC_PEDAGOGICAL,
                self.scientific_days_input.value()
            )
            SystemSettings.set_value(
                db, SETTING_VACATION_DAYS_PEDAGOGICAL,
                self.pedagogical_days_input.value()
            )
            SystemSettings.set_value(
                db, SETTING_VACATION_DAYS_ADMINISTRATIVE,
                self.admin_days_input.value()
            )

            # Налаштування табеля
            SystemSettings.set_value(
                db, "tabel_show_monthly_totals",
                self.show_monthly_totals_checkbox.isChecked()
            )
            SystemSettings.set_value(
                db, "tabel_limit_hours_calc",
                self.limit_hours_calc_checkbox.isChecked()
            )
            SystemSettings.set_value(
                db, "tabel_work_hours_per_day",
                self.work_hours_per_day_edit.text().strip()
            )

            # Зберігаємо обрані посади для підрахунку годин
            # Convert Ukrainian labels back to enum values
            label_to_enum = {v: k for k, v in STAFF_POSITION_LABELS.items()}
            selected_positions = []
            for i in range(self.hours_calc_positions_list.count()):
                item = self.hours_calc_positions_list.item(i)
                label = item.text()
                # Convert label to enum value if it exists in the mapping
                selected_positions.append(label_to_enum.get(label, label))
            SystemSettings.set_value(db, "tabel_hours_calc_positions", selected_positions)

            # Працівник кадрової служби
            hr_employee_id = self.hr_employee_input.currentData()
            # Якщо обрано зі списку - зберігаємо ID, якщо введено вручну - зберігаємо текст
            if hr_employee_id is None:
                hr_employee_text = self.hr_employee_input.currentText().strip()
                if hr_employee_text:
                    SystemSettings.set_value(db, "hr_signature_id", f"custom:{hr_employee_text}")
                else:
                    SystemSettings.set_value(db, "hr_signature_id", "")
            else:
                SystemSettings.set_value(db, "hr_signature_id", hr_employee_id)

            # Telegram налаштування
            SystemSettings.set_value(
                db, "telegram_enabled",
                self.telegram_enabled_checkbox.isChecked()
            )
            SystemSettings.set_value(
                db, "telegram_bot_token",
                self.telegram_token_input.text().strip()
            )
            # Save telegram mode
            telegram_mode = self.telegram_mode_combo.currentData() or "polling"
            SystemSettings.set_value(db, "telegram_mode", telegram_mode)
            
            SystemSettings.set_value(
                db, "telegram_webhook_url",
                self.telegram_webhook_input.text().strip()
            )
            SystemSettings.set_value(
                db, "telegram_mini_app_url",
                self.telegram_mini_app_url_input.text().strip()
            )

        # Показуємо повідомлення і закриваємо діалог
        QMessageBox.information(
            self,
            "Успішно",
            "Налаштування збережено!"
        )
        self.accept()

    def _create_telegram_tab(self) -> QWidget:
        """Створює вкладку налаштувань Telegram."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Група "Telegram Bot"
        bot_group = QGroupBox("Telegram Bot")
        bot_layout = QFormLayout()

        self.telegram_enabled_checkbox = QCheckBox("Увімкнути Telegram бота")
        bot_layout.addRow(self.telegram_enabled_checkbox)

        self.telegram_token_input = QLineEdit()
        self.telegram_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.telegram_token_input.setPlaceholderText(
            "Введіть токен бота від @BotFather\n"
            "Наприклад: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        )
        bot_layout.addRow("Bot Token:", self.telegram_token_input)

        # Bot Mode selector
        self.telegram_mode_combo = QComboBox()
        self.telegram_mode_combo.addItem("Polling (рекомендовано для розробки)", "polling")
        self.telegram_mode_combo.addItem("Webhook (потребує публічний URL)", "webhook")
        self.telegram_mode_combo.setToolTip(
            "Polling: Бот опитує Telegram API (простіше, не потребує публічного URL)\n"
            "Webhook: Telegram надсилає оновлення на ваш сервер (ефективніше для продакшн)"
        )
        self.telegram_mode_combo.currentIndexChanged.connect(self._on_telegram_mode_changed)
        bot_layout.addRow("Режим роботи:", self.telegram_mode_combo)

        self.telegram_webhook_input = QLineEdit()
        self.telegram_webhook_input.setPlaceholderText(
            "Webhook URL для отримання оновлень\n"
            "Наприклад: https://your-domain.com/api/telegram/webhook\n"
            "Для розробки можна використовувати ngrok або інший тунель"
        )
        bot_layout.addRow("Webhook URL:", self.telegram_webhook_input)

        self.telegram_mini_app_url_input = QLineEdit()
        self.telegram_mini_app_url_input.setPlaceholderText(
            "URL Mini App для відкриття в Telegram\n"
            "Наприклад: https://your-domain.com/telegram-mini-app/"
        )
        bot_layout.addRow("Mini App URL:", self.telegram_mini_app_url_input)

        # Кнопки автоновизначення та тестування
        buttons_layout = QHBoxLayout()
        auto_btn = QPushButton("Автовизначити URL")
        auto_btn.setToolTip("Автоматично заповнити URL на основі поточної мережі")
        auto_btn.clicked.connect(self._auto_detect_urls)
        buttons_layout.addWidget(auto_btn)

        test_btn = QPushButton("Перевірити з'єднання")
        test_btn.clicked.connect(self._test_telegram_connection)
        buttons_layout.addWidget(test_btn)
        buttons_layout.addStretch()
        bot_layout.addRow("", buttons_layout)

        bot_group.setLayout(bot_layout)
        layout.addWidget(bot_group)

        # Група "Запити на підключення"
        requests_group = QGroupBox("Запити на підключення")
        requests_layout = QVBoxLayout()

        # Фільтр
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Статус:"))
        self.request_status_filter = QComboBox()
        self.request_status_filter.addItems(["Очікує (Pending)", "Схвалено (Approved)", "Відхилено (Rejected)", "Всі"])
        self.request_status_filter.currentIndexChanged.connect(self._load_telegram_requests)
        filter_layout.addWidget(self.request_status_filter)
        filter_layout.addStretch()
        requests_layout.addLayout(filter_layout)

        # Таблиця запитів
        self.telegram_requests_table = QTableWidget()
        self.telegram_requests_table.setColumnCount(5)
        self.telegram_requests_table.setHorizontalHeaderLabels(["Користувач", "Username", "Статус", "Телефон", "Дата"])
        self.telegram_requests_table.horizontalHeader().setStretchLastSection(True)
        self.telegram_requests_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.telegram_requests_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.telegram_requests_table.setMinimumHeight(200)
        requests_layout.addWidget(self.telegram_requests_table)

        # Кнопки управління
        req_buttons_layout = QHBoxLayout()

        refresh_btn = QPushButton("Оновити")
        refresh_btn.clicked.connect(self._load_telegram_requests)
        req_buttons_layout.addWidget(refresh_btn)

        approve_btn = QPushButton("Схвалити")
        approve_btn.clicked.connect(self._approve_telegram_request)
        approve_btn.setStyleSheet("background-color: #D1FAE5; color: #065F46;")
        req_buttons_layout.addWidget(approve_btn)

        reject_btn = QPushButton("Відхилити")
        reject_btn.clicked.connect(self._reject_telegram_request)
        reject_btn.setStyleSheet("background-color: #FEE2E2; color: #991B1B;")
        req_buttons_layout.addWidget(reject_btn)

        edit_perms_btn = QPushButton("Права доступу")
        edit_perms_btn.clicked.connect(self._edit_telegram_permissions)
        edit_perms_btn.setStyleSheet("background-color: #FEF3C7; color: #92400E;")
        edit_perms_btn.setToolTip("Змінити права доступу для вже схваленого користувача")
        req_buttons_layout.addWidget(edit_perms_btn)

        unlink_btn = QPushButton("Відв'язати")
        unlink_btn.clicked.connect(self._unlink_telegram_request)
        unlink_btn.setStyleSheet("background-color: #fee2e2; color: #b91c1c;")
        unlink_btn.setToolTip("Скасувати прив'язку та забрати права")
        req_buttons_layout.addWidget(unlink_btn)

        req_buttons_layout.addStretch()
        requests_layout.addLayout(req_buttons_layout)

        requests_group.setLayout(requests_layout)
        layout.addWidget(requests_group)

        # Підказка
        help_label = QLabel(
            "<b>Telegram Bot</b> дозволяє управляти документами через Telegram.<br><br>"
            "<b>Режими роботи:</b><br>"
            "• <b>Polling</b> - Простий режим для розробки. Запускається через <code>python run.py --telegram</code><br>"
            "• <b>Webhook</b> - Для продакшн з публічним URL. Запускається через <code>python run.py --telegram-webhook</code><br><br>"
            "<b>Можливості бота (без Mini App):</b><br>"
            "• Перегляд документів та їх статусів<br>"
            "• Підписання/погодження документів<br>"
            "• Управління проблемними документами<br>"
            "• Перегляд профілю<br><br>"
            "<i>Примітка: Сканування доступне тільки через Mini App</i>"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-size: 11px; padding: 10px; background: #f0f0f0; border-radius: 5px;")
        layout.addWidget(help_label)

        layout.addStretch()
        return widget

    def _on_telegram_mode_changed(self, index: int):
        """Обробляє зміну режиму Telegram бота."""
        mode = self.telegram_mode_combo.currentData()
        # Webhook URL field is only relevant in webhook mode
        self.telegram_webhook_input.setEnabled(mode == "webhook")
        if mode == "polling":
            self.telegram_webhook_input.setPlaceholderText("(Не потрібно для режиму Polling)")
        else:
            self.telegram_webhook_input.setPlaceholderText(
                "Webhook URL для отримання оновлень\n"
                "Наприклад: https://your-domain.com/api/telegram/webhook"
            )

    def _load_telegram_requests(self):
        """Завантажує список запитів на підключення."""
        from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
        from sqlalchemy import select
        
        self.telegram_requests_table.setRowCount(0)
        
        filter_idx = self.request_status_filter.currentIndex()
        # 0=Pending, 1=Approved, 2=Rejected, 3=All
        
        with get_db_context() as db:
            query = select(TelegramLinkRequest).order_by(TelegramLinkRequest.created_at.desc())
            
            if filter_idx == 0:
                query = query.where(TelegramLinkRequest.status == LinkRequestStatus.PENDING)
            elif filter_idx == 1:
                query = query.where(TelegramLinkRequest.status == LinkRequestStatus.APPROVED)
            elif filter_idx == 2:
                query = query.where(TelegramLinkRequest.status == LinkRequestStatus.REJECTED)
                
            requests = db.execute(query).scalars().all()
            
            self.telegram_requests_table.setRowCount(len(requests))
            for i, req in enumerate(requests):
                user_item = QTableWidgetItem(f"{req.first_name} {req.last_name or ''}")
                user_item.setData(Qt.ItemDataRole.UserRole, req.id)
                self.telegram_requests_table.setItem(i, 0, user_item)
                
                self.telegram_requests_table.setItem(i, 1, QTableWidgetItem(f"@{req.telegram_username}" if req.telegram_username else "-"))
                
                # Status with color
                status_item = QTableWidgetItem(req.status.value)
                if req.status == LinkRequestStatus.APPROVED:
                    status_item.setBackground(QColor("#d1fae5"))
                elif req.status == LinkRequestStatus.REJECTED:
                    status_item.setBackground(QColor("#fee2e2"))
                elif req.status == LinkRequestStatus.PENDING:
                    status_item.setBackground(QColor("#eff6ff"))
                self.telegram_requests_table.setItem(i, 2, status_item)
                
                self.telegram_requests_table.setItem(i, 3, QTableWidgetItem(req.phone_number or "-"))
                self.telegram_requests_table.setItem(i, 4, QTableWidgetItem(req.created_at.strftime("%Y-%m-%d %H:%M")))

    def _approve_telegram_request(self):
        """Схвалює обраний запит."""
        current_row = self.telegram_requests_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть запит для схвалення")
            return
            
        request_id = self.telegram_requests_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        
        # Dialog to select staff and permissions
        dialog = TelegramApprovalDialog(self, request_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_telegram_requests()
            QMessageBox.information(self, "Успіх", "Запит успішно схвалено")

    def _reject_telegram_request(self):
        """Відхиляє обраний запит."""
        current_row = self.telegram_requests_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть запит для відхилення")
            return
            
        request_id = self.telegram_requests_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        
        reason, ok = QInputDialog.getText(
            self, "Відхилення запиту", 
            "Вкажіть причину відхилення (необов'язково):"
        )
        
        if ok:
            from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
            from sqlalchemy import select
            import asyncio
            from backend.api.routes.telegram import _send_rejection_notification
            
            with get_db_context() as db:
                req = db.execute(
                    select(TelegramLinkRequest).where(TelegramLinkRequest.id == request_id)
                ).scalar_one()
                
                req.status = LinkRequestStatus.REJECTED
                req.rejection_reason = reason
                req.processed_at = datetime.now()
                req.approved_by = "Desktop Admin"
                
                db.commit()
                
                # Try to send notification (this is async, so we just try best effort in desktop)
                # Ideally this should be done via API or properly handled asyncio loop
                try:
                    # Simple fire-and-forget wrapper if we have a running loop, otherwise ignores
                    pass 
                except:
                    pass
            
            self._load_telegram_requests()

    def _unlink_telegram_request(self):
        """Відв'язує користувача."""
        current_row = self.telegram_requests_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть запит для відв'язування")
            return
            
        request_id = self.telegram_requests_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Підтвердження",
            "Ви впевнені, що хочете відв'язати цього користувача?\n"
            "Він втратить доступ до боту.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
        from backend.models.staff import Staff
        from sqlalchemy import select
        
        try:
            with get_db_context() as db:
                req = db.execute(select(TelegramLinkRequest).where(TelegramLinkRequest.id == request_id)).scalar_one()
                
                if req.staff_id:
                    staff = db.execute(select(Staff).where(Staff.id == req.staff_id)).scalar_one_or_none()
                    if staff:
                        staff.telegram_user_id = None
                        staff.telegram_username = None
                        staff.telegram_permissions = None
                
                req.status = LinkRequestStatus.REJECTED
                req.rejection_reason = "Unlinked by admin"
                req.processed_at = datetime.now()

                db.commit()
                QMessageBox.information(self, "Успіх", "Користувача відв'язано.")
                self._load_telegram_requests()
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося відв'язати користувача: {e}")

    def _edit_telegram_permissions(self):
        """Відкриває діалог для зміни прав доступу користувача."""
        current_row = self.telegram_requests_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть запит")
            return

        request_id = self.telegram_requests_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)

        dialog = TelegramPermissionsDialog(self, request_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_telegram_requests()

    def _test_telegram_connection(self):
        """Перевіряє з'єднання з Telegram API."""
        token = self.telegram_token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Увага", "Введіть токен бота")
            return

        try:
            import requests

            # Test bot info
            response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            data = response.json()

            if data.get("ok"):
                bot_info = data["result"]
                message = (
                    f"З'єднання з Telegram встановлено!\n\n"
                    f"Bot: @{bot_info.get('username', 'N/A')}\n"
                    f"Ім'я: {bot_info.get('first_name', 'N/A')}\n"
                    f"ID: {bot_info.get('id', 'N/A')}"
                )
                QMessageBox.information(self, "Успіх", message)
            else:
                error_desc = data.get("description", "Невідома помилка")
                QMessageBox.critical(self, "Помилка", f"Не вдалося підключитися до Telegram:\n{error_desc}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося перевірити з'єднання:\n{e}")

    def _auto_detect_urls(self):
        """Автоматично визначає URL для webhook та Mini App на основі локальної IP адреси."""
        import socket

        # Get local IP address
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            # Fallback to common local IP
            local_ip = "127.0.0.1"

        # Read backend port from settings or use default
        from pathlib import Path
        import json

        port = 8000  # Default port

        # Try to read from .env file
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('VM_PORT='):
                            port = int(line.split('=')[1].strip())
                            break
            except Exception:
                pass

        # Generate URLs
        webhook_url = f"http://{local_ip}:{port}/api/telegram/webhook"
        mini_app_url = f"http://{local_ip}:5173"  # Vite default port

        # Show dialog with URLs
        dialog = QDialog(self)
        dialog.setWindowTitle("Автовизначені URL")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(f"Локальна IP адреса: <b>{local_ip}</b>"))
        layout.addWidget(QLabel(f"Backend порт: <b>{port}</b>"))
        layout.addWidget(QLabel(""))

        # Webhook URL
        webhook_layout = QFormLayout()
        webhook_input = QLineEdit(webhook_url)
        webhook_input.setMinimumWidth(400)
        webhook_layout.addRow("Webhook URL:", webhook_input)
        layout.addLayout(webhook_layout)

        # Mini App URL
        mini_app_layout = QFormLayout()
        mini_app_input = QLineEdit(mini_app_url)
        mini_app_input.setMinimumWidth(400)
        mini_app_layout.addRow("Mini App URL:", mini_app_input)
        layout.addLayout(mini_app_layout)

        # Warning about HTTPS
        warning = QLabel(
            "<b>Увага:</b> Telegram вимагає <b>HTTPS</b> для webhook URL.<br><br>"
            "Для розробки використовуйте:<br>"
            "• <b>ngrok</b>: ngrok http 8000<br>"
            "• <b>Cloudflare Tunnel</b>: cloudflared tunnel<br>"
            "• Інший локальний тунель з HTTPS"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #B91C1C; background: #FEE2E2; padding: 10px; border-radius: 5px;")
        layout.addWidget(warning)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Застосувати")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Скасувати")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply the URLs
            self.telegram_webhook_input.setText(webhook_input.text())
            self.telegram_mini_app_url_input.setText(mini_app_input.text())
            QMessageBox.information(
                self,
                "Успішно",
                "URL оновлено!\n\nДля продакшну не забудьте змінити http:// на https://"
            )


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
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Форма
        form_layout = QFormLayout()

        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("Наприклад: директора ННІ")
        form_layout.addRow("Посада (називний):", self.position_input)

        # Назви ПІБ з кнопкою автогенерації
        name_layout = QHBoxLayout()
        self.name_nom_input = QLineEdit()
        self.name_nom_input.setPlaceholderText(
            "ПІБ у називному відмінку\nНаприклад: Савик Василь Миколайович"
        )
        name_layout.addWidget(self.name_nom_input)

        auto_btn = QPushButton("Оновити")
        auto_btn.setMaximumWidth(40)
        auto_btn.setToolTip("Автоматично перетворити у давальний відмінок")
        auto_btn.clicked.connect(self._auto_generate_dative)
        name_layout.addWidget(auto_btn)

        form_layout.addRow("ПІБ (називний - хто?):", name_layout)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            "ПІБ у давальному відмінку\nНаприклад: Савику Василю Миколайовичу"
        )
        form_layout.addRow("ПІБ (давальний - кому?):", self.name_input)

        self.order_input = QSpinBox()
        self.order_input.setRange(1, 100)
        self.order_input.setValue(1)
        form_layout.addRow("Порядок:", self.order_input)

        layout.addLayout(form_layout)

        # Підказка
        help_label = QLabel(
            "<b>Давальний відмінок</b> - для шапки документів (кому?): «директору <b>Іванову</b>»<br><br>"
            "<b>Називний відмінок</b> - для розділу «Погоджено» (хто?): «<b>Іванов</b> І.І.»<br><br>"
            "Натисніть Оновити щоб автоматично перетворити називний у давальний"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic; padding: 10px; background: #f0f0f0; border-radius: 5px;")
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
            self.name_nom_input.setText(self.approver.full_name_nom or "")
            self.order_input.setValue(self.approver.order_index)

    def _auto_generate_dative(self):
        """Автоматично перетворює називний відмінок у давальний."""
        nominative = self.name_nom_input.text().strip()
        if not nominative:
            return

        try:
            from backend.services.grammar_service import GrammarService
            grammar = GrammarService()
            dative = grammar.to_dative(nominative)
            self.name_input.setText(dative)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Помилка",
                f"Не вдалося перетворити ім'я: {e}\n\n"
                "Будь ласка, введіть давальний відмінок вручну."
            )


class PositionSelectionDialog(QDialog):
    """Діалог для вибору посади зі списку."""

    def __init__(self, parent):
        """
        Ініціалізує діалог вибору посади.

        Args:
            parent: Батьківський віджет
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("Оберіть посаду")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Список посад
        layout.addWidget(QLabel("Оберіть посаду зі списку:"))

        self.positions_list = QListWidget()
        self.positions_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.positions_list)

        # Заповнюємо список
        parent = self.parent()
        if hasattr(parent, '_all_positions'):
            for position in parent._all_positions:
                self.positions_list.addItem(position)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_position(self) -> str | None:
        """Повертає обрану посаду."""
        current_item = self.positions_list.currentItem()
        if current_item:
            return current_item.text()
        return None


class TelegramApprovalDialog(QDialog):
    """Діалог для схвалення запиту на прив'язку Telegram."""

    def __init__(self, parent, request_id: int):
        super().__init__(parent)
        self.request_id = request_id
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("Схвалення запиту")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Інфо про користувача
        self.user_info = QLabel("Завантаження...")
        self.user_info.setStyleSheet("background: #f0f9ff; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.user_info)

        # Вибір співробітника
        staff_group = QGroupBox("Прив'язати до співробітника")
        staff_layout = QFormLayout()

        self.staff_combo = QComboBox()
        self.staff_combo.setEditable(True)
        staff_layout.addRow("Співробітник:", self.staff_combo)
        
        staff_group.setLayout(staff_layout)
        layout.addWidget(staff_group)

        # Права доступу
        perm_group = QGroupBox("Права доступу та дозволи")
        perm_layout = QVBoxLayout()

        self.perm_view_docs = QCheckBox("Перегляд своїх документів")
        self.perm_view_docs.setChecked(True)
        self.perm_view_docs.setEnabled(False) # Always required
        perm_layout.addWidget(self.perm_view_docs)

        self.perm_sign_docs = QCheckBox("Підписання/Погодження документів")
        perm_layout.addWidget(self.perm_sign_docs)

        self.perm_view_stale = QCheckBox("Перегляд застарілих документів")
        perm_layout.addWidget(self.perm_view_stale)

        self.perm_manage_stale = QCheckBox("Управління застарілими документами")
        perm_layout.addWidget(self.perm_manage_stale)

        # Admin access - separated visually
        perm_layout.addWidget(QLabel(""))
        admin_separator = QLabel("─" * 30)
        admin_separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        perm_layout.addWidget(admin_separator)

        self.perm_view_all = QCheckBox("<b>Адміністративний доступ</b> - перегляд документів усіх співробітників")
        self.perm_view_all.setToolTip("Дозволяє переглядати документи будь-якого співробітника через команду /search у Telegram боті")
        perm_layout.addWidget(self.perm_view_all)

        perm_group.setLayout(perm_layout)
        layout.addWidget(perm_group)
        
        # Повідомлення про відправку
        layout.addWidget(QLabel("Користувач отримає повідомлення про схвалення та перелік своїх прав."))

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self):
        """Завантажує дані запиту та список співробітників."""
        from backend.models.telegram_link_request import TelegramLinkRequest
        from backend.models.staff import Staff
        from sqlalchemy import select
        
        with get_db_context() as db:
            # Load request
            self.request = db.execute(
                select(TelegramLinkRequest).where(TelegramLinkRequest.id == self.request_id)
            ).scalar_one()
            
            self.user_info.setText(
                f"<b>{self.request.first_name} {self.request.last_name or ''}</b>\n"
                f"Телефон: {self.request.phone_number or 'Без телефону'}\n"
                f"@{self.request.telegram_username or '---'}"
            )
            
            # Load staff list
            staff_list = db.execute(
                select(Staff).where(Staff.is_active == True).order_by(Staff.pib_nom)
            ).scalars().all()
            
            for s in staff_list:
                # Mark already linked staff
                linked = f" (вже має Telegram: {s.telegram_user_id})" if s.telegram_user_id else ""
                self.staff_combo.addItem(f"{s.pib_nom} - {s.position}{linked}", s.id)
                
            # Try to auto-select if phone match or name similarity (simple check)
            # This is a basic implementation, can be improved
            
    def _accept(self):
        """Обробляє схвалення."""
        import json
        from datetime import datetime
        from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
        from backend.models.staff import Staff
        from sqlalchemy import select
        from backend.api.routes.telegram import _send_approval_notification
        import asyncio

        staff_id = self.staff_combo.currentData()
        if not staff_id:
            QMessageBox.warning(self, "Увага", "Оберіть співробітника")
            return

        permissions = ["view_documents"]
        if self.perm_sign_docs.isChecked(): permissions.append("sign_documents")
        if self.perm_view_stale.isChecked(): permissions.append("view_stale")
        if self.perm_manage_stale.isChecked(): permissions.append("manage_stale")
        if self.perm_view_all.isChecked(): permissions.append("view_all_documents")

        try:
            with get_db_context() as db:
                staff = db.execute(select(Staff).where(Staff.id == staff_id)).scalar_one()
                req = db.execute(select(TelegramLinkRequest).where(TelegramLinkRequest.id == self.request_id)).scalar_one()
                
                # Check if staff already linked to different ID
                if staff.telegram_user_id and staff.telegram_user_id != req.telegram_user_id:
                    reply = QMessageBox.question(
                        self, "Підтвердження",
                        f"Співробітник {staff.pib_nom} вже прив'язаний до іншого Telegram ID!\n"
                        f"Перезаписати прив'язку?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return

                # Update stats
                staff.telegram_user_id = req.telegram_user_id
                staff.telegram_username = req.telegram_username
                staff.telegram_permissions = json.dumps(permissions)
                
                req.status = LinkRequestStatus.APPROVED
                req.staff_id = staff_id
                req.processed_at = datetime.now()
                req.approved_by = "Desktop Admin"
                
                db.commit()

                # Notify user using direct HTTP request to Telegram API (sync)
                try:
                    import requests
                    # Access token from parent settings dialog
                    parent_dialog = self.parent()
                    token = parent_dialog.telegram_token_input.text().strip()
                    
                    if token:
                        permission_labels = {
                            "view_documents": "Перегляд документів",
                            "sign_documents": "Підписання документів",
                            "view_stale": "Перегляд застарілих",
                            "manage_stale": "Управління застарілими",
                        }
                        perm_text = "\n".join(f"• {permission_labels.get(p, p)}" for p in permissions)
                        
                        msg = (
                            f"<b>Вітаємо, {staff.pib_nom}!</b>\n\n"
                            f"Ваш Telegram акаунт успішно прив'язано до системи VacationManager.\n\n"
                            f"<b>Ваша посада:</b> {staff.position}\n"
                            f"Підрозділ: {staff.department or 'Не вказано'}\n\n"
                            f"<b>Ваші права доступу:</b>\n{perm_text}"
                        )
                        
                        requests.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={
                                "chat_id": req.telegram_user_id,
                                "text": msg,
                                "parse_mode": "HTML"
                            },
                            timeout=5
                        )
                except Exception as e:
                    print(f"Failed to send telegram notification: {e}")

                QMessageBox.information(
                    self, "Успіх",
                    f"Користувача {req.first_name} успішно прив'язано до {staff.pib_nom}!"
                )
                self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти зміни: {e}")


class TelegramPermissionsDialog(QDialog):
    """Діалог для зміни прав доступу Telegram користувача."""

    def __init__(self, parent, request_id: int):
        super().__init__(parent)
        self.request_id = request_id
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("Змінити права доступу")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Інфо про користувача
        self.user_info = QLabel("Завантаження...")
        self.user_info.setStyleSheet("background: #f0f9ff; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.user_info)

        # Права доступу
        perm_group = QGroupBox("🔐 Права доступу")
        perm_layout = QVBoxLayout()

        self.perm_view_docs = QCheckBox("Перегляд своїх документів")
        self.perm_view_docs.setChecked(True)
        self.perm_view_docs.setEnabled(False)  # Always required
        perm_layout.addWidget(self.perm_view_docs)

        self.perm_sign_docs = QCheckBox("Підписання/Погодження документів")
        perm_layout.addWidget(self.perm_sign_docs)

        self.perm_view_stale = QCheckBox("Перегляд застарілих документів")
        perm_layout.addWidget(self.perm_view_stale)

        self.perm_manage_stale = QCheckBox("Управління застарілими документами")
        perm_layout.addWidget(self.perm_manage_stale)

        # Admin access
        perm_layout.addWidget(QLabel(""))
        admin_separator = QLabel("─" * 30)
        admin_separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        perm_layout.addWidget(admin_separator)

        self.perm_view_all = QCheckBox("<b>Адміністративний доступ</b>")
        self.perm_view_all.setToolTip("Дозволяє переглядати документи будь-якого співробітника через команду /search")
        perm_layout.addWidget(self.perm_view_all)

        perm_group.setLayout(perm_layout)
        layout.addWidget(perm_group)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self):
        """Завантажує поточні права доступу."""
        import json
        from sqlalchemy import select
        from backend.models.telegram_link_request import TelegramLinkRequest
        from backend.models.staff import Staff

        with get_db_context() as db:
            # Load request
            req = db.execute(
                select(TelegramLinkRequest).where(TelegramLinkRequest.id == self.request_id)
            ).scalar_one()

            # Load linked staff
            staff = db.execute(
                select(Staff).where(Staff.id == req.staff_id)
            ).scalar_one_or_none()

            if not staff:
                self.user_info.setText("❌ Співробітника не знайдено")
                return

            self.staff = staff
            self.user_info.setText(
                f"<b>{staff.pib_nom}</b>\n"
                f"📋 {staff.position}\n"
                f"📱 Telegram ID: {staff.telegram_user_id}"
            )

            # Load current permissions
            try:
                permissions = json.loads(staff.telegram_permissions) if staff.telegram_permissions else []
            except:
                permissions = []

            self.perm_view_docs.setChecked("view_documents" in permissions)
            self.perm_sign_docs.setChecked("sign_documents" in permissions)
            self.perm_view_stale.setChecked("view_stale" in permissions)
            self.perm_manage_stale.setChecked("manage_stale" in permissions)
            self.perm_view_all.setChecked("view_all_documents" in permissions)

    def _save(self):
        """Зберігає нові права доступу."""
        import json
        from sqlalchemy import select
        from backend.models.staff import Staff

        permissions = ["view_documents"]
        if self.perm_sign_docs.isChecked(): permissions.append("sign_documents")
        if self.perm_view_stale.isChecked(): permissions.append("view_stale")
        if self.perm_manage_stale.isChecked(): permissions.append("manage_stale")
        if self.perm_view_all.isChecked(): permissions.append("view_all_documents")

        try:
            with get_db_context() as db:
                staff = db.execute(select(Staff).where(Staff.id == self.staff.id)).scalar_one()
                staff.telegram_permissions = json.dumps(permissions)
                db.commit()

            QMessageBox.information(self, "Успіх", "Права доступу оновлено!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося оновити права: {e}")


class SQLQueryBuilderDialog(QDialog):
    """Діалог для візуального конструювання SQL запитів."""


    def __init__(self, parent=None):
        super().__init__(parent)
        self.conditions = []
        self._tables = self._get_tables()
        self._setup_ui()

    def _get_tables(self) -> list[str]:
        """Отримує список таблиць з бази даних."""
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).parent.parent.parent / "vacation_manager.db"
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_%' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except:
            return ["attendance", "staff", "documents", "tabel_approval", "settings"]

    def _get_columns(self, table: str) -> list[str]:
        """Отримує список стовпців для таблиці."""
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).parent.parent.parent / "vacation_manager.db"
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            conn.close()
            return columns
        except:
            return ["id"]

    def _setup_ui(self):
        self.setWindowTitle("Конструктор SQL запитів")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # Query type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Тип запиту:"))
        self.query_type = QComboBox()
        self.query_type.addItems(["SELECT", "UPDATE", "DELETE"])
        self.query_type.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.query_type)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # Table selector
        table_layout = QHBoxLayout()
        table_layout.addWidget(QLabel("Таблиця:"))
        self.table_combo = QComboBox()
        self.table_combo.addItems(self._tables)
        self.table_combo.currentTextChanged.connect(self._on_table_changed)
        table_layout.addWidget(self.table_combo)
        table_layout.addStretch()
        layout.addLayout(table_layout)

        # Columns group (for SELECT)
        self.columns_group = QGroupBox("Стовпці (SELECT)")
        columns_layout = QVBoxLayout()
        self.select_all_checkbox = QCheckBox("Всі стовпці (*)")
        self.select_all_checkbox.setChecked(True)
        self.select_all_checkbox.toggled.connect(self._on_select_all_toggled)
        columns_layout.addWidget(self.select_all_checkbox)
        
        self.columns_list = QListWidget()
        self.columns_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.columns_list.setMaximumHeight(100)
        columns_layout.addWidget(self.columns_list)
        self.columns_group.setLayout(columns_layout)
        layout.addWidget(self.columns_group)

        # SET group (for UPDATE)
        self.set_group = QGroupBox("SET (оновити значення)")
        set_layout = QHBoxLayout()
        self.set_column = QComboBox()
        set_layout.addWidget(self.set_column)
        set_layout.addWidget(QLabel("="))
        self.set_value = QLineEdit()
        self.set_value.setPlaceholderText("Нове значення")
        set_layout.addWidget(self.set_value)
        self.set_group.setLayout(set_layout)
        self.set_group.hide()
        layout.addWidget(self.set_group)

        # WHERE conditions
        where_group = QGroupBox("WHERE (умови)")
        where_layout = QVBoxLayout()

        # Conditions list
        self.conditions_widget = QWidget()
        self.conditions_layout = QVBoxLayout(self.conditions_widget)
        self.conditions_layout.setContentsMargins(0, 0, 0, 0)
        where_layout.addWidget(self.conditions_widget)

        # Add condition button
        add_cond_btn = QPushButton("Додати умову")
        add_cond_btn.clicked.connect(self._add_condition)
        where_layout.addWidget(add_cond_btn)

        where_group.setLayout(where_layout)
        layout.addWidget(where_group)

        # ORDER BY and LIMIT
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("ORDER BY:"))
        self.order_combo = QComboBox()
        self.order_combo.addItem("(немає)")
        options_layout.addWidget(self.order_combo)
        
        self.order_dir = QComboBox()
        self.order_dir.addItems(["DESC", "ASC"])
        options_layout.addWidget(self.order_dir)

        options_layout.addWidget(QLabel("LIMIT:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 10000)
        self.limit_spin.setValue(100)
        self.limit_spin.setSpecialValueText("(без ліміту)")
        options_layout.addWidget(self.limit_spin)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Preview
        preview_group = QGroupBox("Попередній перегляд запиту")
        preview_layout = QVBoxLayout()
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(80)
        self.preview_text.setStyleSheet("font-family: monospace; background: #f5f5f5;")
        preview_layout.addWidget(self.preview_text)
        
        refresh_btn = QPushButton("Оновити перегляд")
        refresh_btn.clicked.connect(self._update_preview)
        preview_layout.addWidget(refresh_btn)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # Raw SQL mode
        self.raw_checkbox = QCheckBox("Редагувати SQL напряму")
        self.raw_checkbox.toggled.connect(self._on_raw_toggled)
        layout.addWidget(self.raw_checkbox)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Виконати")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Initialize
        self._on_table_changed(self.table_combo.currentText())
        self._update_preview()

    def _on_type_changed(self, query_type: str):
        """Обробляє зміну типу запиту."""
        self.columns_group.setVisible(query_type == "SELECT")
        self.set_group.setVisible(query_type == "UPDATE")
        self._update_preview()

    def _on_table_changed(self, table: str):
        """Оновлює список стовпців при зміні таблиці."""
        columns = self._get_columns(table)
        
        self.columns_list.clear()
        self.set_column.clear()
        self.order_combo.clear()
        self.order_combo.addItem("(немає)")
        
        for col in columns:
            self.columns_list.addItem(col)
            self.set_column.addItem(col)
            self.order_combo.addItem(col)

        # Update conditions
        for cond in self.conditions:
            cond["column"].clear()
            for col in columns:
                cond["column"].addItem(col)

        self._update_preview()

    def _on_select_all_toggled(self, checked: bool):
        self.columns_list.setEnabled(not checked)
        self._update_preview()

    def _on_raw_toggled(self, checked: bool):
        self.preview_text.setReadOnly(not checked)
        if checked:
            self.preview_text.setStyleSheet("font-family: monospace; background: white;")
        else:
            self.preview_text.setStyleSheet("font-family: monospace; background: #f5f5f5;")

    def _add_condition(self):
        """Додає нову умову WHERE."""
        cond_widget = QWidget()
        cond_layout = QHBoxLayout(cond_widget)
        cond_layout.setContentsMargins(0, 0, 0, 0)

        # Connector (AND/OR)
        connector = QComboBox()
        connector.addItems(["AND", "OR"])
        connector.setMaximumWidth(60)
        if not self.conditions:
            connector.hide()
        cond_layout.addWidget(connector)

        # Column
        column = QComboBox()
        columns = self._get_columns(self.table_combo.currentText())
        for col in columns:
            column.addItem(col)
        cond_layout.addWidget(column)

        # Operator
        operator = QComboBox()
        operator.addItems(["=", "!=", ">", "<", ">=", "<=", "LIKE", "IS NULL", "IS NOT NULL"])
        operator.currentTextChanged.connect(lambda: self._on_operator_changed(operator, value))
        cond_layout.addWidget(operator)

        # Value
        value = QLineEdit()
        value.setPlaceholderText("Значення")
        cond_layout.addWidget(value)

        # Remove button
        remove_btn = QPushButton("❌")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda: self._remove_condition(cond_widget))
        cond_layout.addWidget(remove_btn)

        self.conditions.append({
            "widget": cond_widget,
            "connector": connector,
            "column": column,
            "operator": operator,
            "value": value,
        })
        self.conditions_layout.addWidget(cond_widget)
        self._update_preview()

    def _on_operator_changed(self, operator: QComboBox, value: QLineEdit):
        """Ховає поле значення для IS NULL/IS NOT NULL."""
        op = operator.currentText()
        value.setVisible(op not in ("IS NULL", "IS NOT NULL"))

    def _remove_condition(self, widget: QWidget):
        """Видаляє умову."""
        self.conditions = [c for c in self.conditions if c["widget"] != widget]
        widget.deleteLater()
        # Show/hide first connector
        if self.conditions:
            self.conditions[0]["connector"].hide()
        self._update_preview()

    def _update_preview(self):
        """Оновлює текст попереднього перегляду."""
        if self.raw_checkbox.isChecked():
            return

        query = self._build_query()
        self.preview_text.setPlainText(query)

    def _build_query(self) -> str:
        """Будує SQL запит з налаштувань."""
        query_type = self.query_type.currentText()
        table = self.table_combo.currentText()

        if query_type == "SELECT":
            if self.select_all_checkbox.isChecked():
                columns = "*"
            else:
                selected = [item.text() for item in self.columns_list.selectedItems()]
                columns = ", ".join(selected) if selected else "*"
            query = f"SELECT {columns} FROM {table}"

        elif query_type == "UPDATE":
            column = self.set_column.currentText()
            value = self.set_value.text()
            # Format value
            if value.lower() in ("null", "true", "false") or value.isdigit():
                formatted_value = value
            else:
                formatted_value = f"'{value}'"
            query = f"UPDATE {table} SET {column} = {formatted_value}"

        else:  # DELETE
            query = f"DELETE FROM {table}"

        # WHERE
        if self.conditions:
            where_parts = []
            for i, cond in enumerate(self.conditions):
                col = cond["column"].currentText()
                op = cond["operator"].currentText()
                val = cond["value"].text()

                if op in ("IS NULL", "IS NOT NULL"):
                    part = f"{col} {op}"
                elif val.lower() in ("null", "true", "false") or val.isdigit():
                    part = f"{col} {op} {val}"
                else:
                    part = f"{col} {op} '{val}'"

                if i > 0:
                    conn = cond["connector"].currentText()
                    part = f"{conn} {part}"

                where_parts.append(part)

            query += " WHERE " + " ".join(where_parts)

        # ORDER BY (only for SELECT)
        if query_type == "SELECT":
            order_col = self.order_combo.currentText()
            if order_col != "(немає)":
                query += f" ORDER BY {order_col} {self.order_dir.currentText()}"

            # LIMIT
            limit = self.limit_spin.value()
            if limit > 0:
                query += f" LIMIT {limit}"

        return query

    def get_query(self) -> str:
        """Повертає готовий SQL запит."""
        if self.raw_checkbox.isChecked():
            return self.preview_text.toPlainText().strip()
        return self._build_query()

