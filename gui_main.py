import sys
import os
from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QSplitter,
    QLineEdit, QMessageBox, QComboBox, QHeaderView, QFileDialog,
    QDialog, QDialogButtonBox, QDateEdit, QRadioButton, QButtonGroup,
    QGroupBox, QCheckBox, QProgressBar, QStatusBar, QFormLayout,
    QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QTimer, QObject, QThread
from PyQt6.QtGui import QFont, QIcon, QPixmap

from sqlalchemy.orm import Session
from app.models import Staff, VacationRequest, LeaveReason, create_tables, init_default_data, get_db

from app.logic_enhanced import (
    calculate_vacation_days,
    get_payment_phrase,
    format_display_name,
    generate_vacation_document_enhanced,
    format_vacation_description,
    generate_vacation_document_md
)
from config import SIGNATORIES, EMPLOYMENT_TYPES, POSITIONS, ACADEMIC_DEGREES, LEAVE_TYPES, STATUSES



class DocGenEnhancedWorker(QObject):
    """Worker for generating enhanced documents in a separate thread"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, request_id, data, parent=None):
        super().__init__(parent)
        self.request_id = request_id
        self.data = data

    def generate(self):
        """Generate the enhanced vacation document"""
        try:
            doc_path = generate_vacation_document_md(
                request_id=self.request_id,
                staff_info=self.data['staff_info'],
                periods=self.data['periods'],
                total_days=self.data['total_days'],
                leave_type=self.data['leave_type'],
                reason_text=self.data.get('reason_text'),
                custom_description=self.data.get('description', '')
            )
            self.finished.emit(doc_path)
        except Exception as e:
            import traceback
            self.error.emit(f"Помилка у фоновому режимі: {e}\n{traceback.format_exc()}")


class CreateVacationDialog(QDialog):
    """Dialog for creating new vacation requests"""
    def __init__(self, parent=None, staff_id=None):
        super().__init__(parent)
        self.setWindowTitle("Створити заяву на відпустку")
        self.setMinimumWidth(500)
        self.staff_id = staff_id
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Staff selection
        staff_group = QGroupBox("Співробітник")
        staff_layout = QHBoxLayout()

        self.staff_combo = QComboBox()
        self.staff_combo.setMinimumWidth(300)
        staff_layout.addWidget(QLabel("Оберіть співробітника:"))
        staff_layout.addWidget(self.staff_combo)
        staff_group.setLayout(staff_layout)
        layout.addWidget(staff_group)

        # Date selection
        date_group = QGroupBox("Період відпустки")
        date_layout = QVBoxLayout()

        dates_layout = QHBoxLayout()
        dates_layout.addWidget(QLabel("З:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        dates_layout.addWidget(self.start_date)

        dates_layout.addWidget(QLabel("По:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addDays(14))
        dates_layout.addWidget(self.end_date)

        date_layout.addLayout(dates_layout)

        self.days_label = QLabel("Загальна кількість днів: 14")
        date_layout.addWidget(self.days_label)
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        # Leave type selection
        type_group = QGroupBox("Тип відпустки")
        type_layout = QVBoxLayout()

        self.leave_type_group = QButtonGroup()
        self.paid_radio = QRadioButton("Оплачувана відпустка")
        self.unpaid_radio = QRadioButton("Відпустка без збереження заробітної плати")
        self.leave_type_group.addButton(self.paid_radio, 0)
        self.leave_type_group.addButton(self.unpaid_radio, 1)
        self.paid_radio.setChecked(True)

        type_layout.addWidget(self.paid_radio)
        type_layout.addWidget(self.unpaid_radio)

        # Payment info (for paid leave)
        self.payment_label = QLabel("")
        self.payment_label.setStyleSheet("color: blue; font-weight: bold;")
        type_layout.addWidget(self.payment_label)

        # Reason selection (for unpaid leave)
        reason_layout = QHBoxLayout()
        reason_layout.addWidget(QLabel("Причина:"))
        self.reason_combo = QComboBox()
        self.reason_combo.setEditable(True)
        reason_layout.addWidget(self.reason_combo)
        type_layout.addLayout(reason_layout)

        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # Connect signals
        self.start_date.dateChanged.connect(self.update_days)
        self.end_date.dateChanged.connect(self.update_days)
        self.leave_type_group.buttonClicked.connect(self.update_leave_type)
        self.reason_combo.editTextChanged.connect(self.on_reason_changed)

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
        self.update_days()
        self.update_leave_type()

    def update_days(self):
        """Update days count when dates change"""
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        days = calculate_vacation_days(start, end)
        self.days_label.setText(f"Загальна кількість днів: {days}")

    def update_leave_type(self):
        """Update UI based on leave type selection"""
        is_paid = self.paid_radio.isChecked()

        if is_paid:
            self.reason_combo.setEnabled(False)
            self.payment_label.setVisible(True)
            # Calculate payment phrase
            start = self.start_date.date().toPyDate()
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

            data = {
                'staff_id': staff_id,
                'staff_info': {
                    'full_name': staff.full_name,
                    'position': staff.position,
                    'academic_degree': staff.academic_degree
                },
                'start_date': self.start_date.date().toPyDate(),
                'end_date': self.end_date.date().toPyDate(),
                'leave_type': 'PAID' if self.paid_radio.isChecked() else 'UNPAID',
                'reason_text': self.reason_combo.currentText().strip()
            }
            return data
        finally:
            db.close()


class VacationDetailsDialog(QDialog):
    """Dialog for viewing and editing vacation request details"""
    def __init__(self, parent=None, request_id=None):
        super().__init__(parent)
        self.setWindowTitle("Деталі заяви")
        self.setMinimumWidth(600)
        self.request_id = request_id
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Details section
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        # Status section
        status_group = QGroupBox("Статус")
        status_layout = QVBoxLayout()
        self.status_label = QLabel()
        status_layout.addWidget(self.status_label)

        # Timesheet processed checkbox
        self.timesheet_checkbox = QCheckBox("Додано до табелю")
        status_layout.addWidget(self.timesheet_checkbox)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Actions
        actions_group = QGroupBox("Дії")
        actions_layout = QVBoxLayout()

        self.open_doc_button = QPushButton("Відкрити документ (.docx)")
        self.open_doc_button.clicked.connect(self.open_document)
        actions_layout.addWidget(self.open_doc_button)

        self.upload_scan_button = QPushButton("Завантажити скан підпису")
        self.upload_scan_button.clicked.connect(self.upload_scan)
        actions_layout.addWidget(self.upload_scan_button)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def load_data(self):
        """Load request data"""
        db = next(get_db())
        try:
            request = db.query(VacationRequest).filter_by(id=self.request_id).first()
            if not request:
                return

            staff = request.staff
            days = calculate_vacation_days(request.start_date, request.end_date)

            details = f"""
            <b>Співробітник:</b> {staff.full_name}<br>
            <b>Посада:</b> {staff.position}<br>
            <b>Період:</b> {request.start_date.strftime('%d.%m.%Y')} - {request.end_date.strftime('%d.%m.%Y')}<br>
            <b>Кількість днів:</b> {days}<br>
            <b>Тип відпустки:</b> {request.leave_type}<br>
            """

            if request.reason_text:
                details += f"<b>Причина:</b> {request.reason_text}<br>"

            if request.scan_path:
                details += f"<b>Скан підпису:</b> {request.scan_path}<br>"

            self.details_label.setText(details)
            self.status_label.setText(f"Статус: {request.status}")
            self.timesheet_checkbox.setChecked(request.timesheet_processed)

            # Enable/disable buttons based on status
            has_scan = bool(request.scan_path)
            self.upload_scan_button.setEnabled(request.status in ['Створено', 'На підписі'])

        finally:
            db.close()

    def open_document(self):
        """Open the generated document"""
        # This would open the .docx file
        # Implementation depends on how documents are stored
        QMessageBox.information(self, "Відкриття документу", "Функція відкриття документу буде реалізована")

    def upload_scan(self):
        """Upload scan of signed document"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Оберіть скан підпису",
            "",
            "PDF Files (*.pdf);;Image Files (*.png *.jpg *.jpeg)"
        )

        if file_path:
            # Save scan and update database
            QMessageBox.information(self, "Завантаження", f"Файл {file_path} завантажено")


