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
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QColor

from desktop.widgets.status_badge import StatusBadge
from desktop.ui.employee_card_dialog import EmployeeCardDialog
from shared.enums import EmploymentType, WorkBasis, StaffPosition, get_position_label, get_employment_type_label
from backend.models.staff import WorkScheduleType


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
        self.refresh_btn.clicked.connect(self._on_refresh)

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

            # Групуємо по pib_nom і збираємо всі позиції для кожного
            staff_groups = {}
            for staff in all_staff:
                if staff.pib_nom not in staff_groups:
                    staff_groups[staff.pib_nom] = []
                staff_groups[staff.pib_nom].append(staff)

            # Створюємо список з групованими даними
            staff_list = []
            for pib, staff_records in staff_groups.items():
                # Фільтруємо тільки активні позиції для відображення
                active_records = [s for s in staff_records if s.is_active]

                if not active_records:
                    continue  # Пропускаємо якщо немає активних позицій

                # Показуємо тільки активні позиції
                combined_rate = sum(float(s.rate) for s in active_records)
                positions = [get_position_label(s.position) for s in active_records]
                active_ids = [s.id for s in active_records]

                # Зберігаємо дані
                staff_list.append({
                    "pib_nom": pib,
                    "positions": positions,
                    "combined_rate": combined_rate,
                    "staff_records": active_records,  # Тільки активні
                    "is_active": True,
                    "term_start": max(s.term_start for s in active_records),
                    "term_end": min(s.term_end for s in active_records),
                    "vacation_balance": max(s.vacation_balance for s in active_records),
                    "days_until_term_end": min(s.days_until_term_end for s in active_records),
                    "is_term_expired": any(s.is_term_expired for s in active_records),
                })

            # Сортуємо за ПІБ
            staff_list.sort(key=lambda s: s["pib_nom"])

            self.table.setRowCount(len(staff_list))

            for row, staff_data in enumerate(staff_list):
                self._set_row_data(row, staff_data)

    def _set_row_data(self, row: int, staff_data: dict):
        """Встановлює дані в рядок таблиці."""
        try:
            from backend.models.settings import SystemSettings

            # Отримуємо поріг попередження з налаштувань
            warning_days = 30  # За замовчуванням
            try:
                with get_db_context() as db:
                    warning_days = SystemSettings.get_value(db, "contract_warning_days", 30)
            except Exception:
                pass

            staff_records = staff_data["staff_records"]
            pib_nom = staff_data["pib_nom"]
            positions = staff_data["positions"]
            combined_rate = staff_data["combined_rate"]
            is_term_expired = staff_data["is_term_expired"]
            days_until_term_end = staff_data["days_until_term_end"]

            # ПІБ - з іконкою попередження якщо контракт закінчується
            name_text = pib_nom
            if is_term_expired:
                name_text = "⚠️ " + name_text
            elif days_until_term_end <= warning_days:
                name_text = "⏰ " + name_text

            self.table.setItem(row, 0, QTableWidgetItem(name_text))

            # Посади - показуємо всі позиції, якщо більше однієї
            if len(positions) > 1:
                position_text = " + ".join(positions)
            else:
                position_text = positions[0] if positions else ""
            self.table.setItem(row, 1, QTableWidgetItem(position_text))

            # Ставка - показуємо комбіновану, якщо > 1.0
            rate_text = f"{combined_rate:.2f}"
            self.table.setItem(row, 2, QTableWidgetItem(rate_text))

            # Тип працевлаштування - показуємо для першого запису
            emp_type = staff_records[0].employment_type.value if staff_records else "main"
            self.table.setItem(row, 3, QTableWidgetItem(get_employment_type_label(emp_type)))

            term_item = QTableWidgetItem(
                f"{staff_data['term_start'].strftime('%d.%m.%Y')} - "
                f"{staff_data['term_end'].strftime('%d.%m.%Y')}"
            )
            self.table.setItem(row, 4, term_item)

            balance_item = QTableWidgetItem(str(staff_data["vacation_balance"]))
            self.table.setItem(row, 5, balance_item)

            # Дні до кінця контракту з підсвіткою
            days_text = str(days_until_term_end)
            if is_term_expired:
                days_text = f"⛔ {days_text}"
            elif days_until_term_end <= warning_days:
                days_text = f"⚠️ {days_text}"

            days_item = QTableWidgetItem(days_text)

            # Підсвітка рядка червоним якщо контракт закінчується
            if is_term_expired:
                for col in range(7):
                    item = QTableWidgetItem() if col != 0 else self.table.item(row, 0)
                    if col != 0:
                        self.table.setItem(row, col, item)
                    item.setBackground(QColor("#FFCCCC"))
            elif days_until_term_end <= warning_days:
                # Тільки days_item підсвітчуємо
                days_item.setBackground(QColor("#FFEBEE"))
                days_item.setForeground(QColor("#D32F2F"))

            self.table.setItem(row, 6, days_item)

            # Зберігаємо всі ID в першому елементі (список)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole,
                [s.id for s in staff_records])
                
        except Exception as e:
            print(f"Error setting row data for row {row}: {e}")
            import traceback
            traceback.print_exc()

    def _on_search(self):
        """Фільтрує дані при пошуку."""
        search_text = self.search_input.text().lower()

        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            match = search_text in name
            self.table.setRowHidden(row, not match)

    def _on_refresh(self):
        """Оновлює дані та виконує авто-деактивацію прострочених контрактів."""
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService
        from PyQt6.QtWidgets import QMessageBox

        # Спочатку виконуємо авто-деактивацію
        try:
            with get_db_context() as db:
                service = StaffService(db, changed_by="SYSTEM")
                count = service.auto_deactivate_expired_contracts()
                if count > 0:
                    QMessageBox.information(
                        self,
                        "Авто-деактивація",
                        f"Автоматично деактивовано {count} записів з простроченими контрактами."
                    )
        except Exception as e:
            print(f"[ERROR] Помилка авто-деактивації: {e}")

        # Потім оновлюємо таблицю
        self._load_data()

    def _on_selection_changed(self):
        """Обробляє зміну виділення."""
        pass  # Більше не потрібно без кнопок

    def _show_context_menu(self, pos: QPoint) -> None:
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

        create_doc_action = menu.addAction("📄 Створити документ")
        menu.addSeparator()
        edit_action = menu.addAction("✏️ Редагувати")

        # Підменю для видалення
        delete_menu = menu.addMenu("🗑️ Видалити")
        soft_delete_action = delete_menu.addAction("Деактивувати")
        hard_delete_action = delete_menu.addAction("Видалити назавжди")

        menu.addSeparator()
        card_action = menu.addAction("📋 Картка")

        # Отримуємо позицію курсору та показуємо меню
        cursor_pos = QCursor.pos()
        action = menu.exec(cursor_pos)

        # Обробляємо вибір
        if action == create_doc_action:
            self._create_document()
        elif action == edit_action:
            self._edit_staff()
        elif action == soft_delete_action:
            self._soft_delete_staff()
        elif action == hard_delete_action:
            self._hard_delete_staff()
        elif action == card_action:
            self._show_employee_card()

    def _create_document(self, staff_id: int | None = None) -> None:
        """
        Створює документ - показує діалог вибору позиції якщо потрібно.
        """
        from backend.core.database import get_db_context
        from backend.models.staff import Staff
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QPushButton, QButtonGroup, QLabel, QHBoxLayout

        # Якщо staff_id не передано, отримуємо з поточного виділення
        if not staff_id:
            item = self.table.currentItem()
            if not item:
                return
            staff_ids = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
            if isinstance(staff_ids, list) and staff_ids:
                staff_id = staff_ids[0]
            elif isinstance(staff_ids, int):
                staff_id = staff_ids
            else:
                return

        # Отримуємо всі активні позиції співробітника
        with get_db_context() as db:
            staff_list = db.query(Staff).filter(
                Staff.pib_nom == db.query(Staff).filter(Staff.id == staff_id).first().pib_nom,
                Staff.is_active == True
            ).all()

            # Сортуємо: rate 1.00 завжди перший, потім за rate descending
            staff_list.sort(key=lambda s: (s.rate != 1.0, -float(s.rate)))

        # Якщо тільки одна позиція - одразу переходимо
        if len(staff_list) == 1:
            self._navigate_to_builder(staff_list[0].id)
            return

        # Показуємо діалог вибору позиції
        dialog = QDialog(self)
        dialog.setWindowTitle("Оберіть позицію")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        # Знаходимо ПІБ співробітника
        pib_nom = staff_list[0].pib_nom
        layout.addWidget(QLabel(f"<b>{pib_nom}</b>"))
        layout.addWidget(QLabel("Оберіть, для якої позиції створити документ:"))

        button_group = QButtonGroup(dialog)

        for staff in staff_list:
            radio = QRadioButton(f"{get_position_label(staff.position)} ({staff.rate})")
            radio.setProperty("staff_id", staff.id)
            button_group.addButton(radio)
            layout.addWidget(radio)
            if staff.id == staff_id:
                radio.setChecked(True)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("ОК")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = button_group.checkedButton()
            if selected:
                selected_id = selected.property("staff_id")
                self._navigate_to_builder(selected_id)

    def _navigate_to_builder(self, staff_id: int):
        """Переходить на вкладку конструктора заяв."""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'navigate_to_builder'):
                parent.navigate_to_builder(staff_id)
                return
            parent = parent.parent()

    def _add_staff(self):
        """Відкриває діалог додавання співробітника."""
        dialog = StaffDialog(parent=self)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            self._load_data()
        elif result == 2:  # Custom code for "Create Employment Document"
            self._create_new_employee_document()

    def _create_new_employee_document(self):
        """
        Переходить на вкладку конструктора та ініціює створення документа про прийом.
        """
        parent = self.parent()
        while parent:
            if hasattr(parent, 'tabs'): # MainWindow typically has 'tabs' widget
                # Switch to Builder tab (index 2 usually, need to verify)
                # Better: find tab by type/name
                tabs = parent.tabs
                for i in range(tabs.count()):
                    if tabs.tabText(i) == "Конструктор заяв":
                        tabs.setCurrentIndex(i)
                        builder_tab = tabs.widget(i)
                        if hasattr(builder_tab, 'start_new_employee_document'):
                            builder_tab.start_new_employee_document()
                        break
                return
            parent = parent.parent()

    def _edit_staff(self):
        """Відкриває діалог редагування співробітника."""
        from backend.core.database import get_db_context
        from backend.models.staff import Staff

        item = self.table.currentItem()
        if not item:
            return

        staff_ids = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        if isinstance(staff_ids, list) and len(staff_ids) > 1:
            # Multiple positions - show selection dialog
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QPushButton, QButtonGroup, QLabel

            dialog = QDialog(self)
            dialog.setWindowTitle("Оберіть позицію для редагування")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout(dialog)

            layout.addWidget(QLabel("Оберіть, яку позицію редагувати:"))

            button_group = QButtonGroup(dialog)

            for staff_id in staff_ids:
                with get_db_context() as db:
                    staff = db.query(Staff).filter(Staff.id == staff_id).first()
                    if staff and staff.is_active:  # Only show active positions
                        radio = QRadioButton(f"{get_position_label(staff.position)} ({staff.rate})")
                        radio.setProperty("staff_id", staff_id)
                        button_group.addButton(radio)
                        layout.addWidget(radio)
                        if staff_ids[0] == staff_id:
                            radio.setChecked(True)

            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("ОК")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("Скасувати")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected = button_group.checkedButton()
                if selected:
                    selected_id = selected.property("staff_id")
                    edit_dialog = StaffDialog(selected_id, parent=self)
                    if edit_dialog.exec():
                        self._load_data()
        elif isinstance(staff_ids, list) and len(staff_ids) == 1:
            edit_dialog = StaffDialog(staff_ids[0], parent=self)
            if edit_dialog.exec():
                self._load_data()

    def _soft_delete_staff(self):
        """Деактивує співробітника (soft delete)."""
        from backend.models.staff import Staff
        from backend.models.document import Document
        from backend.core.database import get_db_context
        from backend.services.staff_service import StaffService
        from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QRadioButton, QPushButton, QButtonGroup, QLabel, QHBoxLayout
        from shared.enums import DocumentStatus

        item = self.table.currentItem()
        if not item:
            return

        staff_ids = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

        if isinstance(staff_ids, list) and len(staff_ids) > 1:
            # Show selection dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Оберіть позицію")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("Оберіть, яку позицію деактивувати:"))

            button_group = QButtonGroup(dialog)

            for staff_id in staff_ids:
                with get_db_context() as db:
                    staff = db.query(Staff).filter(Staff.id == staff_id).first()
                    if staff and staff.is_active:  # Only show active positions
                        radio = QRadioButton(f"{get_position_label(staff.position)} ({staff.rate})")
                        radio.setProperty("staff_id", staff_id)
                        button_group.addButton(radio)
                        layout.addWidget(radio)
                        if staff_ids[0] == staff_id:
                            radio.setChecked(True)

            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("ОК")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("Скасувати")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            selected = button_group.checkedButton()
            if not selected:
                return

            staff_id = selected.property("staff_id")
        elif isinstance(staff_ids, list):
            staff_id = staff_ids[0]
        else:
            staff_id = staff_ids

        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff or not staff.is_active:
                return  # Only allow operations on active staff

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
                f"Деактивувати {staff.pib_nom} ({get_position_label(staff.position)})?",
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
        from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QRadioButton, QPushButton, QButtonGroup, QLabel, QHBoxLayout
        from shared.enums import DocumentStatus

        item = self.table.currentItem()
        if not item:
            return

        staff_ids = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

        if isinstance(staff_ids, list) and len(staff_ids) > 1:
            # Show selection dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Оберіть позицію")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("Оберіть, яку позицію видалити назавжди:"))

            button_group = QButtonGroup(dialog)

            for staff_id in staff_ids:
                with get_db_context() as db:
                    staff = db.query(Staff).filter(Staff.id == staff_id).first()
                    if staff and staff.is_active:  # Only show active positions
                        radio = QRadioButton(f"{get_position_label(staff.position)} ({staff.rate})")
                        radio.setProperty("staff_id", staff_id)
                        button_group.addButton(radio)
                        layout.addWidget(radio)
                        if staff_ids[0] == staff_id:
                            radio.setChecked(True)

            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("ОК")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("Скасувати")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            selected = button_group.checkedButton()
            if not selected:
                return

            staff_id = selected.property("staff_id")
        elif isinstance(staff_ids, list):
            staff_id = staff_ids[0]
        else:
            staff_id = staff_ids

        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff or not staff.is_active:
                return  # Only allow operations on active staff

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
                f"Ви впевнені, що хочете назавжди видалити {staff.pib_nom} ({get_position_label(staff.position)})?\n\n"
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
        from backend.core.database import get_db_context
        from backend.models.document import Document, DocumentType, DocumentStatus
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QPushButton, QHBoxLayout
        from datetime import date

        item = self.table.currentItem()
        if not item:
            return

        staff_ids = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        if isinstance(staff_ids, list) and len(staff_ids) > 1:
            # Use first staff_id for now
            staff_id = staff_ids[0]
        else:
            staff_id = staff_ids

        # Get staff name
        with get_db_context() as db:
            from backend.models.staff import Staff
            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff:
                return
            staff_name = staff.pib_nom

            # Get documents
            documents = db.query(Document).filter(
                Document.staff_id == staff_id,
                Document.status == DocumentStatus.PROCESSED
            ).order_by(Document.date_start.desc()).all()

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Документи: {staff_name}")
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(400)

        layout = QVBoxLayout(dialog)

        # Table
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["ID", "Тип", "Дата початку", "Дата завершення", "Статус"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(documents))

        for row, doc in enumerate(documents):
            table.setItem(row, 0, QTableWidgetItem(str(doc.id)))
            table.setItem(row, 1, QTableWidgetItem(doc.doc_type.value))
            table.setItem(row, 2, QTableWidgetItem(doc.date_start.strftime("%d.%m.%Y")))
            table.setItem(row, 3, QTableWidgetItem(doc.date_end.strftime("%d.%m.%Y")))
            table.setItem(row, 4, QTableWidgetItem(doc.status.value))

        layout.addWidget(QLabel(f"<b>Документи працівника: {staff_name}</b>"))
        layout.addWidget(table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Закрити")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _show_employee_card(self):
        """Відкриває картку працівника."""
        from backend.core.database import get_db_context
        from backend.models.staff import Staff

        item = self.table.currentItem()
        if not item:
            return

        staff_ids = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

        if isinstance(staff_ids, list) and len(staff_ids) > 1:
            # Show selection dialog
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QPushButton, QButtonGroup, QLabel, QHBoxLayout

            dialog = QDialog(self)
            dialog.setWindowTitle("Оберіть позицію")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("Оберіть, картку якої позиції переглянути:"))

            button_group = QButtonGroup(dialog)

            for staff_id in staff_ids:
                with get_db_context() as db:
                    staff = db.query(Staff).filter(Staff.id == staff_id).first()
                    if staff and staff.is_active:  # Only show active positions
                        radio = QRadioButton(f"{get_position_label(staff.position)} ({staff.rate})")
                        radio.setProperty("staff_id", staff_id)
                        button_group.addButton(radio)
                        layout.addWidget(radio)
                        if staff_ids[0] == staff_id:
                            radio.setChecked(True)

            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("ОК")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("Скасувати")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            selected = button_group.checkedButton()
            if not selected:
                return

            staff_id = selected.property("staff_id")
        elif isinstance(staff_ids, list):
            staff_id = staff_ids[0]
        else:
            staff_id = staff_ids

        if not staff_id:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Помилка", "Не вдалося отримати ID співробітника. Спробуйте оновити таблицю.")
            self._load_data()
            return

        dialog = EmployeeCardDialog(staff_id, parent=self)
        # Connect signals for document actions
        dialog.edit_document.connect(self._on_edit_document)
        dialog.delete_document.connect(self._on_delete_document)
        # Connect signal to refresh tabel tab when attendance is modified
        dialog.attendance_modified.connect(self._on_attendance_modified)
        # Connect signal for adding subposition via document
        dialog.subposition_via_document.connect(self._on_subposition_via_document)
        # Connect signal for staff changes
        dialog.staff_changed.connect(self._load_data)

        # Use open() instead of exec() to allow non-blocking signal handling
        # After dialog closes, refresh the table
        dialog.finished.connect(lambda result: self._load_data())
        dialog.open()

    def _on_edit_document(self, document_id: int):
        """Обробляє сигнал редагування документа."""
        # Navigate to builder tab and load document
        self._edit_document_in_builder(document_id)

    def _on_delete_document(self, document_id: int):
        """Обробляє сигнал видалення документа."""
        self._load_data()  # Refresh to show changes

    def _edit_document_in_builder(self, document_id: int):
        """Відкриває документ у конструкторі заяв."""
        from backend.core.database import get_db_context
        from backend.models.document import Document

        with get_db_context() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                return

            staff_id = doc.staff_id

        # Navigate to builder tab
        self._edit_document(document_id, staff_id)

    def _edit_document(self, document_id: int, staff_id: int):
        """Редагує існуючий документ."""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'navigate_to_builder'):
                parent.navigate_to_builder(staff_id, document_id)
                return
            parent = parent.parent()

    def _show_all_cards(self):
        """Відкриває діалог з усіма картками працівників."""
        from backend.core.database import get_db_context
        from backend.models.staff import Staff
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt

        # Завантажуємо дані перед створенням діалогу
        def load_staff_data():
            with get_db_context() as db:
                # Отримуємо ВСІ записи (включаючи деактивовані)
                staff_list = db.query(Staff).order_by(Staff.pib_nom, Staff.id.desc()).all()

                # Конвертуємо ВСІ записи в список даних
                staff_data_list = []
                for staff in staff_list:
                    staff_data_list.append({
                        "id": staff.id,
                        "pib_nom": staff.pib_nom,
                        "position": staff.position,
                        "rate": str(staff.rate),
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
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            "ID",
            "ПІБ",
            "Посада",
            "Ставка",
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
                table.setItem(row, 2, QTableWidgetItem(get_position_label(staff["position"])))

                # Ставка
                table.setItem(row, 3, QTableWidgetItem(staff.get("rate", "")))

                # Статус
                status_text = "✅ Активний" if staff["is_active"] else "❌ Неактивний"
                status_item = QTableWidgetItem(status_text)
                if not staff["is_active"]:
                    status_item.setBackground(QColor("#FFCDD2"))
                table.setItem(row, 4, status_item)

                # Контракт
                term_item = QTableWidgetItem(
                    f"{staff['term_start'].strftime('%d.%m.%Y')} - "
                    f"{staff['term_end'].strftime('%d.%m.%Y')}"
                )
                table.setItem(row, 5, term_item)

                # Баланс
                table.setItem(row, 6, QTableWidgetItem(str(staff["vacation_balance"])))

                # Дні до кінця
                days_text = str(staff["days_until_term_end"])
                if staff["is_term_expired"]:
                    days_text = f"⛔ {days_text}"
                elif staff["days_until_term_end"] <= 30:
                    days_text = f"⚠️ {days_text}"
                table.setItem(row, 7, QTableWidgetItem(days_text))

        # Заповнюємо таблицю початковими даними
        populate_table(staff_data_list)

        # Функція для оновлення таблиці
        def refresh_table():
            new_data = load_staff_data()
            populate_table(new_data)

        # Двійний клік відкриває картку
        def on_double_click(item):
            staff_id = table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
            card_dialog = EmployeeCardDialog(staff_id, self)  # Use self (StaffTab) as parent
            # Connect signals for document actions
            card_dialog.edit_document.connect(self._on_edit_document)
            card_dialog.delete_document.connect(self._on_delete_document)
            card_dialog.finished.connect(lambda result: refresh_table())
            # Connect signal to refresh tabel tab when attendance is modified
            card_dialog.attendance_modified.connect(self._on_attendance_modified)
            # Connect signal for adding subposition via document
            card_dialog.subposition_via_document.connect(self._on_subposition_via_document)
            # Connect signal for staff changes
            card_dialog.staff_changed.connect(lambda: (refresh_table(), self._load_data()))
            card_dialog.open()

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

    def _on_attendance_modified(self, correction_info=None):
        """Викликається при зміні відвідуваності - оновлює табель."""
        # Get main window and refresh tabel tab
        parent = self.parent()
        while parent:
            if hasattr(parent, 'refresh_tabel_tab'):
                parent.refresh_tabel_tab(correction_info)
                break
            parent = parent.parent()

    def _on_subposition_via_document(self):
        """Викликається при додаванні сумісництва через документ."""
        # Get main window and navigate to builder tab with subposition document
        parent = self.parent()
        while parent:
            if hasattr(parent, 'switch_to_builder_for_subposition'):
                parent.switch_to_builder_for_subposition()
                break
            parent = parent.parent()

    def refresh_documents(self):
        """Оновлює список документів (слот для сигналу).

        Викликається коли документ створено у конструкторі заяв.
        """
        # Refresh main staff data to update any cached document info
        self._load_data()

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

        # Посада - dropdown from StaffPosition enum
        self.position_input = QComboBox()
        self.position_input.setEditable(True)
        position_items = {
            StaffPosition.HEAD_OF_DEPARTMENT: "Завідувач кафедри",
            StaffPosition.ACTING_HEAD_OF_DEPARTMENT: "В.о завідувача кафедри",
            StaffPosition.PROFESSOR: "Професор",
            StaffPosition.ASSOCIATE_PROFESSOR: "Доцент",
            StaffPosition.SENIOR_LECTURER: "Старший викладач",
            StaffPosition.LECTURER: "Асистент",
            StaffPosition.SPECIALIST: "Фахівець",
        }
        for pos_value, pos_label in position_items.items():
            self.position_input.addItem(pos_label, pos_value)

        # Ставка - from 1.0 to 0.1 with step 0.25 for quick selection
        rate_layout = QHBoxLayout()
        self.rate_input = QDoubleSpinBox()
        self.rate_input.setRange(0.0, 1.0)
        self.rate_input.setSingleStep(0.25)
        self.rate_input.setDecimals(2)
        self.rate_input.setValue(1.0)
        rate_layout.addWidget(self.rate_input)

        # Quick rate buttons
        for rate_value in [1.0, 0.75, 0.5, 0.25]:
            rate_btn = QPushButton(f"{rate_value:.2f}")
            rate_btn.setFixedWidth(50)
            rate_btn.setStyleSheet("font-weight: bold;")
            rate_btn.clicked.connect(lambda checked, r=rate_value: self.rate_input.setValue(r))
            rate_layout.addWidget(rate_btn)

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
        self.vacation_balance_input.setValue(0)

        # Графік роботи
        self.work_schedule_input = QComboBox()
        self.work_schedule_items = {
            WorkScheduleType.STANDARD: "Повний робочий день (8 год)",
            WorkScheduleType.PART_TIME: "Неповний робочий день/тиждень",
        }
        for ws, label in self.work_schedule_items.items():
            self.work_schedule_input.addItem(label, ws)

        # Додаємо поля до форми (перед кнопками)
        layout.addRow("ПІБ:", self.pib_input)
        layout.addRow("Вчений ступінь:", self.degree_input)
        layout.addRow("Посада:", self.position_input)
        layout.addRow("Ставка:", rate_layout)
        layout.addRow("Тип працевлаштування:", self.employment_type_input)
        layout.addRow("Основа:", self.work_basis_input)
        layout.addRow("Початок контракту:", self.term_start_input)
        layout.addRow("Кінець контракту:", self.term_end_input)
        layout.addRow("Кількість днів відпустки:", self.vacation_balance_input)
        layout.addRow("Графік роботи:", self.work_schedule_input)

        # Кнопки
        from PyQt6.QtWidgets import QDialogButtonBox

        buttons_layout = QHBoxLayout()
        
        # New "Create Employment Application" button
        self.create_doc_btn = QPushButton("Створити заяву про прийом")
        self.create_doc_btn.setStyleSheet("background-color: #10B981; color: white; font-weight: bold;")
        self.create_doc_btn.clicked.connect(self._on_create_document)
        
        # Standard buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        buttons_layout.addWidget(self.create_doc_btn)
        # Add spacer to separate custom button from standard ones
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.button_box)
        
        layout.addRow(buttons_layout)
        
        # Hide custom button if editing existing staff
        if self.staff_id is not None:
            self.create_doc_btn.setVisible(False)

    def _on_create_document(self):
        """Handle click on Create Employment Document."""
        # Use a special result code or mechanism to signal parent
        # We can use done(2) for example, where 2 is a custom code
        self.done(2)

    def _load_data(self):
        """Завантажує дані співробітника."""
        from backend.models.staff import Staff
        from backend.core.database import get_db_context

        with get_db_context() as db:
            staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
            if staff:
                self.pib_input.setText(staff.pib_nom)
                self.degree_input.setText(staff.degree or "")
                # Set position by enum value in editable combobox
                index = self.position_input.findData(staff.position)
                if index >= 0:
                    self.position_input.setCurrentIndex(index)
                else:
                    # Fallback: show as-is
                    self.position_input.setCurrentText(get_position_label(staff.position))
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
                # For new employee without vacation record, show special text
                if staff.vacation_balance == 0 and not staff.documents:
                    self.vacation_balance_input.setValue(0)
                else:
                    self.vacation_balance_input.setValue(staff.vacation_balance)

                # Find work schedule by enum value
                for i in range(self.work_schedule_input.count()):
                    if self.work_schedule_input.itemData(i) == staff.work_schedule:
                        self.work_schedule_input.setCurrentIndex(i)
                        break

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

        # Get department from settings
        from backend.models.settings import SystemSettings
        with get_db_context() as db:
            department = SystemSettings.get_value(db, "department_name", "")

        # Prepare staff data
        staff_data = {
            "pib_nom": pib,
            "degree": self.degree_input.text() or None,
            "position": self.position_input.currentData(),
            "rate": rate,
            "employment_type": employment_type,
            "work_basis": work_basis,
            "term_start": self.term_start_input.date().toPyDate(),
            "term_end": self.term_end_input.date().toPyDate(),
            "is_active": True,
            "vacation_balance": self.vacation_balance_input.value(),
            "department": department,
            "work_schedule": self.work_schedule_input.currentData(),
        }

        # Перевірка унікальності посади завідувача (можна тільки одного: завідувач або в.о.)
        head_positions = [StaffPosition.HEAD_OF_DEPARTMENT, StaffPosition.ACTING_HEAD_OF_DEPARTMENT]
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
                    # Створення нового працівника
                    service.create_staff(staff_data)
                else:
                    # Оновлення існуючого працівника
                    staff = db.query(Staff).filter(Staff.id == self.staff_id).first()
                    if staff:
                        service.update_staff(staff, staff_data)

            super().accept()
        except IntegrityError as e:
            QMessageBox.critical(self, "Помилка", f"Помилка цілісності даних: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти: {e}")
