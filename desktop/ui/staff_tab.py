"""Вкладка управління персоналом."""

from datetime import date

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QDialog,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
    QDateEdit,
    QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from desktop.widgets.status_badge import StatusBadge
from desktop.ui.employee_card_dialog import EmployeeCardDialog
from shared.enums import EmploymentType, WorkBasis


class StaffTab(QWidget):
    """
    Вкладка для управління списком співробітників.

    Містить таблицю персоналу з можливістю додавання,
    редагування та перегляду деталей.
    """

    document_created = pyqtSignal()

    def __init__(self):
        """Ініціалізує вкладку персоналу."""
        super().__init__()
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        layout = QVBoxLayout(self)

        # Панель пошуку та фільтрів
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Пошук за ПІБ...")
        self.search_input.textChanged.connect(self._on_search)

        self.filter_active = QComboBox()
        self.filter_active.addItems(["Всі", "Активні", "Неактивні"])
        self.filter_active.currentIndexChanged.connect(self._load_data)

        self.refresh_btn = QPushButton("Оновити")
        self.refresh_btn.clicked.connect(self._load_data)

        search_layout.addWidget(QLabel("Пошук:"))
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(QLabel("Фільтр:"))
        search_layout.addWidget(self.filter_active)
        search_layout.addWidget(self.refresh_btn)
        search_layout.addStretch()

        layout.addLayout(search_layout)

        # Таблиця
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Заборонити редагування
        self.table.setHorizontalHeaderLabels([
            "ПІБ",
            "Посада",
            "Ставка",
            "Тип",
            "Контракт",
            "Баланс",
            "Дні до кінця",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Кнопки дій
        actions_layout = QHBoxLayout()

        self.add_btn = QPushButton("Додати")
        self.add_btn.clicked.connect(self._add_staff)

        self.all_cards_btn = QPushButton("📚 Всі картки")
        self.all_cards_btn.clicked.connect(self._show_all_cards)

        actions_layout.addWidget(self.add_btn)
        actions_layout.addWidget(self.all_cards_btn)
        actions_layout.addStretch()

        layout.addLayout(actions_layout)

        # Контекстне меню на правий клік
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Підключення сигналів таблиці
        self.table.itemDoubleClicked.connect(self._show_employee_card)

    def _load_data(self):
        """Завантажує дані в таблицю."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            query = db.query(Staff)

            # Фільтр активності
            filter_idx = self.filter_active.currentIndex()
            if filter_idx == 1:  # Активні
                query = query.filter(Staff.is_active == True)
            elif filter_idx == 2:  # Неактивні
                query = query.filter(Staff.is_active == False)

            all_staff = query.order_by(Staff.pib_nom, Staff.id.desc()).all()

            # Групуємо по pib_nom - показуємо тільки останній запис для кожного
            latest_staff = {}
            for staff in all_staff:
                if staff.pib_nom not in latest_staff:
                    latest_staff[staff.pib_nom] = staff

            staff_list = list(latest_staff.values())
            # Сортуємо за ПІБ
            staff_list.sort(key=lambda s: s.pib_nom)

            self.table.setRowCount(len(staff_list))

            for row, staff in enumerate(staff_list):
                self._set_row_data(row, staff)

    def _set_row_data(self, row: int, staff):
        """Встановлює дані в рядок таблиці."""
        from backend.models.settings import SystemSettings

        # Отримуємо поріг попередження з налаштувань
        warning_days = 30  # За замовчуванням
        try:
            with get_db_context() as db:
                warning_days = SystemSettings.get_value(db, "contract_warning_days", 30)
        except Exception:
            pass

        # ПІБ - з іконкою попередження якщо контракт закінчується
        name_text = staff.pib_nom
        if staff.is_term_expired:
            name_text = "⚠️ " + name_text
        elif staff.days_until_term_end <= warning_days:
            name_text = "⏰ " + name_text

        self.table.setItem(row, 0, QTableWidgetItem(name_text))
        self.table.setItem(row, 1, QTableWidgetItem(staff.position))
        self.table.setItem(row, 2, QTableWidgetItem(str(staff.rate)))
        self.table.setItem(row, 3, QTableWidgetItem(staff.employment_type.value))

        term_item = QTableWidgetItem(
            f"{staff.term_start.strftime('%d.%m.%Y')} - "
            f"{staff.term_end.strftime('%d.%m.%Y')}"
        )
        self.table.setItem(row, 4, term_item)

        balance_item = QTableWidgetItem(str(staff.vacation_balance))
        self.table.setItem(row, 5, balance_item)

        # Дні до кінця контракту з підсвіткою
        days_text = str(staff.days_until_term_end)
        if staff.is_term_expired:
            days_text = f"⛔ {days_text}"
        elif staff.days_until_term_end <= warning_days:
            days_text = f"⚠️ {days_text}"

        days_item = QTableWidgetItem(days_text)

        # Підсвітка рядка червоним якщо контракт закінчується
        if staff.is_term_expired:
            for col in range(7):
                item = QTableWidgetItem() if col != 0 else self.table.item(row, 0)
                if col != 0:
                    self.table.setItem(row, col, item)
                item.setBackground(QColor("#FFCCCC"))
        elif staff.days_until_term_end <= warning_days:
            # Тільки days_item підсвітчуємо
            days_item.setBackground(QColor("#FFEBEE"))
            days_item.setForeground(QColor("#D32F2F"))

        self.table.setItem(row, 6, days_item)

        # Зберігаємо ID в першому елементі
        self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, staff.id)

    def _on_search(self):
        """Фільтрує дані при пошуку."""
        search_text = self.search_input.text().lower()

        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            match = search_text in name
            self.table.setRowHidden(row, not match)

    def _on_selection_changed(self):
        """Обробляє зміну виділення."""
        pass  # Більше не потрібно без кнопок

    def _show_context_menu(self, pos):
        """Показує контекстне меню на правий клік."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QCursor

        # Отримуємо рядок під курсором
        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        self.table.selectRow(row)

        # Створюємо меню
        menu = QMenu(self)

        edit_action = menu.addAction("✏️ Редагувати")

        # Підменю для видалення
        delete_menu = menu.addMenu("🗑️ Видалити")
        soft_delete_action = delete_menu.addAction("Деактивувати")
        hard_delete_action = delete_menu.addAction("Видалити назавжди")

        menu.addSeparator()
        docs_action = menu.addAction("📄 Документи")
        card_action = menu.addAction("📋 Картка")

        # Отримуємо позицію курсору та показуємо меню
        cursor_pos = QCursor.pos()
        action = menu.exec(cursor_pos)

        # Обробляємо вибір
        if action == edit_action:
            self._edit_staff()
        elif action == soft_delete_action:
            self._soft_delete_staff()
        elif action == hard_delete_action:
            self._hard_delete_staff()
        elif action == docs_action:
            self._view_documents()
        elif action == card_action:
            self._show_employee_card()

    def _add_staff(self):
        """Відкриває діалог додавання співробітника."""
        dialog = StaffDialog(parent=self)
        if dialog.exec():
            self._load_data()

    def _edit_staff(self):
        """Відкриває діалог редагування співробітника."""
        item = self.table.currentItem()
        if not item:
            return

        staff_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        dialog = StaffDialog(staff_id, parent=self)
        if dialog.exec():
            self._load_data()

    def _soft_delete_staff(self):
        """Деактивує співробітника (soft delete)."""
        from backend.models.staff import Staff
        from backend.models.document import Document
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService
        from PyQt6.QtWidgets import QMessageBox
        from shared.enums import DocumentStatus

        item = self.table.currentItem()
        if not item:
            return

        staff_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

        with get_db_context() as db:
            # Перевіряємо наявність документів
            documents = (
                db.query(Document)
                .filter(Document.staff_id == staff_id)
                .all()
            )

            # Кількість неархівованих документів
            non_archived = [d for d in documents if d.status != DocumentStatus.PROCESSED]

            if non_archived:
                doc_info = "\n".join([
                    f"  - {d.doc_type.value}: {d.date_start} - {d.date_end} ({d.status.value})"
                    for d in non_archived[:5]
                ])
                if len(non_archived) > 5:
                    doc_info += f"\n  ... та ще {len(non_archived) - 5} документів"

                QMessageBox.warning(
                    self,
                    "Неможливо видалити",
                    f"Неможливо видалити співробітника, оскільки є "
                    f"{len(non_archived)} незавершених документів:\n\n{doc_info}\n\n"
                    f"Спочатку архівуйте або видаліть ці документи."
                )
                return

            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff:
                QMessageBox.warning(self, "Помилка", "Співробітника не знайдено")
                return

            reply = QMessageBox.question(
                self,
                "Підтвердження",
                f"Деактивувати {staff.pib_nom}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    service = StaffService(db, changed_by="USER")
                    service.deactivate_staff(staff, reason="Видалено користувачем")
                    self.filter_active.setCurrentIndex(1)  # 1 = Активні
                    self._load_data()
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося деактивувати: {e}")

    def _hard_delete_staff(self):
        """Повністю видаляє співробітника (hard delete)."""
        from backend.models.staff import Staff
        from backend.models.document import Document
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService
        from PyQt6.QtWidgets import QMessageBox
        from shared.enums import DocumentStatus

        item = self.table.currentItem()
        if not item:
            return

        staff_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

        with get_db_context() as db:
            # Перевіряємо наявність документів
            documents = (
                db.query(Document)
                .filter(Document.staff_id == staff_id)
                .all()
            )

            # Кількість неархівованих документів
            non_archived = [d for d in documents if d.status != DocumentStatus.PROCESSED]

            if non_archived:
                doc_info = "\n".join([
                    f"  - {d.doc_type.value}: {d.date_start} - {d.date_end} ({d.status.value})"
                    for d in non_archived[:5]
                ])
                if len(non_archived) > 5:
                    doc_info += f"\n  ... та ще {len(non_archived) - 5} документів"

                QMessageBox.warning(
                    self,
                    "Неможливо видалити",
                    f"Неможливо видалити співробітника, оскільки є "
                    f"{len(non_archived)} незавершених документів:\n\n{doc_info}\n\n"
                    f"Спочатку архівуйте або видаліть ці документи."
                )
                return

            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff:
                QMessageBox.warning(self, "Помилка", "Співробітника не знайдено")
                return

            confirm = QMessageBox.warning(
                self,
                "ОСТОРОЖНО!",
                f"Ви впевнені, що хочете назавжди видалити {staff.pib_nom}?\n\n"
                "ЦЯ ДІЯ НЕЗВОРОТНЯ! Всі дані та історія будуть втрачені.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    service = StaffService(db, changed_by="USER")
                    service.hard_delete_staff(staff)
                    self._load_data()
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося видалити: {e}")

    def _delete_staff(self):
        """Видаляє співробітника (застарілий метод, використовуйте soft/hard)."""
        self._soft_delete_staff()

    def _view_documents(self):
        """Відкриває список документів співробітника."""
        # TODO: Реалізувати перегляд документів
        pass

    def _show_employee_card(self):
        """Відкриває картку працівника."""
        item = self.table.currentItem()
        if not item:
            return

        staff_id = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        dialog = EmployeeCardDialog(staff_id, parent=self)
        if dialog.exec():
            self._load_data()

    def _show_all_cards(self):
        """Відкриває діалог з усіма картками працівників."""
        from backend.core.database import get_db_context
        from backend.models.staff import Staff
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt

        # Завантажуємо дані перед створенням діалогу
        def load_staff_data():
            with get_db_context() as db:
                # Отримуємо всі записи, групуємо по pib_nom і беремо останній для кожного
                staff_list = db.query(Staff).order_by(Staff.pib_nom, Staff.id.desc()).all()

                # Словник для зберігання останнього запису для кожного pib_nom
                latest_staff = {}
                for staff in staff_list:
                    if staff.pib_nom not in latest_staff:
                        latest_staff[staff.pib_nom] = staff

                # Конвертуємо в список даних
                staff_data_list = []
                for staff in latest_staff.values():
                    staff_data_list.append({
                        "id": staff.id,
                        "pib_nom": staff.pib_nom,
                        "position": staff.position,
                        "is_active": staff.is_active,
                        "term_start": staff.term_start,
                        "term_end": staff.term_end,
                        "vacation_balance": staff.vacation_balance,
                        "days_until_term_end": staff.days_until_term_end,
                        "is_term_expired": staff.days_until_term_end < 0,
                    })
                return staff_data_list

        staff_data_list = load_staff_data()

        dialog = QDialog(self)
        dialog.setWindowTitle("Всі картки працівників")
        dialog.setMinimumSize(1200, 600)

        layout = QVBoxLayout(dialog)

        # Таблиця всіх співробітників
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            "ID",
            "ПІБ",
            "Посада",
            "Статус",
            "Контракт",
            "Баланс",
            "Дні до кінця",
        ])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Заборонити редагування

        # Функція для заповнення таблиці
        def populate_table(data_list):
            table.setRowCount(len(data_list))
            for row, staff in enumerate(data_list):
                # ID
                id_item = QTableWidgetItem(str(staff["id"]))
                id_item.setData(Qt.ItemDataRole.UserRole, staff["id"])
                table.setItem(row, 0, id_item)

                # ПІБ
                table.setItem(row, 1, QTableWidgetItem(staff["pib_nom"]))

                # Посада
                table.setItem(row, 2, QTableWidgetItem(staff["position"]))

                # Статус
                status_text = "✅ Активний" if staff["is_active"] else "❌ Неактивний"
                status_item = QTableWidgetItem(status_text)
                if not staff["is_active"]:
                    status_item.setBackground(QColor("#FFCDD2"))
                table.setItem(row, 3, status_item)

                # Контракт
                term_item = QTableWidgetItem(
                    f"{staff['term_start'].strftime('%d.%m.%Y')} - "
                    f"{staff['term_end'].strftime('%d.%m.%Y')}"
                )
                table.setItem(row, 4, term_item)

                # Баланс
                table.setItem(row, 5, QTableWidgetItem(str(staff["vacation_balance"])))

                # Дні до кінця
                days_text = str(staff["days_until_term_end"])
                if staff["is_term_expired"]:
                    days_text = f"⛔ {days_text}"
                elif staff["days_until_term_end"] <= 30:
                    days_text = f"⚠️ {days_text}"
                table.setItem(row, 6, QTableWidgetItem(days_text))

        # Заповнюємо таблицю початковими даними
        populate_table(staff_data_list)

        # Функція для оновлення таблиці
        def refresh_table():
            new_data = load_staff_data()
            populate_table(new_data)

        # Двійний клік відкриває картку
        def on_double_click(item):
            staff_id = table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
            card_dialog = EmployeeCardDialog(staff_id, dialog)
            # Після закриття картки оновлюємо таблицю
            card_dialog.exec()
            refresh_table()

        table.itemDoubleClicked.connect(on_double_click)

        layout.addWidget(QLabel("<b>Двійний клік для перегляду картки працівника</b>"))
        layout.addWidget(table)

        # Кнопка закриття
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("Закрити")
        close_btn.clicked.connect(dialog.accept)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

        dialog.exec()

    def refresh_documents(self):
        """Оновлює список документів (слот для сигналу)."""
        # TODO: Оновити список документів
        pass

    def refresh(self):
        """Оновлює дані вкладки."""
        self._load_data()


class StaffDialog(QDialog):
    """Діалог для створення/редагування співробітника."""

    def __init__(self, staff_id: int | None = None, parent=None):
        """Ініціалізує діалог."""
        super().__init__(parent)
        self.staff_id = staff_id
        self._setup_ui()
        if staff_id:
            self._load_data()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("Співробітник" if self.staff_id is None else "Редагування")
        self.setMinimumWidth(500)

        layout = QFormLayout(self)

        self.pib_input = QLineEdit()
        self.pib_input.setPlaceholderText("Прізвище Ім'я По батькові")
        self.degree_input = QLineEdit()

        # Посада - dropdown with predefined values
        self.position_input = QComboBox()
        self.position_input.setEditable(True)
        self.position_input.addItems([
            "Завідувач кафедри",
            "В.о завідувача кафедри",
            "професор",
            "доцент",
            "ст. викладач",
            "асистент",
            "фахівець",
        ])

        # Ставка - from 1.0 to 0.1 with step 0.1
        self.rate_input = QDoubleSpinBox()
        self.rate_input.setRange(0.1, 1.0)
        self.rate_input.setSingleStep(0.1)
        self.rate_input.setDecimals(1)
        self.rate_input.setValue(1.0)

        # Тип працевлаштування - with Ukrainian labels
        self.employment_type_input = QComboBox()
        self.employment_type_items = {
            EmploymentType.MAIN: "Основне місце роботи",
            EmploymentType.INTERNAL: "Внутрішній сумісник",
            EmploymentType.EXTERNAL: "Зовнішній сумісник",
        }
        for et, label in self.employment_type_items.items():
            self.employment_type_input.addItem(label, et)

        self.work_basis_input = QComboBox()
        # Ukrainian labels for work basis
        self.work_basis_items = {
            WorkBasis.CONTRACT: "Контракт",
            WorkBasis.COMPETITIVE: "Конкурсна основа",
            WorkBasis.STATEMENT: "Заява",
        }
        for wb, label in self.work_basis_items.items():
            self.work_basis_input.addItem(label, wb)

        # Контракт - dates with current date defaults
        from datetime import date

        self.term_start_input = QDateEdit()
        self.term_start_input.setCalendarPopup(True)
        self.term_start_input.setDate(date.today())

        self.term_end_input = QDateEdit()
        self.term_end_input.setCalendarPopup(True)
        self.term_end_input.setDate(date.today())

        self.vacation_balance_input = QSpinBox()
        self.vacation_balance_input.setRange(0, 365)

        layout.addRow("ПІБ:", self.pib_input)
        layout.addRow("Вчений ступінь:", self.degree_input)
        layout.addRow("Посада:", self.position_input)
        layout.addRow("Ставка:", self.rate_input)
        layout.addRow("Тип працевлаштування:", self.employment_type_input)
        layout.addRow("Основа:", self.work_basis_input)
        layout.addRow("Період контракту (початок):", self.term_start_input)
        layout.addRow("Період контракту (кінець):", self.term_end_input)
        layout.addRow("Наявна кількість днів відпустки:", self.vacation_balance_input)

        # Кнопки
        from PyQt6.QtWidgets import QDialogButtonBox

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_data(self):
        """Завантажує дані співробітника."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
            if staff:
                self.pib_input.setText(staff.pib_nom)
                self.degree_input.setText(staff.degree or "")
                # Set position text in editable combobox
                index = self.position_input.findText(staff.position)
                if index >= 0:
                    self.position_input.setCurrentIndex(index)
                else:
                    self.position_input.setCurrentText(staff.position)
                # Rate is now decimal (1.0 to 0.1)
                self.rate_input.setValue(float(staff.rate))
                # Find employment type by enum value
                for i in range(self.employment_type_input.count()):
                    if self.employment_type_input.itemData(i) == staff.employment_type:
                        self.employment_type_input.setCurrentIndex(i)
                        break
                # Find work basis by enum value
                for i in range(self.work_basis_input.count()):
                    if self.work_basis_input.itemData(i) == staff.work_basis:
                        self.work_basis_input.setCurrentIndex(i)
                        break
                self.term_start_input.setDate(staff.term_start)
                self.term_end_input.setDate(staff.term_end)
                self.vacation_balance_input.setValue(staff.vacation_balance)

    def accept(self):
        """Зберігає дані."""
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService
        from PyQt6.QtWidgets import QMessageBox
        from sqlalchemy.exc import IntegrityError

        # Валідація ПІБ: Прізвище Ім'я По батькові
        pib = self.pib_input.text().strip()
        pib_parts = pib.split()

        if len(pib_parts) != 3:
            QMessageBox.warning(
                self,
                "Некоректний ПІБ",
                "ПІБ має бути у форматі: Прізвище Ім'я По батькові\n\n"
                "Приклад: Петренко Тарас Сергійович\n\n"
                f"Введено: {pib}"
            )
            return

        # Перевірка на українські літери та велику першу літеру
        import re
        ukrainian_pattern = r"^[А-ЩЬЮЯЇІЄҐA-Z][а-щьюяїієҐ'a-z\-]+$"

        for part in pib_parts:
            if not re.match(ukrainian_pattern, part):
                QMessageBox.warning(
                    self,
                    "Некоректний ПІБ",
                    f"Кожна частина ПІБ має починатися з великої літери\n"
                    "та містити лише українські літери.\n\n"
                    f"Некоректна частина: {part}\n\n"
                    "Приклад: Петренко Тарас Сергійович"
                )
                return

        # Rate is now already in decimal format (1.0 to 0.1)
        rate = self.rate_input.value()
        # Get employment type and work basis from stored data
        employment_type = self.employment_type_input.currentData()
        work_basis = self.work_basis_input.currentData()

        staff_data = {
            "pib_nom": pib,
            "degree": self.degree_input.text() or None,
            "position": self.position_input.currentText(),
            "rate": rate,
            "employment_type": employment_type,
            "work_basis": work_basis,
            "term_start": self.term_start_input.date().toPyDate(),
            "term_end": self.term_end_input.date().toPyDate(),
            "vacation_balance": self.vacation_balance_input.value(),
            "is_active": True,
        }

        # Перевірка унікальності посади завідувача (можна тільки одного: завідувач або в.о.)
        head_positions = ["Завідувач кафедри", "В.о завідувача кафедри"]
        if staff_data["position"] in head_positions:
            from backend.models.staff import Staff
            with get_db_context() as db:
                existing_head = db.query(Staff).filter(
                    Staff.position.in_(head_positions),
                    Staff.is_active == True
                ).first()
                if existing_head and (self.staff_id is None or existing_head.id != self.staff_id):
                    QMessageBox.warning(
                        self,
                        "Помилка",
                        f"Посада завідувача кафедри вже зайнята.\n\n"
                        f"Поточний: {existing_head.pib_nom} ({existing_head.position})\n"
                        "Спочатку деактивуйте або змініть посаду поточного запису."
                    )
                    return

        try:
            with get_db_context() as db:
                service = StaffService(db, changed_by="USER")

                if self.staff_id is None:
                    # Створення - дозволяємо сумісництво (однакове ПІБ, різні посади)
                    service.create_staff(staff_data)
                else:
                    # Оновлення
                    staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
                    if staff:
                        service.update_staff(staff, staff_data)

            super().accept()
        except IntegrityError as e:
            QMessageBox.critical(self, "Помилка", f"Помилка цілісності даних: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти: {e}")