class AddStaffDialog(QDialog):
    """Dialog for adding a new staff member"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Додати співробітника")
        self.setMinimumWidth(500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Form layout
        form_layout = QFormLayout()

        # Full Name
        self.full_name_edit = QLineEdit()
        form_layout.addRow("Повне ім'я (ПІБ):*", self.full_name_edit)

        # Academic Degree
        self.degree_combo = QComboBox()
        self.degree_combo.setEditable(True)
        self.degree_combo.addItems(ACADEMIC_DEGREES)
        form_layout.addRow("Вчений ступінь:", self.degree_combo)

        # Rate
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.1, 2.0)
        self.rate_spin.setSingleStep(0.25)
        self.rate_spin.setValue(1.0)
        self.rate_spin.setSuffix(" ставки")
        form_layout.addRow("Ставка:", self.rate_spin)

        # Position
        self.position_combo = QComboBox()
        self.position_combo.setEditable(True)
        self.position_combo.addItems(POSITIONS)
        form_layout.addRow("Посада:", self.position_combo)

        # Employment Type
        self.employment_combo = QComboBox()
        self.employment_combo.addItems(list(EMPLOYMENT_TYPES.values()))
        form_layout.addRow("Тип зайнятості:", self.employment_combo)

        # Employment Term
        dates_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        dates_layout.addWidget(QLabel("З:"))
        dates_layout.addWidget(self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addYears(5))
        dates_layout.addWidget(QLabel("По:"))
        dates_layout.addWidget(self.end_date)

        form_layout.addRow("Термін роботи:", dates_layout)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def get_data(self):
        """Get form data"""
        return {
            'full_name': self.full_name_edit.text().strip(),
            'academic_degree': self.degree_combo.currentText(),
            'rate': self.rate_spin.value(),
            'position': self.position_combo.currentText(),
            'employment_type': self.employment_combo.currentText(),
            'employment_start': self.start_date.date().toPyDate(),
            'employment_end': self.end_date.date().toPyDate()
        }

    def accept(self):
        """Validate and accept"""
        data = self.get_data()
        if not data['full_name']:
            QMessageBox.warning(self, "Помилка", "Повне ім'я є обов'язковим полем")
            return

        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VacationManager - Система управління відпустками")
        self.setGeometry(100, 100, 1200, 700)
        self.selected_staff_id = None

        # Initialize database
        create_tables()
        init_default_data()

        self.setup_ui()
        self.load_data()

        # Setup timer for refresh
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds

    def setup_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Toolbar
        toolbar_layout = QHBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Пошук співробітників...")
        self.search_box.textChanged.connect(self.filter_staff)
        toolbar_layout.addWidget(QLabel("Пошук:"))
        toolbar_layout.addWidget(self.search_box)

        toolbar_layout.addStretch()

        self.add_staff_btn = QPushButton("Додати співробітника")
        self.add_staff_btn.clicked.connect(self.add_staff)
        toolbar_layout.addWidget(self.add_staff_btn)

        main_layout.addLayout(toolbar_layout)

        # Splitter for two panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Staff
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)

        left_layout.addWidget(QLabel("Список співробітників"))

        self.staff_table = QTableWidget()
        self.staff_table.setColumnCount(4)
        self.staff_table.setHorizontalHeaderLabels(["ПІБ", "Посада", "Ставка", "Тип"])
        self.staff_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.staff_table.selectionModel().selectionChanged.connect(self.on_staff_selected)
        self.staff_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self.staff_table)

        splitter.addWidget(left_panel)

        # Right panel - Vacations
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        right_header = QHBoxLayout()
        right_header.addWidget(QLabel("Заяви на відпустку"))
        self.create_vacation_btn = QPushButton("Створити заяву")
        self.create_vacation_btn.clicked.connect(self.create_vacation)
        right_header.addWidget(self.create_vacation_btn)
        right_header.addStretch()
        right_layout.addLayout(right_header)

        self.vacation_table = QTableWidget()
        self.vacation_table.setColumnCount(5)
        self.vacation_table.setHorizontalHeaderLabels(["Період", "Кількість днів", "Тип", "Статус", "Дії"])
        self.vacation_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.vacation_table.doubleClicked.connect(self.show_vacation_details)
        self.vacation_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        right_layout.addWidget(self.vacation_table)

        splitter.addWidget(right_panel)

        splitter.setSizes([500, 700])
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")

    def load_data(self):
        """Load data from database"""
        db = next(get_db())
        try:
            # Load staff
            staff = db.query(Staff).all()
            self.staff_table.setRowCount(len(staff))

            for row, s in enumerate(staff):
                self.staff_table.setItem(row, 0, QTableWidgetItem(s.full_name))
                self.staff_table.setItem(row, 1, QTableWidgetItem(s.position or ""))
                self.staff_table.setItem(row, 2, QTableWidgetItem(str(s.rate)))
                self.staff_table.setItem(row, 3, QTableWidgetItem(s.employment_type or ""))
                self.staff_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s.id)

            # Load vacations
            self.refresh_vacations()

        finally:
            db.close()

    def refresh_vacations(self, staff_id=None):
        """Refresh vacation list"""
        db = next(get_db())
        try:
            query = db.query(VacationRequest)
            if staff_id:
                query = query.filter_by(staff_id=staff_id)

            vacations = query.order_by(VacationRequest.created_at.desc()).all()
            self.vacation_table.setRowCount(len(vacations))

            for row, v in enumerate(vacations):
                period = f"{v.start_date.strftime('%d.%m.%Y')} - {v.end_date.strftime('%d.%m.%Y')}"
                days = calculate_vacation_days(v.start_date, v.end_date)

                self.vacation_table.setItem(row, 0, QTableWidgetItem(period))
                self.vacation_table.setItem(row, 1, QTableWidgetItem(str(days)))
                self.vacation_table.setItem(row, 2, QTableWidgetItem(v.leave_type))
                self.vacation_table.setItem(row, 3, QTableWidgetItem(v.status))

                # Actions buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout()
                actions_layout.setContentsMargins(2, 2, 2, 2)
                actions_layout.setSpacing(2)

                details_btn = QPushButton("Деталі")
                details_btn.setMaximumWidth(60)
                details_btn.clicked.connect(lambda _, rid=v.id: self.show_vacation_details_by_id(rid))
                actions_layout.addWidget(details_btn)

                delete_btn = QPushButton("Видалити")
                delete_btn.setMaximumWidth(60)
                delete_btn.setStyleSheet("QPushButton { background-color: #ff6b6b; }")
                delete_btn.clicked.connect(lambda _, rid=v.id: self.delete_vacation_request(rid))
                actions_layout.addWidget(delete_btn)

                actions_widget.setLayout(actions_layout)
                self.vacation_table.setCellWidget(row, 4, actions_widget)
                self.vacation_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, v.id)

        finally:
            db.close()

    def filter_staff(self):
        """Filter staff table based on search"""
        text = self.search_box.text().lower()
        for row in range(self.staff_table.rowCount()):
            item = self.staff_table.item(row, 0)
            if text in item.text().lower():
                self.staff_table.showRow(row)
            else:
                self.staff_table.hideRow(row)

    def on_staff_selected(self):
        """Handle staff selection"""
        selected_items = self.staff_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            staff_id = self.staff_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.selected_staff_id = staff_id
            self.refresh_vacations(staff_id)

    def create_vacation(self):
        """Create new vacation request using the enhanced dialog and save with enhanced logic."""
        selected_items = self.staff_table.selectedItems()
        staff_id = None

        if selected_items:
            row = selected_items[0].row()
            staff_id = self.staff_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        else:
            staff_id = 1  # Default to 1 if no selection

        from gui_main_enhanced_simple import CreateVacationDialogEnhancedSimple
        dialog = CreateVacationDialogEnhancedSimple(self, staff_id)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            # Directly use the enhanced save method
            self.save_vacation_request_enhanced(data)


    
    def on_doc_gen_finished(self, file_path):
        """Handle successful document generation."""
        self.status_bar.showMessage(f"Документ успішно згенеровано: {file_path}", 5000)
        QMessageBox.information(self, "Успіх", f"Заяву створено та збережено у файл:\n{file_path}")
        if self.thread:
            self.thread.quit()

    def on_doc_gen_error(self, error_message):
        """Handle document generation error."""
        self.status_bar.showMessage("Помилка генерації документу.", 5000)
        QMessageBox.critical(self, "Помилка генерації документу", error_message)
        if self.thread:
            self.thread.quit()

    def save_vacation_request_enhanced(self, data):
        """Save enhanced vacation request to database and generate document in background."""
        db = next(get_db())
        try:
            # Determine start and end dates for database record
            if data['periods']:
                start_date = min(p['start_date'] for p in data['periods'])
                end_date = max(p['end_date'] for p in data['periods'])
            else:
                # For custom descriptions, use current date as placeholder
                start_date = date.today()
                end_date = date.today() + timedelta(days=data['total_days'])

            leave_type = data.get('vacation_payment_type', 'paid').upper()
            data['leave_type'] = leave_type # Add leave_type to the dictionary

            # Need to get fresh staff info for the worker and for the DB record
            staff = db.query(Staff).filter_by(id=data['staff_id']).first()
            if not staff:
                QMessageBox.critical(self, "Помилка", f"Співробітника з ID {data['staff_id']} не знайдено.")
                return
                
            data['staff_info'] = {
                'full_name': staff.full_name,
                'position': staff.position,
                'academic_degree': staff.academic_degree
            }
            # For unpaid leave, the custom description may be the reason
            reason = data.get('description')
            
            request = VacationRequest(
                staff_id=data['staff_id'],
                start_date=start_date,
                end_date=end_date,
                total_days=data['total_days'],
                leave_type=leave_type,
                reason_text=reason,
                status=STATUSES['DRAFT']
            )

            db.add(request)
            db.commit()
            db.refresh(request)

            # --- Start Background Document Generation (Enhanced) ---
            self.status_bar.showMessage("Заяву створено. Генеруємо розширений документ...", 10000)

            self.thread = QThread()
            # Pass the new request ID to the worker
            self.worker = DocGenEnhancedWorker(request_id=request.id, data=data)
            self.worker.moveToThread(self.thread)

            self.thread.started.connect(self.worker.generate)
            self.worker.finished.connect(self.on_doc_gen_finished)
            self.worker.error.connect(self.on_doc_gen_error)
            self.thread.finished.connect(self.thread.deleteLater)

            self.thread.start()
            # --- End Background Document Generation ---

            self.refresh_data()

        except Exception as e:
            db.rollback()
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити розширену заяву: {str(e)}")
        finally:
            db.close()

    def add_staff(self):
        """Add a new staff member"""
        dialog = AddStaffDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.save_staff(data)

    def save_staff(self, data):
        """Save new staff member to database"""
        db = next(get_db())
        try:
            # Check if staff member already exists
            existing = db.query(Staff).filter_by(full_name=data['full_name']).first()
            if existing:
                QMessageBox.warning(self, "Помилка", "Співробітник з таким іменем вже існує")
                return

            # Create new staff member
            staff = Staff(
                full_name=data['full_name'],
                academic_degree=data['academic_degree'],
                rate=data['rate'],
                position=data['position'],
                employment_type=data['employment_type'],
                employment_start=data['employment_start'],
                employment_end=data['employment_end']
            )

            db.add(staff)
            db.commit()

            self.status_bar.showMessage(f"Співробітника {data['full_name']} додано", 3000)
            self.refresh_data()

        except Exception as e:
            db.rollback()
            QMessageBox.critical(self, "Помилка", f"Не вдалося додати співробітника: {str(e)}")
        finally:
            db.close()

    def show_vacation_details(self, index):
        """Show vacation details for selected row"""
        row = index.row()
        item = self.vacation_table.item(row, 0)
        if item:
            request_id = item.data(Qt.ItemDataRole.UserRole)
            self.show_vacation_details_by_id(request_id)

    def show_vacation_details_by_id(self, request_id):
        """Show vacation details by ID"""
        dialog = VacationDetailsDialog(self, request_id)
        dialog.exec()

    def delete_vacation_request(self, request_id):
        """Delete vacation request after confirmation"""
        # Get vacation details for confirmation message
        db = next(get_db())
        try:
            vacation = db.query(VacationRequest).filter_by(id=request_id).first()
            if not vacation:
                QMessageBox.warning(self, "Помилка", "Заявку не знайдено")
                return

            # Get staff name for better confirmation message
            staff_name = vacation.staff.full_name if vacation.staff else f"ID: {vacation.staff_id}"
            period = f"{vacation.start_date.strftime('%d.%m.%Y')} - {vacation.end_date.strftime('%d.%m.%Y')}"

            # Show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Підтвердження видалення",
                f"Ви впевнені, що хочете видалити заяву?\n\n"
                f"Співробітник: {staff_name}\n"
                f"Період: {period}\n"
                f"Кількість днів: {vacation.total_days}\n"
                f"Тип: {vacation.leave_type}\n"
                f"Статус: {vacation.status}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Delete the vacation request
                db.delete(vacation)
                db.commit()

                # Show success message
                self.status_bar.showMessage("Заяву успішно видалено", 3000)

                # Refresh the vacation table
                if hasattr(self, 'selected_staff_id') and self.selected_staff_id:
                    self.refresh_vacations(self.selected_staff_id)
                else:
                    self.refresh_vacations()

        except Exception as e:
            db.rollback()
            QMessageBox.critical(self, "Помилка", f"Не вдалося видалити заявку: {str(e)}")
        finally:
            db.close()

    def refresh_data(self):
        """Refresh all data"""
        self.load_data()

    def closeEvent(self, event):
        """Handle window close event."""
        if hasattr(self, 'thread') and self.thread.isRunning():
            reply = QMessageBox.question(self, 'Завершення роботи', 
                                           "Іде генерація документу. Ви впевнені, що хочете вийти?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                self.thread.quit()
                self.thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Set application font
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
