"""Tabulir Tab - Monthly timesheet table preview and management."""

import calendar
import logging
import os
import shutil
import subprocess
import tempfile
import traceback
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from PyQt6.QtCore import Qt, pyqtSignal, QMarginsF, QTimer, QUrl
from PyQt6.QtGui import QAction, QIntValidator, QPageLayout, QPageSize, QPagedPaintDevice
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QToolButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QProgressDialog,
    QApplication,
)

from backend.services.tabel_service import (
    generate_tabel_html,
    save_tabel_to_file,
    save_tabel_archive,
    reconstruct_tabel_from_archive,
    reconstruct_tabel_html_from_archive,
    list_tabel_archives,
    MONTHS_UKR,
    populate_title_docx,
    convert_docx_to_pdf,
    merge_pdfs,
    DEFAULT_INSTITUTION_NAME,
    DEFAULT_EDRPOU_CODE,
)

# WeasyPrint executable path
WEASYPRINT_EXE = Path(__file__).parent.parent.parent / 'weasyprint' / 'dist' / 'weasyprint.exe'

# CSS content embedded directly (instead of external sheet.css)
TABEL_CSS = """/* Tabel (Timesheet) Styles - Ukrainian Government Form P-5 */
@page {
    size: A4 landscape;
    margin: 5mm;
}
@media print {
    body {
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
        width: 100%;
        zoom: 0.85;
    }
    .ritz.grid-container {
        zoom: 0.85;
        width: 130%;
    }
}
html {
    width: 297mm;
}
body {
    font-family: "Times New Roman", Times, serif;
    font-size: 8pt;
    margin: 0;
    padding: 0;
    width: 297mm;
}
.ritz.grid-container {
    width: 130%;
    max-width: none;
    margin: 0;
    transform-origin: top left;
}
table.waffle {
    border-collapse: collapse;
    width: 100%;
    table-layout: fixed;
}
table.waffle th, table.waffle td {
    padding: 1px 2px;
    vertical-align: middle;
    font-size: 7pt;
    overflow: hidden;
}
table.waffle th, table.waffle td:not(.s2):not(.s15):not(.s16):not(.s17):not(.s18):not(.s19):not(.s20):not(.s22):not(.s23):not(.s24) {
    border: 1px solid #000;
}
.s15, .s17, .s19, .s20, .s22, .s23, .s24 {
    border: none !important;
}
.s0, .s1 {
    border: none !important;
    background-color: #fff;
    text-align: center;
    font-weight: bold;
    font-style: italic;
    color: #000;
    vertical-align: middle;
}
.s0 { font-size: 8pt; }
.s1 { font-size: 14pt; }
.s2, table.waffle td.s2 { background-color: #fff; border: none !important; }
.s3 {
    border-bottom: 1px solid #000;
    border-right: 1px solid #000;
    background-color: #fff;
    text-align: center;
    color: #000;
    font-size: 7pt;
    vertical-align: middle;
}
.s4 {
    border-bottom: 1px solid #000;
    border-right: 1px solid #000;
    background-color: #fff;
    text-align: center;
    color: #000;
    font-size: 8pt;
    vertical-align: middle;
}
.s5 {
    border-bottom: 1px solid #000;
    background-color: #fff;
    text-align: center;
    color: #000;
    font-size: 6pt;
    vertical-align: middle;
    padding: 1px;
}
.s6 {
    border-bottom: 1px solid #000;
    border-right: 1px solid #000;
    background-color: #fff;
    text-align: center;
    color: #000;
    font-size: 8pt;
    vertical-align: middle;
}
/* Employee name+position cell - enable word wrap */
td.employee-cell {
    text-align: center;
    font-size: 14pt;
    line-height: 1.2;
    word-wrap: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    padding: 2px 4px;
}
/* Employee header cell */
td.employee-header-cell {
    font-size: 14pt;
}
.s7 {
    border-bottom: 1px solid #000;
    border-right: 1px solid #000;
    background-color: #fff;
    text-align: center;
    color: #000;
    font-size: 9pt;
    vertical-align: middle;
}
.s8 {
    border-bottom: 1px solid #000;
    border-right: 1px solid #000;
    background-color: #fff;
    text-align: center;
    color: #000;
    font-size: 9pt;
    vertical-align: middle;
}
.s9 {
    border-bottom: 1px solid #000;
    border-right: 1px solid #000;
    background-color: #fff;
    text-align: center;
    color: #000;
    font-size: 9pt;
    vertical-align: middle;
}
.s13 {
    border-bottom: 1px solid #000;
    border-right: 1px solid #000;
    background-color: #fff;
    text-align: center;
    font-weight: bold;
    font-style: italic;
    color: #000;
    font-size: 11pt;
    vertical-align: middle;
}
.s14 {
    border-bottom: 1px solid #000;
    border-right: 1px solid #000;
    background-color: #fff;
    text-align: center;
    color: #000;
    font-family: "Times New Roman", Times, serif;
    font-size: 9pt;
    vertical-align: middle;
}
.s15, .s17, .s19, .s20, .s22, .s23, .s24 {
    background-color: #fff;
    text-align: left;
    color: #000;
    font-family: "Times New Roman", Times, serif;
    font-size: 12pt;
    vertical-align: middle;
    white-space: nowrap;
}
.s16, .s18 { border-bottom: 1px solid #000; }
.s16 { text-align: center; font-family: "Times New Roman", Times, serif; font-size: 12pt; }
.s18 { text-align: center; font-family: "Times New Roman", Times, serif; font-size: 14pt; }
.s19 { text-align: center; font-family: "Times New Roman", Times, serif; font-size: 12pt; }
.s20 { text-align: left; font-family: "Times New Roman", Times, serif; font-size: 12pt; }
.s23 { text-align: center; font-family: "Times New Roman", Times, serif; font-size: 12pt; }
/* Row heights */
tr[style*="height: 24px"] { height: 18px !important; }
tr[style*="height: 21px"] { height: 16px !important; }
tr[style*="height: 38px"] { height: 28px !important; }
tr[style*="height: 66px"] { height: 48px !important; }
tr[style*="height: 28px"] { height: 20px !important; }
tr[style*="height: 36px"] { height: 26px !important; }
tr[style*="height: 17px"] { height: 13px !important; }
tr[style*="height: 20px"] { height: 15px !important; }
tr[style*="height: 25px"] { height: 18px !important; }
tr[style*="height: 12px"] { height: 10px !important; }
tr[style*="height: 35px"] { height: 25px !important; }

/* Strikethrough for days outside contract period - centered line */
/* Uses pseudo-element with border for WeasyPrint PDF compatibility */
td.disabled-cell {
    position: relative;
    border: 1px solid #000 !important;
    background-color: #fff !important;
}
td.disabled-cell::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    border-top: 1px solid #000;
    transform: translateY(-50%);
}

/* Page break for pagination - use before for WeasyPrint */
.page-break {
    page-break-before: always;
    break-before: page;
    -webkit-column-break-before: always;
    page-break-after: avoid;
    break-after: avoid;
}
.page-break-after {
    page-break-after: always;
    break-after: page;
    -webkit-column-break-after: always;
}
/* Each page container for multi-page PDF output */
.page-container {
    width: 297mm;
    min-height: 210mm;
    background: #fff;
    margin: 0 auto 30px auto;
    padding: 5mm;
    box-sizing: border-box;
    /* Visible border for clear page separation in preview */
    border: 2px solid #333;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
/* Each page grid-container within container */
.page-container .ritz.grid-container {
    width: 100%;
    max-width: none;
    margin: 0;
}
/* Page separator - clear visual break between pages */
.page-separator {
    height: 20px;
    background: repeating-linear-gradient(
        45deg,
        #666,
        #666 10px,
        #fff 10px,
        #fff 20px
    );
    margin: 10px 0;
    border-top: 2px solid #333;
    border-bottom: 2px solid #333;
}
@media print {
    .page-break {
        page-break-before: always;
        break-before: page;
    }
    .page-break-after {
        page-break-after: always;
        break-after: page;
    }
    .page-container {
        width: auto !important;
        min-height: auto !important;
        background: none !important;
        border: none !important;
        box-shadow: none !important;
    }
    .page-separator {
        display: none;
    }
}
"""


