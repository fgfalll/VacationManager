"""Головне вікно Desktop додатку."""

import webbrowser
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QTabWidget,
    QMenuBar,
    QMenu,
    QDialog,
    QTabBar,
)

from desktop.ui.staff_tab import StaffTab
from desktop.ui.schedule_tab import ScheduleTab
from desktop.ui.builder_tab import BuilderTab
from desktop.ui.settings_tab import SettingsDialog
from desktop.ui.tabel_tab import TabelTab


class MainWindow(QMainWindow):
    """
    Головне вікно додатку VacationManager.

    Містить вкладки для управління персоналом, планування графіку
    та конструктора заяв.
    """

    document_created = pyqtSignal()

    def __init__(self, show_splash: bool = True):
        """
        Ініціалізує головне вікно.

        Args:
            show_splash: Якщо True - показує сплеш-скрін та оновлює його (для старту),
                         якщо False - не оновлює (для внутрішнього використання)
        """
        super().__init__()
        self._show_splash = show_splash
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Налаштовує інтерфейс."""
        self.setWindowTitle("VacationManager v6.0")
        self.setMinimumSize(1400, 900)

        # Центральний віджет - табки
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Вкладки (без передачі db - кожна вкладка створює свою сесію)
        self.staff_tab = StaffTab()
        self.schedule_tab = ScheduleTab()  # Hidden for now
        self.builder_tab = BuilderTab()
        self.tabel_tab = TabelTab()

        self.tabs.addTab(self.staff_tab, "Персонал")
        # self.tabs.addTab(self.schedule_tab, "Графік відпусток")  # Hidden for now
        self.tabs.addTab(self.builder_tab, "Конструктор заяв")
        self.tabs.addTab(self.tabel_tab, "Табель")

        # Enable closing tabs (for ephemeral builder tabs)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)

        # Hide close buttons for persistent tabs
        # Indices correspond to the visible tabs above
        self.tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tabs.tabBar().setTabButton(1, QTabBar.ButtonPosition.RightSide, None)
        self.tabs.tabBar().setTabButton(2, QTabBar.ButtonPosition.RightSide, None)

        # Refresh data on app start (тільки якщо не використовуємо сплеш-скрін)
        if not self._show_splash:
            self._refresh_data()

        # Меню
        menubar = self.menuBar()

        # Файл
        file_menu = menubar.addMenu("Файл")
        file_menu.addAction("Налаштування", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("Вихід", self.close)

        # Синхронізація
        sync_menu = menubar.addMenu("Синхронізація")
        sync_menu.addAction("Відкрити Web Portal", self._open_web_portal)
        sync_menu.addAction("Оновити дані", self._refresh_data)

        # Допомога
        help_menu = menubar.addMenu("Допомога")
        help_menu.addAction("Про програму", self._show_about)

    def _connect_signals(self):
        """Підключає сигнали між компонентами."""
        # Коли документ створено, оновити список у персоналі
        self.builder_tab.document_created.connect(self.staff_tab.refresh_documents)

    def navigate_to_builder(self, staff_id: int, document_id: int | None = None):
        """
        Переходить на вкладку конструктора заяв.

        Args:
            staff_id: ID співробітника
            document_id: ID документа для редагування (None для нового документа)
        """
        self.tabs.setCurrentWidget(self.builder_tab)
        if document_id:
            self.builder_tab.load_document(document_id, staff_id)
        else:
            self.builder_tab.new_document(staff_id)

    def _open_settings(self, tab: str | None = None) -> None:
        """Відкриває діалог налаштувань."""
        dialog = SettingsDialog(self)
        if tab:
            dialog.set_tab(tab)
        dialog.exec()

    def _open_web_portal(self) -> None:
        """Відкриває Web Portal у браузері."""
        webbrowser.open("http://127.0.0.1:8000")

    def _refresh_data(self):
        """Оновлює дані на всіх вкладках."""
        self.staff_tab.refresh()
        self.schedule_tab.refresh()
        self.builder_tab.refresh()
        self.tabel_tab.refresh()

    def refresh_tabel_tab(self, correction_info=None):
        """Оновлює вкладку табеля (викликається при зміні відвідуваності)."""
        self.tabel_tab.refresh(correction_info)

    def switch_to_builder_for_subposition(self):
        """Переключається на вкладку конструктора для створення документа сумісництва."""
        self.tabs.setCurrentWidget(self.builder_tab)
        # Trigger the subposition document creation flow in builder
        self.builder_tab.start_subposition_document()

    def open_temporary_builder_tab(self, workflow_type: str, staff_id: int | None = None):
        """
        Відкриває тимчасову вкладку конструктора для специфічного завдання.
        
        Args:
            workflow_type: Тип завдання ("new_employee" або "subposition")
            staff_id: ID співробітника (для сумісництва)
        """
        # Create new builder instance
        builder = BuilderTab(is_ephemeral=True)
        
        # Configure based on workflow
        title = "Конструктор"
        if workflow_type == "new_employee":
            title = "Конструктор заяв (прийом)"
            # Initialize for new employee
            builder.start_new_employee_document()
            
        elif workflow_type == "subposition":
            title = "Конструктор заяв (сумісництво)"
            if staff_id:
                builder.start_subposition_mode_for_staff(staff_id)
        
        # Connect signals
        builder.document_created.connect(self.staff_tab.refresh_documents)
        
        # Auto-close logic
        def on_completed():
            index = self.tabs.indexOf(builder)
            if index != -1:
                self.tabs.removeTab(index)
                builder.deleteLater()
                
        builder.task_completed.connect(on_completed)
        
        # Add and focus
        index = self.tabs.addTab(builder, title)
        self.tabs.setCurrentIndex(index)

    def _on_tab_close_requested(self, index: int):
        """
        Обробляє запит на закриття вкладки.
        Дозволяє закривати тільки тимчасові вкладки (is_ephemeral=True).
        """
        widget = self.tabs.widget(index)
        
        # Перевіряємо, чи це тимчасова вкладка
        if isinstance(widget, BuilderTab) and hasattr(widget, 'is_ephemeral') and widget.is_ephemeral:
            self.tabs.removeTab(index)
            widget.deleteLater()
            
    def _show_about(self):
        """Показує інформацію про програму."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Про VacationManager",
            "VacationManager v6.0\n\n"
            "Система управління відпустками для університету\n\n"
            "© 2025",
        )


class TabMixin:
    """
    Mixin для загальних методів вкладок.
    """

    def refresh(self):
        """Оновити дані вкладки."""
        pass

    def save(self):
        """Зберегти зміни."""
        pass