def _wrap_tabel_html_for_pdf(content_html: str) -> str:
    """Обгортає HTML табеля у повний документ з вбудованим CSS для друку."""
    # Remove external stylesheet link and add embedded CSS
    content_html = content_html.replace('<link rel="stylesheet" href="sheet.css">', '')
    return f'<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"><title>Табель обліку робочого часу</title><style type="text/css">{TABEL_CSS}</style></head><body>{content_html}</body></html>'


def _generate_pdf_with_weasyprint(html_content: str, output_path: Path) -> None:
    """Генерує PDF з HTML контенту використовуючи WeasyPrint."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        html_path = f.name

    try:
        if not os.path.exists(WEASYPRINT_EXE):
            raise RuntimeError(f"WeasyPrint not found at: {WEASYPRINT_EXE}")

        result = subprocess.run(
            [WEASYPRINT_EXE, html_path, str(output_path)],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            raise RuntimeError(f"WeasyPrint failed: {result.stderr or 'Unknown error'}")

    finally:
        if os.path.exists(html_path):
            os.remove(html_path)


class TabelTab(QWidget):
    """Tab for viewing and managing monthly timesheet tables."""

    data_changed = pyqtSignal()

    def __init__(self) -> None:
        """Initialize tab."""
        super().__init__()
        self._current_month: int = date.today().month
        self._current_year: int = date.today().year
        self._archive_visible: bool = False
        self._correction_months: list[dict] = []
        self._current_correction_month: int | None = None
        self._current_correction_year: int | None = None
        self._approval_button: QPushButton | None = None
        self._warning_widget: QLabel | None = None
        self._setup_ui()
        self._connect_signals()
        self._load_archive_list()
        self._update_correction_tabs()
        self._check_show_warning()
        self._load_tabel()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Warning banner (hidden by default)
        self._warning_widget = QLabel("⚠ Увага: Табель необхідно згенерувати та погодити з кадрами до 10 числа")
        self._warning_widget.setStyleSheet("""
            QLabel {
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 4px;
                padding: 8px 12px;
                color: #856404;
                font-weight: bold;
            }
        """)
        self._warning_widget.setVisible(False)
        layout.addWidget(self._warning_widget)

        # Approval status banner (hidden by default)
        self._approval_banner = QLabel()
        self._approval_banner.setVisible(False)
        layout.addWidget(self._approval_banner)

        # Top toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        layout.addWidget(toolbar)

        # Month/year selection
        self.month_combo = QComboBox()
        self.month_combo.setMinimumWidth(100)
        self.month_combo.addItems(MONTHS_UKR)
        toolbar.addWidget(self.month_combo)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2100)
        self.year_spin.setSuffix(" р.")
        self.year_spin.setMinimumWidth(80)
        toolbar.addWidget(self.year_spin)

        toolbar.addSeparator()

        # Refresh action
        refresh_action = QAction("🔄 Оновити", self)
        refresh_action.triggered.connect(self._load_tabel)
        toolbar.addAction(refresh_action)

        # Print action
        print_action = QAction("🖨️ Друкувати PDF", self)
        print_action.triggered.connect(self._print_pdf)
        toolbar.addAction(print_action)

        # HR Approval button (initially hidden)
        self._approval_button = QAction("✓ Погоджено з кадрами", self)
        self._approval_button.triggered.connect(self._on_hr_approval_clicked)
        self._approval_button.setVisible(False)
        toolbar.addAction(self._approval_button)

        toolbar.addSeparator()

        # Zoom control
        toolbar.addWidget(QLabel("Масштаб:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 150)
        self.zoom_slider.setValue(int(self.PRINT_ZOOM * 100))
        self.zoom_slider.setFixedWidth(80)
        self.zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        toolbar.addWidget(self.zoom_slider)

        self.zoom_input = QLineEdit()
        self.zoom_input.setText(f"{int(self.PRINT_ZOOM * 100)}")
        self.zoom_input.setFixedWidth(40)
        self.zoom_input.setValidator(QIntValidator(50, 150))
        self.zoom_input.editingFinished.connect(self._on_zoom_input_changed)
        toolbar.addWidget(self.zoom_input)

        self.zoom_label = QLabel("%")
        self.zoom_label.setFixedWidth(15)
        toolbar.addWidget(self.zoom_label)

        # Width control
        toolbar.addWidget(QLabel("Ширина:"))
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(80, 200)
        self.width_slider.setValue(self.PRINT_WIDTH_PERCENT)
        self.width_slider.setFixedWidth(80)
        self.width_slider.valueChanged.connect(self._on_width_slider_changed)
        toolbar.addWidget(self.width_slider)

        self.width_input = QLineEdit()
        self.width_input.setText(str(self.PRINT_WIDTH_PERCENT))
        self.width_input.setFixedWidth(40)
        self.width_input.setValidator(QIntValidator(80, 200))
        self.width_input.editingFinished.connect(self._on_width_input_changed)
        toolbar.addWidget(self.width_input)

        self.width_label = QLabel("%")
        self.width_label.setFixedWidth(15)
        toolbar.addWidget(self.width_label)

        toolbar.addSeparator()

        # Employees per page control
        toolbar.addWidget(QLabel("Працівників на стор.:"))
        self.employees_per_page_spin = QSpinBox()
        self.employees_per_page_spin.setRange(0, 100)
        self.employees_per_page_spin.setValue(self.EMPLOYEES_PER_PAGE)
        self.employees_per_page_spin.setSpecialValueText("Без обмеження")
        self.employees_per_page_spin.setFixedWidth(100)
        self.employees_per_page_spin.valueChanged.connect(self._on_employees_per_page_changed)
        toolbar.addWidget(self.employees_per_page_spin)

        # Apply button
        apply_btn = QPushButton("Застосувати")
        apply_btn.clicked.connect(self._apply_scaling)
        toolbar.addWidget(apply_btn)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Archive button
        archive_action = QAction("📁 Архів", self)
        archive_action.triggered.connect(self._toggle_archive)
        toolbar.addAction(archive_action)

        # Content area - split between archive list and preview
        content = QHBoxLayout()
        content.setSpacing(10)
        layout.addLayout(content, 1)

        # Archive panel (hidden by default)
        self.archive_stack = QStackedWidget()
        self.archive_list = QTreeWidget()
        self.archive_list.setHeaderLabels(["Табель"])
        self.archive_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.archive_list.itemClicked.connect(self._on_archive_item_clicked)
        self.archive_list.setIndentation(15)
        self.archive_stack.addWidget(self.archive_list)

        # Archive placeholder when empty
        archive_placeholder = QLabel("Немає архівних табелів")
        archive_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        archive_placeholder.setStyleSheet("color: #888; font-style: italic;")
        self.archive_stack.addWidget(archive_placeholder)

        archive_frame = QFrame()
        archive_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        archive_frame.setMinimumWidth(200)
        archive_frame.setMaximumWidth(250)
        archive_frame.setVisible(False)
        self.archive_frame = archive_frame

        archive_layout = QVBoxLayout(archive_frame)
        archive_layout.addWidget(QLabel("<b>Архів табелів</b>"))
        archive_layout.addWidget(self.archive_stack)

        # Restore button in archive
        self.restore_btn = QPushButton("Відновити")
        self.restore_btn.clicked.connect(self._restore_from_archive)
        self.restore_btn.setEnabled(False)
        archive_layout.addWidget(self.restore_btn)

        content.addWidget(archive_frame)

        # Tab widget for tabel views (main + archive tabs)
        self.tab_widget = QTabWidget()
        self.tab_widget.setMovable(True)
        content.addWidget(self.tab_widget, 1)

        # Create main tabel web view
        self.web_view = QWebEngineView()
        self.web_view.setSizePolicy(
            self.web_view.sizePolicy().Policy.Expanding,
            self.web_view.sizePolicy().Policy.Expanding
        )
        self.tab_widget.addTab(self.web_view, "Табель")

        # Store archive tab info: tab_index -> archive_data
        self._archive_tabs: dict[int, dict] = {}
        self._archive_tab_counter = 0

        # Excel-style tabs at bottom (navigation between correction modes)
        tabs_container = QWidget()
        tabs_layout = QHBoxLayout(tabs_container)
        tabs_layout.setContentsMargins(0, 5, 0, 0)
        tabs_layout.setSpacing(2)

        # Tab button group
        self.tab_button_group = QButtonGroup(tabs_container)
        self.tab_button_group.setExclusive(True)

        # Normal tabel tab
        self.normal_tab_btn = QPushButton("Табель")
        self.normal_tab_btn.setCheckable(True)
        self.normal_tab_btn.setChecked(True)
        self.normal_tab_btn.setFixedHeight(28)
        self.normal_tab_btn.setFixedWidth(170)
        self.normal_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-bottom: 2px solid #d0d0d0;
                border-radius: 0px;
                padding: 4px 15px;
                font-size: 11px;
                text-align: center;
            }
            QPushButton:checked {
                background-color: #ffffff;
                border-bottom: 3px solid #217346;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
            QPushButton:hover:checked {
                background-color: #ffffff;
            }
        """)
        self.tab_button_group.addButton(self.normal_tab_btn)
        tabs_layout.addWidget(self.normal_tab_btn)

        # Container for correction tabs (sits between normal tab and + button)
        self.correction_tabs_widget = QWidget()
        self.correction_tabs_widget.setStyleSheet("background: transparent;")
        self.correction_tabs_layout = QHBoxLayout(self.correction_tabs_widget)
        self.correction_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.correction_tabs_layout.setSpacing(2)
        tabs_layout.addWidget(self.correction_tabs_widget)

        # Add '+' button AFTER correction tabs container (so it's always last)
        self.add_correction_btn = QPushButton("+")
        self.add_correction_btn.setFixedSize(28, 28)
        self.add_correction_btn.setToolTip("Додати корегуючий табель")
        self.add_correction_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 0px;
                font-size: 14px;
                font-weight: bold;
                color: #217346;
            }
            QPushButton:hover {
                background-color: #e8f5e9;
                border-color: #217346;
            }
        """)
        self.add_correction_btn.clicked.connect(self._on_add_correction_clicked)
        tabs_layout.addWidget(self.add_correction_btn)

        # Connect normal tab button
        self.normal_tab_btn.clicked.connect(self._on_normal_tab_clicked)

        # Add spacer
        tabs_layout.addStretch()

        layout.addWidget(tabs_container)

        # Status bar
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.status_label)

        # Initialize display
        self._update_month_display()

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        self.year_spin.valueChanged.connect(self._on_year_changed)

    @property
    def _is_correction(self) -> bool:
        """Return True if correction tabel is selected."""
        return self._current_correction_month is not None

    def _on_normal_tab_clicked(self) -> None:
        """Called when normal tabel tab is clicked."""
        self._current_correction_month = None
        self._current_correction_year = None
        
        # Restore normal tab button style
        self.normal_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-bottom: 2px solid #d0d0d0;
                border-radius: 0px;
                padding: 4px 15px;
                font-size: 11px;
                text-align: center;
            }
            QPushButton:checked {
                background-color: #ffffff;
                border-bottom: 3px solid #217346;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
            QPushButton:hover:checked {
                background-color: #ffffff;
            }
        """)

        self._load_tabel()
        self._check_show_warning()

    def _open_archive_in_new_tab(self, archive_data: dict, display_name: str) -> int:
        """Open an archived tabel in a new tab.

        Args:
            archive_data: Archive data dictionary
            display_name: Name to show on tab

        Returns:
            int: Index of the new tab
        """
        self._archive_tab_counter += 1

        # Create new web view for this archive
        web_view = QWebEngineView()
        web_view.setSizePolicy(
            web_view.sizePolicy().Policy.Expanding,
            web_view.sizePolicy().Policy.Expanding
        )

        # Generate HTML from archive
        html = reconstruct_tabel_html_from_archive(archive_data)

        # Set HTML with template directory
        template_dir = Path(__file__).parent.parent / "templates" / "tabel"
        web_view.setHtml(html, QUrl.fromLocalFile(str(template_dir) + "/"))

        # Create close button
        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                font-size: 12px;
                font-weight: bold;
                color: #888;
            }
            QToolButton:hover {
                background-color: #ffcccc;
                border-radius: 2px;
                color: #cc0000;
            }
        """)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Add web view as tab content - addTab returns the actual index of the new tab
        tab_index = self.tab_widget.addTab(web_view, f"📄 {display_name}")

        # Connect close button (use closure to capture current index)
        close_btn.clicked.connect(lambda checked=False, idx=tab_index: self._close_archive_tab(idx))

        # Set close button on tab (Qt6 uses QTabBar.TabButtonPosition enum)
        from PyQt6.QtWidgets import QTabBar
        self.tab_widget.tabBar().setTabButton(tab_index, QTabBar.ButtonPosition.RightSide, close_btn)
        self.tab_widget.setCurrentIndex(tab_index)

        # Store archive data for this tab
        self._archive_tabs[tab_index] = archive_data

        # Connect signal to apply print scaling
        web_view.loadFinished.connect(self._apply_print_scaling)

        return tab_index

    def _close_archive_tab(self, tab_index: int) -> None:
        """Close a specific archive tab."""
        if tab_index <= 0:
            return

        # Remove from archive tabs dict
        if tab_index in self._archive_tabs:
            del self._archive_tabs[tab_index]

        # Get the widget before removing (to properly clean up)
        widget = self.tab_widget.widget(tab_index)
        if widget:
            widget.deleteLater()

        # Remove tab
        self.tab_widget.removeTab(tab_index)

        # Update indices in _archive_tabs (shift all indices >= removed index down by 1)
        new_archive_tabs = {}
        for idx, data in self._archive_tabs.items():
            if idx > tab_index:
                new_archive_tabs[idx - 1] = data
            elif idx < tab_index:
                new_archive_tabs[idx] = data
        self._archive_tabs = new_archive_tabs

    def _update_correction_tabs(self) -> None:
        """Update the list of correction tabs based on existing correction records."""
        from backend.services.tabel_approval_service import TabelApprovalService
        from backend.core.database import get_db_context

        # Configure layout to minimize size
        self.correction_tabs_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.correction_tabs_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        # Clear existing correction tabs (including spacers)
        while self.correction_tabs_layout.count():
            item = self.correction_tabs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


        # Get correction months from locked months with corrections
        with get_db_context() as db:
            approval_service = TabelApprovalService(db)
            self._correction_months = approval_service.get_correction_months()

        # Create tab buttons for each correction month (max 4)
        for correction in self._correction_months:
            corr_month = correction.get("correction_month")
            corr_year = correction.get("correction_year")
            month_name = MONTHS_UKR[corr_month - 1]

            # Tab label shows which month is being corrected
            tab_text = f"Корег. ({month_name})"

            tab_btn = QPushButton(tab_text)
            tab_btn.setCheckable(True)
            tab_btn.setFixedHeight(28)
            tab_btn.setFixedWidth(170)
            tab_btn.setProperty("correction_month", corr_month)
            tab_btn.setProperty("correction_year", corr_year)
            tab_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #d0d0d0;
                    border-bottom: 2px solid #d0d0d0;
                    border-radius: 0px;
                    padding: 4px 25px 4px 15px;
                    font-size: 11px;
                    text-align: center;
                }
                QPushButton:checked {
                    background-color: #ffffff;
                    border-bottom: 3px solid #217346;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #f0f0f0;
                }
                QPushButton:hover:checked {
                    background-color: #ffffff;
                }
            """)
            tab_btn.clicked.connect(lambda checked, m=corr_month, y=corr_year: self._on_correction_tab_clicked(m, y))

            # Add close button to the tab
            from PyQt6.QtWidgets import QToolButton
            close_btn = QToolButton(tab_btn)
            close_btn.setText("×")
            close_btn.setFixedSize(16, 16)
            close_btn.setCursor(Qt.CursorShape.ArrowCursor)
            close_btn.setToolTip("Видалити корегуючий табель")
            close_btn.setStyleSheet("""
                QToolButton {
                    border: none;
                    background: transparent;
                    font-weight: bold;
                    color: #999;
                    font-size: 14px;
                }
                QToolButton:hover {
                    color: #d32f2f;
                    background: rgba(211, 47, 47, 0.1);
                    border-radius: 8px;
                }
            """)
            # Connect close signal - use lambda to capture specific month/year
            # blockSignals(True) prevents the tab from being selected when closing? 
            # No, because close_btn is a child, clicking it might propagate? 
            # QToolButton click doesn't propagate to parent usually unless ignored.
            close_btn.clicked.connect(lambda checked=False, m=corr_month, y=corr_year: self._close_correction_tab(m, y))

            # Position close button on the right
            from PyQt6.QtWidgets import QHBoxLayout
            btn_layout = QHBoxLayout(tab_btn)
            btn_layout.setContentsMargins(0, 0, 4, 0)
            btn_layout.setSpacing(0)
            btn_layout.addStretch()
            btn_layout.addWidget(close_btn)

            self.correction_tabs_layout.addWidget(tab_btn)
            self.tab_button_group.addButton(tab_btn)

    def _switch_to_correction_tab(self, month: int, year: int) -> None:
        """Switch to correction tab for specified month/year."""
        # Find the max sequence for this correction month
        max_seq = 1
        for corr in self._correction_months:
            if corr.get("correction_month") == month and corr.get("correction_year") == year:
                max_seq = corr.get("correction_sequence", 1)
                break

        # Set correction state
        self._current_correction_month = month
        self._current_correction_year = year
        self._current_correction_sequence = max_seq

        # Uncheck all correction tab buttons and check the matching one
        for btn in self.tab_button_group.buttons():
            btn.setChecked(False)

        # Find and check the matching correction tab button
        for btn in self.tab_button_group.buttons():
            if btn.property("correction_month") == month and btn.property("correction_year") == year:
                btn.setChecked(True)
                break

        # Update normal tab button style
        self.normal_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8;
                border: 1px solid #999;
                border-bottom: none;
                border-radius: 3px 3px 0 0;
                padding: 4px 15px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #d8d8d8;
            }
        """)

        # Load tabel for correction month
        self._load_tabel()
        self._check_show_warning()

    def _on_correction_tab_clicked(self, month: int, year: int) -> None:
        """Called when a correction tab is clicked."""
        # Find the max sequence for this correction month
        max_seq = 1
        for corr in self._correction_months:
            if corr.get("correction_month") == month and corr.get("correction_year") == year:
                max_seq = corr.get("correction_sequence", 1)
                break

        self._current_correction_month = month
        self._current_correction_year = year
        self._current_correction_sequence = max_seq
        self._load_tabel()
        self._check_show_warning()


    def _close_correction_tab(self, month: int, year: int) -> None:
        """Called when correction tab close button is clicked."""
        from PyQt6.QtWidgets import QMessageBox
        from backend.services.tabel_approval_service import TabelApprovalService
        from backend.core.database import get_db_context

        # Confirm deletion
        month_name = MONTHS_UKR[month - 1]
        reply = QMessageBox.question(
            self,
            "Видалити корегуючий табель?",
            f"Ви впевнені, що хочете видалити корегуючий табель за {month_name} {year}?\n"
            "Цю дію неможливо відмінити.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Delete correction
        with get_db_context() as db:
            approval_service = TabelApprovalService(db)
            success = approval_service.delete_correction(month, year)

            if not success:
                QMessageBox.warning(self, "Помилка", "Не вдалося видалити корегуючий табель.")
                return

        # Update UI
        self._update_correction_tabs()

        # If we were viewing the deleted tab, switch to main tabel
        if (self._current_correction_month == month and 
            self._current_correction_year == year and 
            self._is_correction):
            self._on_normal_tab_clicked()

    def _on_add_correction_clicked(self) -> None:
        """Called when '+' button is clicked to add new correction."""
        from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox, QDialogButtonBox
        from backend.services.tabel_approval_service import TabelApprovalService
        from backend.core.database import get_db_context

        # Create month picker dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Додати корегуючий табель")
        dialog.setMinimumWidth(300)

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel("Оберіть місяць для корегуючого табеля:")
        layout.addWidget(info_label)

        # Generate list of all previous months (treat as locked by default)
        from datetime import date
        current_date = date.today()
        current_month = current_date.month
        current_year = current_date.year

        # Generate previous months (up to 12 months back)
        available_months = []
        for i in range(1, 13):  # Up to 12 months back
            month = current_month - i
            year = current_year
            if month <= 0:
                month += 12
                year -= 1
            available_months.append((month, year))

        if not available_months:
            QMessageBox.information(
                self,
                "Інформація",
                "Немає заблокованих місяців.\n"
                "Спочатку потрібно створити та погодити основний табель."
            )
            return

        # Month/Year selector
        selector_layout = QHBoxLayout()

        selector_layout.addWidget(QLabel("Місяць:"))
        month_combo = QComboBox()
        for month, year in available_months:
            month_name = MONTHS_UKR[month - 1]
            month_combo.addItem(f"{month_name} {year}", (month, year))
        selector_layout.addWidget(month_combo)

        layout.addLayout(selector_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Get selected month
        selected_data = month_combo.currentData()
        if not selected_data:
            return

        selected_month, selected_year = selected_data

        with get_db_context() as db:
            approval_service = TabelApprovalService(db)

            # Get or create correction sequence
            correction_sequence = approval_service.get_or_create_correction_sequence(
                selected_month, selected_year
            )

            # Create a new correction approval record
            approval_service.record_generation(
                month=selected_month,
                year=selected_year,
                is_correction=True,
                correction_month=selected_month,
                correction_year=selected_year,
                correction_sequence=correction_sequence
            )

        # Refresh correction tabs
        self._update_correction_tabs()

        # Switch to the new correction tab
        self._switch_to_correction_tab(selected_month, selected_year)

        QMessageBox.information(
            self,
            "Корегуючий табель",
            f"Створено корегуючий табель для {MONTHS_UKR[selected_month - 1]} {selected_year}.\n"
            f"Відобразяться записи з позначкою is_correction для цього місяця."
        )

    def _on_month_changed(self) -> None:
        """Called when month is selected from combo."""
        self._current_month = self.month_combo.currentIndex() + 1
        self._load_tabel()
        self._check_show_warning()

    def _on_year_changed(self) -> None:
        """Called when year is changed."""
        self._current_year = self.year_spin.value()
        self._load_tabel()
        self._check_show_warning()

    def _on_zoom_slider_changed(self, value: int) -> None:
        """Called when zoom slider is moved."""
        self.zoom_input.blockSignals(True)
        self.zoom_input.setText(str(value))
        self.zoom_input.blockSignals(False)
        self.PRINT_ZOOM = value / 100
        self._apply_print_scaling()

    def _on_zoom_input_changed(self) -> None:
        """Called when zoom input is edited."""
        try:
            value = int(self.zoom_input.text())
            if 50 <= value <= 150:
                self.zoom_slider.blockSignals(True)
                self.zoom_slider.setValue(value)
                self.zoom_slider.blockSignals(False)
                self.PRINT_ZOOM = value / 100
                self._apply_print_scaling()
        except ValueError:
            pass

    def _on_width_slider_changed(self, value: int) -> None:
        """Called when width slider is moved."""
        self.width_input.blockSignals(True)
        self.width_input.setText(str(value))
        self.width_input.blockSignals(False)
        self.PRINT_WIDTH_PERCENT = value
        self._apply_print_scaling()

    def _on_width_input_changed(self) -> None:
        """Called when width input is edited."""
        try:
            value = int(self.width_input.text())
            if 80 <= value <= 200:
                self.width_slider.blockSignals(True)
                self.width_slider.setValue(value)
                self.width_slider.blockSignals(False)
                self.PRINT_WIDTH_PERCENT = value
                self._apply_print_scaling()
        except ValueError:
            pass

    def _on_employees_per_page_changed(self, value: int) -> None:
        """Called when employees per page spin is changed."""
        self.EMPLOYEES_PER_PAGE = value

    def _apply_scaling(self) -> None:
        """Apply current zoom/width settings to preview."""
        self._apply_print_scaling()
        # Reload tabel with new employees per page setting
        self._load_tabel()

    def _update_month_display(self) -> None:
        """Update month display controls."""
        self.month_combo.setCurrentIndex(self._current_month - 1)
        self.year_spin.setValue(self._current_year)

    def _toggle_archive(self) -> None:
        """Toggle archive panel visibility."""
        self._archive_visible = not self._archive_visible
        self.archive_frame.setVisible(self._archive_visible)

    def _load_archive_list(self) -> None:
        """Load list of archived tabels from JSON archives with expandable corrections."""
        self.archive_list.clear()

        # Use the new list_tabel_archives function
        archive_data = list_tabel_archives()
        main_tabels = archive_data.get("main_tabels", [])
        orphan_corrections = archive_data.get("orphan_corrections", [])

        # Add main tabels with their corrections
        for main in main_tabels:
            main_display = main["display_name"]
            if main.get("is_approved"):
                main_display += " ✓"
            main_item = QTreeWidgetItem(self.archive_list, [main_display])
            main_item.setData(0, Qt.ItemDataRole.UserRole, main)

            # Add expand/collapse indicator based on whether there are corrections
            has_corrections = len(main.get("corrections", [])) > 0
            main_item.setExpanded(False)  # Start collapsed

            # Add correction children if any
            for corr in main.get("corrections", []):
                corr_display = corr["display_name"]
                if corr.get("is_approved"):
                    corr_display += " ✓"
                corr_item = QTreeWidgetItem(main_item, [corr_display])
                corr_item.setData(0, Qt.ItemDataRole.UserRole, corr)

            # Add "+ X corrections" indicator if there are corrections
            if has_corrections:
                corr_count = len(main.get("corrections", []))
                approved_suffix = " ✓" if main.get("is_approved") else ""
                main_item.setText(0, f"{main['display_name']} (+{corr_count}){approved_suffix}")

        # Add orphan corrections at the top level
        for corr in orphan_corrections:
            corr_item = QTreeWidgetItem(self.archive_list, [corr["display_name"]])
            corr_item.setData(0, Qt.ItemDataRole.UserRole, corr)
            if corr.get("is_approved"):
                corr_item.setText(0, corr["display_name"] + " ✓")

        if main_tabels or orphan_corrections:
            self.archive_stack.setCurrentIndex(0)
            self.archive_list.expandAll()
        else:
            self.archive_stack.setCurrentIndex(1)

    def _on_archive_item_clicked(self, item: QTreeWidgetItem, column: int = 0) -> None:
        """Called when archive item is clicked."""
        # Check if item has archive data
        archive_info = item.data(0, Qt.ItemDataRole.UserRole)
        if archive_info:
            self.restore_btn.setEnabled(True)
        else:
            # This is a parent item without data (just a label)
            self.restore_btn.setEnabled(False)

    def _restore_from_archive(self) -> None:
        """Restore selected tabel from archive in a new tab."""
        current = self.archive_list.currentItem()
        if not current:
            return

        archive_info = current.data(0, Qt.ItemDataRole.UserRole)
        if not archive_info:
            return

        archive_path = archive_info["path"]
        # Remove " ✓" suffix if present for display name
        display_name = archive_info["display_name"].replace(" ✓", "")

        # Load full archive data
        full_archive_data = reconstruct_tabel_from_archive(archive_path)

        # Open in new tab
        self._open_archive_in_new_tab(full_archive_data, display_name)

    def _get_days_in_month(self) -> int:
        """Get number of days in current month."""
        return calendar.monthrange(self._current_year, self._current_month)[1]

    def _load_tabel(self, archive_data: dict | None = None, target_web_view: QWebEngineView | None = None) -> None:
        """Load and render tabel for current month.

        Args:
            archive_data: Optional archive data dict. If provided, loads from archive
                         instead of regenerating from database.
            target_web_view: Optional web view to load into. If None, uses main tab.
        """
        self.status_label.setText("Формування табеля...")

        # Define template_dir here so it's available in except block
        template_dir = Path(__file__).parent.parent / "templates" / "tabel"

        # Use provided web view or the main one
        web_view = target_web_view if target_web_view else self.web_view

        # Determine which month/year to use
        # In correction mode, use correction month/year; otherwise use selected month/year
        if self._is_correction and self._current_correction_month and self._current_correction_year:
            display_month = self._current_correction_month
            display_year = self._current_correction_year
            tabel_month = self._current_correction_month
            tabel_year = self._current_correction_year
        else:
            display_month = self._current_month
            display_year = self._current_year
            tabel_month = self._current_month
            tabel_year = self._current_year

        try:
            if archive_data:
                # Load from archive, but REGENERATE from database to ensure full data
                # We use the archive purely for metadata (month, year, settings)
                
                # Extract settings from archive to preserve history where possible
                settings = archive_data.get("settings", {})
                inst_name = settings.get("institution_name", DEFAULT_INSTITUTION_NAME)
                edrpou = settings.get("edrpou_code", DEFAULT_EDRPOU_CODE)
                dept_name = settings.get("department_name", "") # Pass this new param
                
                html = generate_tabel_html(
                    month=tabel_month,
                    year=tabel_year,
                    institution_name=inst_name,
                    edrpou_code=edrpou,
                    department_name=dept_name,
                    is_correction=self._is_correction,
                    correction_month=self._current_correction_month if self._is_correction else None,
                    correction_year=self._current_correction_year if self._is_correction else None,
                )
                self.status_label.setText(f"Табель з архіву (відновлено з БД): {MONTHS_UKR[display_month - 1]} {display_year}")
            else:
                # Get institution settings
                from backend.models.settings import SystemSettings
                from backend.core.database import get_db_context

                institution_name = ""
                edrpou_code = ""
                department_name = ""

                with get_db_context() as db:
                    institution_name = SystemSettings.get_value(db, "university_name", "")
                    edrpou_code = SystemSettings.get_value(db, "edrpou_code", "")
                    department_name = SystemSettings.get_value(db, "department_name", "")

                # Generate HTML using Jinja2 template
                html = generate_tabel_html(
                    month=tabel_month,
                    year=tabel_year,
                    institution_name=institution_name,
                    edrpou_code=edrpou_code,
                    department_name=department_name,
                    employees_per_page=self.EMPLOYEES_PER_PAGE if self.EMPLOYEES_PER_PAGE > 0 else 0,
                    is_correction=self._is_correction,
                    correction_month=self._current_correction_month if self._is_correction else None,
                    correction_year=self._current_correction_year if self._is_correction else None,
                )

            # Load into web view - use absolute path to template directory
            web_view.setHtml(html, QUrl.fromLocalFile(str(template_dir) + "/"))

            # Connect signal to apply print scaling and minimize empty columns after load
            web_view.loadFinished.connect(self._apply_print_scaling)

            # Update status
            month_name = MONTHS_UKR[display_month - 1]
            self.status_label.setText(f"Табель: {month_name} {display_year}")

        except Exception as e:
            import traceback
            error_msg = str(e) if str(e) else repr(e)
            tb = traceback.format_exc()
            self.status_label.setText(f"Помилка формування табеля: {error_msg}")
            # Show error in web view for debugging
            error_html = f"""
            <html><head><style>body {{ font-family: Arial; padding: 20px; }}</style></head>
            <body>
                <h2 style="color: red;">Помилка формування табеля</h2>
                <p><b>Тип помилки:</b> {type(e).__name__}</p>
                <p><b>Помилка:</b> {error_msg}</p>
                <pre style="background: #f5f5f5; padding: 10px; overflow: auto;">{tb}</pre>
                <p><b>Шлях до шаблону:</b> {template_dir}</p>
            </body></html>
            """
            self.web_view.setHtml(error_html)

    def _apply_print_scaling(self) -> None:
        """Apply print scaling to match preview with print output."""
        zoom = self.PRINT_ZOOM
        width_percent = self.PRINT_WIDTH_PERCENT
        js_code = f"""
        (function() {{
            // Apply scaling to all containers (each page has its own)
            const containers = document.querySelectorAll('.ritz.grid-container');
            containers.forEach((container) => {{
                container.style.zoom = '{zoom}';
                container.style.width = '{width_percent}%';
            }});
        }})();
        """
        self.web_view.page().runJavaScript(js_code)

    def _minimize_empty_columns(self) -> None:
        """Minimize width of columns that have no data."""
        js_code = """
        (function() {
            // Find all s5-vertical header cells (absence type columns)
            const headerCells = document.querySelectorAll('td.s5-vertical');
            headerCells.forEach((headerCell, index) => {
                // Get all cells in this column (same cellIndex across all rows)
                const cellIndex = headerCell.cellIndex;
                const table = headerCell.closest('table');
                const rows = table.querySelectorAll('tr');
                let hasData = false;

                // Check all data rows (skip header rows)
                for (let i = 4; i < rows.length - 1; i++) {
                    const cells = rows[i].querySelectorAll('td, th');
                    if (cells[cellIndex]) {
                        const text = cells[cellIndex].textContent.trim();
                        // Check employee data columns (after day columns, before totals)
                        if (cellIndex >= 18 && cellIndex <= 29) {
                            if (text !== '' && text !== '0' && text !== '0,00') {
                                hasData = true;
                                break;
                            }
                        }
                    }
                }

                // If no data in column, minimize width
                if (!hasData) {
                    const col = table.querySelectorAll('colgroup col')[cellIndex];
                    if (col) {
                        col.style.width = '15px';
                    }
                    // Also set min-width on header cell
                    headerCell.style.minWidth = '15px';
                    headerCell.style.width = '15px';
                }
            });
        })();
        """
        self.web_view.page().runJavaScript(js_code)

    # Print settings (defaults for zoom, can be adjusted by user)
    PRINT_ZOOM = 0.70
    PRINT_WIDTH_PERCENT = 97
    EMPLOYEES_PER_PAGE = 10  # employees per page

    def _print_pdf(self) -> None:
        """Export tabel to PDF (uses existing implementation)."""
        from PyQt6.QtWidgets import QFileDialog

        month_name = MONTHS_UKR[self._current_month - 1]
        if self._is_correction:
            filename = f"Табель_корегуючий_{month_name}_{self._current_year}.pdf"
        else:
            filename = f"Табель_{month_name}_{self._current_year}.pdf"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Зберегти табель PDF",
            filename,
            "PDF Files (*.pdf)"
        )

        if not filepath:
            return

        self._print_filepath = filepath
        self._do_print_pdf()

    def _do_print_pdf(self) -> None:
        """Actually print to PDF with optional title page from DOCX."""
        import traceback
        from pathlib import Path
        from datetime import datetime
        from backend.core.database import get_db_context
        from backend.models.settings import SystemSettings
        from backend.models.staff import Staff
        from backend.services.tabel_service import (
            MONTHS_GENITIVE, format_initials
        )

        filepath = Path(self._print_filepath)
        final_filepath = filepath

        # Create temp directory in storage\temp
        storage_dir = Path(__file__).parent.parent.parent / "storage" / "temp"
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique temp folder name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = storage_dir / f"tabel_{timestamp}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Setup progress dialog
        progress = QProgressDialog("Підготовка до друку...", "Скасувати", 0, 4, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setWindowTitle("Експорт PDF")
        
        # Ensure dialog is visible immediately
        progress.show()
        QApplication.processEvents()

        try:
            if progress.wasCanceled():
                return
            
            progress.setLabelText("Генерація PDF з табелю...")
            progress.setValue(1)
            QApplication.processEvents()

            # Configure page layout - use 0 margins, rely on CSS template margins
            page_layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Landscape,
                QMarginsF(0, 0, 0, 0),
                QPageLayout.Unit.Millimeter
            )

            # Step 1: Capture web view PDF to temp file
            tabel_pdf_path = temp_dir / "tabel.pdf"
            self.web_view.page().printToPdf(
                str(tabel_pdf_path),
                page_layout
            )

            # Wait for PDF to be generated (Qt6 printToPdf is async)
            # from PyQt6.QtWidgets import QApplication  # Already imported at top
            from PyQt6.QtCore import QEventLoop

            max_wait = 50  # 5 seconds max
            wait_count = 0
            while not tabel_pdf_path.exists() and wait_count < max_wait:
                QApplication.processEvents()
                loop = QEventLoop()
                QTimer.singleShot(100, loop.quit)
                loop.exec()
                wait_count += 1
                
                if progress.wasCanceled():
                    return

            if not tabel_pdf_path.exists():
                raise Exception(f"Tabel PDF not generated after {max_wait * 0.1}s")

            if progress.wasCanceled():
                return
                
            progress.setLabelText("Генерація титульної сторінки...")
            progress.setValue(2)
            QApplication.processEvents()

            # Step 2: Generate title page if DOCX template exists
            # Determine template directory
            if self._is_correction:
                template_dir = Path(__file__).parent.parent / "templates" / "tabel_corection"
                docx_template = template_dir / "Title_tabel_corection.docx"
            else:
                template_dir = Path(__file__).parent.parent / "templates" / "tabel"
                docx_template = template_dir / "Title_tabel.docx"

            title_pdf_path = None
            if docx_template.exists():
                # Get institution settings
                with get_db_context() as db:
                    institution_name = SystemSettings.get_value(
                        db, "institution_name", DEFAULT_INSTITUTION_NAME
                    )
                    edrpou_code = SystemSettings.get_value(
                        db, "edrpou_code", DEFAULT_EDRPOU_CODE
                    )
                    department_name = SystemSettings.get_value(db, "dept_name", "")
                    department_abbr = SystemSettings.get_value(db, "dept_abbr", "")

                    # Get responsible person (specialist) by ID
                    specialist_id = SystemSettings.get_value(db, "dept_specialist_id", None)
                    if specialist_id and str(specialist_id) not in ("None", "none", ""):
                        if str(specialist_id).startswith("custom:"):
                            responsible_person = str(specialist_id)[7:]
                        else:
                            specialist_staff = db.query(Staff).get(int(specialist_id))
                            responsible_person = format_initials(specialist_staff.pib_nom) if specialist_staff else ""
                    else:
                        responsible_person = ""

                    # Get department head by ID
                    dept_head_id = SystemSettings.get_value(db, "dept_head_id", None)
                    if dept_head_id and str(dept_head_id) not in ("None", "none", ""):
                        if str(dept_head_id).startswith("custom:"):
                            department_head = str(dept_head_id)[7:]
                        else:
                            dept_head_staff = db.query(Staff).get(int(dept_head_id))
                            department_head = format_initials(dept_head_staff.pib_nom) if dept_head_staff else ""
                    else:
                        department_head = ""

                # Prepare title page data
                month_name = MONTHS_UKR[self._current_month - 1]
                month_genitive = MONTHS_GENITIVE[self._current_month - 1]

                # Combine department abbr and name without duplication
                if department_abbr and department_name:
                    # Check if abbr is already part of name to avoid duplication
                    if department_name.startswith(department_abbr):
                        department_full = department_name
                    else:
                        department_full = f"{department_abbr} {department_name}"
                elif department_abbr:
                    department_full = department_abbr
                else:
                    department_full = department_name

                title_data = {
                    "institution_name": institution_name,
                    "department_name": department_full.strip(),
                    "month_name": month_name,
                    "month_start": datetime(self._current_year, self._current_month, 1).strftime("%d.%m.%Y"),  # First day of month
                    "month_end": datetime(self._current_year, self._current_month, calendar.monthrange(self._current_year, self._current_month)[1]).strftime("%d.%m.%Y"),  # Last day of month
                    "year": str(self._current_year),
                    "edrpou_code": edrpou_code,
                    "generation_date": datetime.now().strftime("%d.%m.%Y"),
                    "responsible_person": responsible_person,
                    "department_head": department_head,
                    "correction_period_1": "",  # Will be filled for correction tabels
                    "correction_period_2": "",  # Will be filled for correction tabels
                }

                # For correction tabel, calculate correction periods
                if self._is_correction:
                    with get_db_context() as db:
                        from backend.models.attendance import Attendance
                        correction_records = db.query(Attendance).filter(
                            Attendance.date < datetime(self._current_year, self._current_month, 1).date()
                        ).all()

                        if correction_records:
                            # Find min and max dates
                            min_date = min(r.date for r in correction_records)
                            max_date = max(r.date for r in correction_records)

                            correction_month = min_date.month
                            correction_year = min_date.year
                            _, days_in_month = calendar.monthrange(correction_year, correction_month)

                            # Determine period range based on min/max dates
                            if min_date.day <= 15:
                                # First half included
                                period_start = datetime(correction_year, correction_month, 1).strftime("%d.%m.%Y")
                            else:
                                # Only second half
                                period_start = datetime(correction_year, correction_month, 16).strftime("%d.%m.%Y")

                            if max_date.day >= 16:
                                # Second half included
                                period_end = datetime(correction_year, correction_month, days_in_month).strftime("%d.%m.%Y")
                            else:
                                # Only first half
                                period_end = datetime(correction_year, correction_month, 15).strftime("%d.%m.%Y")

                            title_data["correction_period_1"] = period_start
                            title_data["correction_period_2"] = period_end

                # Populate DOCX and convert to PDF
                docx_path = temp_dir / "title.docx"
                populate_title_docx(docx_template, docx_path, title_data)

                title_pdf_path = temp_dir / "title.pdf"
                convert_docx_to_pdf(docx_path, title_pdf_path)

            if progress.wasCanceled():
                return

            progress.setLabelText("Об'єднання документів...")
            progress.setValue(3)
            QApplication.processEvents()
            
            # Step 3: Merge PDFs (title page + tabel)
            pdfs_to_merge = []
            if title_pdf_path and title_pdf_path.exists():
                pdfs_to_merge.append(title_pdf_path)

            if tabel_pdf_path.exists():
                pdfs_to_merge.append(tabel_pdf_path)

            merge_pdfs(pdfs_to_merge, final_filepath)

            progress.setValue(4)
            progress.setLabelText("Готово!")
            QApplication.processEvents()

            # SUCCESS: Clean up temp folder
            import shutil
            shutil.rmtree(temp_dir)
            
            progress.close()

        except Exception as e:
            progress.close()
            # ERROR: Preserve temp folder and create logs.txt
            # ERROR: Preserve temp folder and create logs.txt
            error_msg = f"""=== PDF Generation Error ===
Time: {datetime.now().isoformat()}
Error: {str(e)}
Traceback:
{traceback.format_exc()}
"""
            log_file = temp_dir / "logs.txt"
            log_file.write_text(error_msg, encoding="utf-8")
            logger.error(f"PDF generation failed, temp folder preserved: {temp_dir}", exc_info=True)

            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Помилка",
                f"Помилка генерації PDF:\n{str(e)}\n\nТимчасові файли збережено в:\n{temp_dir}"
            )
            return

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Успіх",
            f"Табель збережено:\n{final_filepath}"
        )

        # Record tabel generation and check if should show approval button
        try:
            with get_db_context() as db:
                from backend.services.tabel_approval_service import TabelApprovalService
                approval_service = TabelApprovalService(db)
                
                # Record that tabel was generated
                approval_service.record_generation(
                    month=self._current_month,
                    year=self._current_year,
                    is_correction=self._is_correction,
                    correction_month=self._current_correction_month if self._is_correction else None,
                    correction_year=self._current_correction_year if self._is_correction else None,
                    correction_sequence=self._current_correction_sequence if self._is_correction else 1
                )
                
                # Check if should show approval button
                status = approval_service.get_approval_status(
                    self._current_month,
                    self._current_year,
                    is_correction=self._is_correction
                )
                if status and not status.get("is_approved"):
                    self._approval_button.setVisible(True)
        except Exception as e:
            logger.error(f"Error recording tabel generation: {e}")

    def _archive_tabel(self, month: int, year: int, is_correction: bool = False,
                       correction_month: int | None = None, correction_year: int | None = None,
                       correction_sequence: int = 1) -> None:
        """Archive the current tabel in compact JSON format.

        Args:
            month: Month to archive
            year: Year to archive
            is_correction: Whether this is a correction tabel
            correction_month: Month being corrected (for corrections)
            correction_year: Year being corrected (for corrections)
            correction_sequence: Sequence number for corrections
        """
        try:
            from backend.core.database import get_db_context
            from backend.services.tabel_approval_service import TabelApprovalService

            # Get employee data for archive
            employees_data = []
            with get_db_context() as db:
                # Database context is already open

                from backend.services.tabel_service import get_employees_for_tabel
                
                # Use shared function to get EXACTLY the same data as the generated tabel
                employees_list, _, _, _ = get_employees_for_tabel(
                    db, month, year, is_correction, correction_month, correction_year
                )
                
                # Convert EmployeeData objects to dicts for JSON serialization
                for emp in employees_list:
                    # Convert EmployeeData to dict
                    emp_dict = {
                        "staff_id": 0, # Not available in EmployeeData, but not strictly needed for archive view
                        "pib_nom": emp.pib,
                        "position": emp.position,
                        "rate": float(emp.rate.replace(',', '.')) if emp.rate else 1.0,
                        "days": [],
                        "vacations": [] # Not stored in EmployeeData, reconstruction uses days codes
                    }
                    
                    # Convert days
                    for i, day in enumerate(emp.days):
                        emp_dict["days"].append({
                            "day": i + 1,
                            "code": day.code,
                            "hours": float(day.hours.split(':')[0]) + float(day.hours.split(':')[1])/60 if day.hours and ':' in day.hours else (float(day.hours) if day.hours else 0),
                            "notes": "" 
                        })
                        
                    employees_data.append(emp_dict)

            # Save compact JSON archive (is_approved=True since this is called after approval)
            save_tabel_archive(
                month=month,
                year=year,
                is_correction=is_correction,
                correction_month=correction_month,
                correction_year=correction_year,
                correction_sequence=correction_sequence,
                employees_data=employees_data,
                is_approved=True,
            )

            # Record tabel generation and check approval status
            with get_db_context() as db:
                approval_service = TabelApprovalService(db)
                approval_service.record_generation(
                    month=month,
                    year=year,
                    is_correction=is_correction,
                    correction_month=correction_month,
                    correction_year=correction_year,
                    correction_sequence=correction_sequence
                )
                # Check if should show approval button
                status = approval_service.get_approval_status(
                    self._current_month,
                    self._current_year,
                    is_correction=self._is_correction
                )
                if status and not status.get("is_approved"):
                    self._approval_button.setVisible(True)

            self._load_archive_list()
            self._check_show_warning()
        except Exception as e:
            logger.error(f"Error archiving tabel: {e}")

    def refresh(self, correction_info=None) -> None:
        """Refresh tabel data.

        Args:
            correction_info: Dict with date, correction_month, correction_year
                If provided and its month is locked, switch to correction tab
        """
        self._load_archive_list()
        self._update_correction_tabs()

        # Check if we need to switch to correction tab
        if correction_info:
            from backend.services.tabel_approval_service import TabelApprovalService
            from backend.core.database import get_db_context

            # Extract info from correction_info
            if isinstance(correction_info, dict):
                corr_month = correction_info.get("correction_month", correction_info.get("date", {}).month if hasattr(correction_info.get("date"), "month") else 0)
                corr_year = correction_info.get("correction_year", correction_info.get("date", {}).year if hasattr(correction_info.get("date"), "year") else 0)
            else:
                # Fallback for old date-only format
                modified_date = correction_info
                corr_month = modified_date.month
                corr_year = modified_date.year

            with get_db_context() as db:
                approval_service = TabelApprovalService(db)

                # Check if the correction month is locked
                if approval_service.is_month_locked(corr_month, corr_year):
                    # Check if we're not already on this correction tab
                    if not self._is_correction or self._current_correction_month != corr_month or self._current_correction_year != corr_year:
                        # Switch to correction tab for this month
                        self._switch_to_correction_tab(corr_month, corr_year)

        self._load_tabel()
        self._check_show_warning()

    def _check_show_warning(self) -> None:
        """Check and update warning and approval banner visibility."""
        from backend.services.tabel_approval_service import TabelApprovalService
        from backend.core.database import get_db_context

        with get_db_context() as db:
            approval_service = TabelApprovalService(db)

            # Handle warning banner (only for non-correction tabels)
            if self._is_correction:
                self._warning_widget.setVisible(False)
            else:
                should_show = approval_service.should_show_warning(self._current_month, self._current_year)
                self._warning_widget.setVisible(should_show)

            # Handle approval banner
            status = approval_service.get_approval_status(
                self._current_month,
                self._current_year,
                is_correction=self._is_correction,
                correction_month=self._current_correction_month if self._is_correction else None,
                correction_year=self._current_correction_year if self._is_correction else None,
            )
            is_approved = status and status.get("is_approved")

            if is_approved:
                approved_by = status.get("approved_by", "")
                approved_at = status.get("approved_at", "")
                month_name = MONTHS_UKR[self._current_month - 1]

                # Format date for display
                if approved_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
                        approved_at = dt.strftime("%d.%m.%Y %H:%M")
                    except:
                        pass

                self._approval_banner.setText(f"✓ Табель за {month_name} {self._current_year} погоджено з кадрами{f' ({approved_by})' if approved_by else ''} {approved_at}")
                self._approval_banner.setStyleSheet("""
                    QLabel {
                        background-color: #d4edda;
                        border: 1px solid #28a745;
                        border-radius: 4px;
                        padding: 8px 12px;
                        color: #155724;
                        font-weight: bold;
                    }
                """)
                self._approval_banner.setVisible(True)
                self._approval_button.setVisible(False)
            else:
                self._approval_banner.setVisible(False)
                # Show approval button if generated but not approved
                is_generated = status and status.get("is_generated")
                self._approval_button.setVisible(bool(is_generated))

    def _on_hr_approval_clicked(self) -> None:
        """Handle HR approval button click."""
        from PyQt6.QtWidgets import QMessageBox
        from backend.services.tabel_approval_service import TabelApprovalService
        from backend.core.database import get_db_context

        if self._is_correction:
            corr_month_name = MONTHS_UKR[self._current_correction_month - 1] if self._current_correction_month else ""
            message = f"Підтвердьте, що корегуючий табель за {corr_month_name} {self._current_correction_year} погоджено з кадровою службою.\n\nПісля погодження корекцію буде зафіксовано.\n\nПродовжити?"
        else:
            message = "Підтвердьте, що табель погоджено з кадровою службою.\n\nПісля погодження місяць буде заблоковано для редагування.\nВсі зміни будуть вноситися в корегуючий табель.\n\nПродовжити?"

        reply = QMessageBox.question(
            self,
            "Погодження з кадрами",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with get_db_context() as db:
                approval_service = TabelApprovalService(db)
                approval_service.confirm_approval(
                    month=self._current_month,
                    year=self._current_year,
                    is_correction=self._is_correction,
                    correction_month=self._current_correction_month if self._is_correction else None,
                    correction_year=self._current_correction_year if self._is_correction else None,
                    correction_sequence=self._current_correction_sequence if self._is_correction else 1
                )

            # Archive the tabel (only when approved)
            # For corrections, archive using correction month/year
            # For normal tabels, archive using current month/year
            if self._is_correction and self._current_correction_month and self._current_correction_year:
                self._archive_tabel(
                    month=self._current_correction_month,
                    year=self._current_correction_year,
                    is_correction=True,
                    correction_month=self._current_correction_month,
                    correction_year=self._current_correction_year,
                    correction_sequence=self._current_correction_sequence
                )
            else:
                self._archive_tabel(
                    month=self._current_month,
                    year=self._current_year,
                    is_correction=False
                )

            self._approval_button.setVisible(False)
            self._check_show_warning()
            self._load_archive_list()  # Refresh archive list

            QMessageBox.information(
                self,
                "Успіх",
                "Табель погоджено з кадровою службою.\n"
                "Місяць заблоковано для редагування."
            )
