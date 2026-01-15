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
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from backend.services.tabel_service import (
    generate_tabel_html,
    save_tabel_to_file,
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
        self.archive_list = QListWidget()
        self.archive_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.archive_list.itemClicked.connect(self._on_archive_item_clicked)
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

        # Web view for preview
        self.web_view = QWebEngineView()
        self.web_view.setSizePolicy(
            self.web_view.sizePolicy().Policy.Expanding,
            self.web_view.sizePolicy().Policy.Expanding
        )
        content.addWidget(self.web_view, 1)

        # Excel-style tabs at bottom
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
        self.normal_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8;
                border: 1px solid #999;
                border-bottom: none;
                border-radius: 3px 3px 0 0;
                padding: 4px 15px;
                font-size: 11px;
                min-width: 80px;
            }
            QPushButton:checked {
                background-color: #fff;
                font-weight: bold;
            }
            QPushButton:hover:checked {
                background-color: #f5f5f5;
            }
        """)
        self.tab_button_group.addButton(self.normal_tab_btn)
        tabs_layout.addWidget(self.normal_tab_btn)

        # Correction tabs container (scrollable for many corrections)
        from PyQt6.QtWidgets import QScrollArea
        self.correction_tabs_scroll = QScrollArea()
        self.correction_tabs_scroll.setWidgetResizable(True)
        self.correction_tabs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.correction_tabs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.correction_tabs_scroll.setFixedHeight(32)
        self.correction_tabs_scroll.setMaximumWidth(600)

        self.correction_tabs_widget = QWidget()
        self.correction_tabs_layout = QHBoxLayout(self.correction_tabs_widget)
        self.correction_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.correction_tabs_layout.setSpacing(2)
        self.correction_tabs_layout.addStretch()

        self.correction_tabs_scroll.setWidget(self.correction_tabs_widget)
        tabs_layout.addWidget(self.correction_tabs_scroll)

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
        self._load_tabel()
        self._check_show_warning()

    def _update_correction_tabs(self) -> None:
        """Update the list of correction tabs based on existing correction records."""
        from backend.services.tabel_approval_service import TabelApprovalService
        from backend.core.database import get_db_context

        # Clear existing correction tabs
        for i in reversed(range(self.correction_tabs_layout.count())):
            item = self.correction_tabs_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        # Get correction months
        with get_db_context() as db:
            approval_service = TabelApprovalService(db)
            self._correction_months = approval_service.get_correction_months()

        # Create tab buttons for each correction month
        for correction in self._correction_months:
            month = correction["month"]
            year = correction["year"]
            month_name = MONTHS_UKR[month - 1]
            tab_text = f"Корег. ({month_name})"

            tab_btn = QPushButton(tab_text)
            tab_btn.setCheckable(True)
            tab_btn.setFixedHeight(28)
            tab_btn.setProperty("correction_month", month)
            tab_btn.setProperty("correction_year", year)
            tab_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e8e8e8;
                    border: 1px solid #999;
                    border-bottom: none;
                    border-radius: 3px 3px 0 0;
                    padding: 4px 15px;
                    font-size: 11px;
                    min-width: 120px;
                }
                QPushButton:checked {
                    background-color: #fff;
                    font-weight: bold;
                }
                QPushButton:hover:checked {
                    background-color: #f5f5f5;
                }
            """)
            tab_btn.clicked.connect(lambda checked, m=month, y=year: self._on_correction_tab_clicked(m, y))

            # Insert before the stretch
            self.correction_tabs_layout.insertWidget(self.correction_tabs_layout.count() - 1, tab_btn)
            self.tab_button_group.addButton(tab_btn)

    def _on_correction_tab_clicked(self, month: int, year: int) -> None:
        """Called when a correction tab is clicked."""
        self._current_correction_month = month
        self._current_correction_year = year
        self._load_tabel()
        self._check_show_warning()

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
        """Load list of archived tabels."""
        base_path = Path(__file__).parent.parent.parent
        archive_dir = base_path / "storage" / "tabels"

        self.archive_list.clear()

        if not archive_dir.exists():
            self.archive_stack.setCurrentIndex(1)  # Show placeholder
            return

        # Find all archived tabels
        archives: list[tuple[int, int, Path]] = []
        for item in archive_dir.iterdir():
            if item.is_dir():
                # Format: YYYY-MM
                try:
                    year = int(item.name[:4])
                    month = int(item.name[5:7])
                    if 1 <= month <= 12:
                        archives.append((year, month, item))
                except (ValueError, IndexError):
                    continue

        # Sort by date (newest first)
        archives.sort(reverse=True)

        for year, month, item in archives:
            list_item = QListWidgetItem(f"{MONTHS_UKR[month - 1]} {year}")
            list_item.setData(Qt.ItemDataRole.UserRole, (year, month, str(item)))
            self.archive_list.addItem(list_item)

        if archives:
            self.archive_stack.setCurrentIndex(0)
        else:
            self.archive_stack.setCurrentIndex(1)

    def _on_archive_item_clicked(self, item: QListWidgetItem) -> None:
        """Called when archive item is clicked."""
        self.restore_btn.setEnabled(True)

    def _restore_from_archive(self) -> None:
        """Restore selected tabel from archive."""
        current = self.archive_list.currentItem()
        if not current:
            return

        year, month, _ = current.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self,
            "Відновлення табеля",
            f"Відновити табель за {current.text()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._current_year = year
            self._current_month = month
            self._update_month_display()
            self._load_tabel()

    def _get_days_in_month(self) -> int:
        """Get number of days in current month."""
        return calendar.monthrange(self._current_year, self._current_month)[1]

    def _load_tabel(self) -> None:
        """Load and render tabel for current month."""
        self.status_label.setText("Формування табеля...")

        # Define template_dir here so it's available in except block
        template_dir = Path(__file__).parent.parent / "templates" / "tabel"

        try:
            # Get institution settings
            from backend.models.settings import SystemSettings
            from backend.core.database import get_db_context

            institution_name = ""
            edrpou_code = ""

            with get_db_context() as db:
                institution_name = SystemSettings.get_value(db, "university_name", "")
                edrpou_code = SystemSettings.get_value(db, "edrpou_code", "")

            # Generate HTML using Jinja2 template
            html = generate_tabel_html(
                month=self._current_month,
                year=self._current_year,
                institution_name=institution_name,
                edrpou_code=edrpou_code,
                employees_per_page=self.EMPLOYEES_PER_PAGE if self.EMPLOYEES_PER_PAGE > 0 else 0,
                is_correction=self._is_correction,
                correction_month=self._current_correction_month,
                correction_year=self._current_correction_year,
            )

            # Load into web view - use absolute path to template directory
            self.web_view.setHtml(html, QUrl.fromLocalFile(str(template_dir) + "/"))

            # Connect signal to apply print scaling and minimize empty columns after load
            self.web_view.loadFinished.connect(self._apply_print_scaling)

            # Update status
            month_name = MONTHS_UKR[self._current_month - 1]
            self.status_label.setText(f"Табель: {month_name} {self._current_year}")

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

        try:
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
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QEventLoop

            max_wait = 50  # 5 seconds max
            wait_count = 0
            while not tabel_pdf_path.exists() and wait_count < max_wait:
                QApplication.processEvents()
                loop = QEventLoop()
                QTimer.singleShot(100, loop.quit)
                loop.exec()
                wait_count += 1

            if not tabel_pdf_path.exists():
                raise Exception(f"Tabel PDF not generated after {max_wait * 0.1}s")

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

            # Step 3: Merge PDFs (title page + tabel)
            pdfs_to_merge = []
            if title_pdf_path and title_pdf_path.exists():
                pdfs_to_merge.append(title_pdf_path)

            if tabel_pdf_path.exists():
                pdfs_to_merge.append(tabel_pdf_path)

            merge_pdfs(pdfs_to_merge, final_filepath)

            # SUCCESS: Clean up temp folder
            import shutil
            shutil.rmtree(temp_dir)

        except Exception as e:
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

        # Archive after file is written
        QTimer.singleShot(500, self._archive_tabel)

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Успіх",
            f"Табель збережено:\n{final_filepath}"
        )

    def _archive_tabel(self) -> None:
        """Archive the current tabel."""
        try:
            # Get institution settings
            from backend.models.settings import SystemSettings
            from backend.core.database import get_db_context
            from backend.services.tabel_service import save_tabel_to_file, generate_tabel_html

            institution_name = ""
            edrpou_code = ""

            with get_db_context() as db:
                institution_name = SystemSettings.get_value(db, "university_name", "")
                edrpou_code = SystemSettings.get_value(db, "edrpou_code", "")

            html = generate_tabel_html(
                month=self._current_month,
                year=self._current_year,
                institution_name=institution_name,
                edrpou_code=edrpou_code,
                is_correction=self._is_correction,
            )
            save_tabel_to_file(
                html=html,
                month=self._current_month,
                year=self._current_year,
            )

            # Record tabel generation and check approval status
            from backend.services.tabel_approval_service import TabelApprovalService
            with get_db_context() as db:
                approval_service = TabelApprovalService(db)
                approval_service.record_generation(
                    month=self._current_month,
                    year=self._current_year,
                    is_correction=self._is_correction
                )
                # Check if should show approval button
                if not self._is_correction:
                    status = approval_service.get_approval_status(self._current_month, self._current_year)
                    if status and not status.get("is_approved"):
                        self._approval_button.setVisible(True)

            self._load_archive_list()
            self._check_show_warning()
        except Exception:
            pass

    def refresh(self) -> None:
        """Refresh tabel data."""
        self._load_archive_list()
        self._update_correction_tabs()
        self._load_tabel()
        self._check_show_warning()

    def _check_show_warning(self) -> None:
        """Check and update warning banner visibility."""
        if self._is_correction:
            self._warning_widget.setVisible(False)
            return

        from backend.services.tabel_approval_service import TabelApprovalService
        from backend.core.database import get_db_context

        with get_db_context() as db:
            approval_service = TabelApprovalService(db)
            should_show = approval_service.should_show_warning(self._current_month, self._current_year)
            self._warning_widget.setVisible(should_show)

    def _on_hr_approval_clicked(self) -> None:
        """Handle HR approval button click."""
        from PyQt6.QtWidgets import QMessageBox
        from backend.services.tabel_approval_service import TabelApprovalService
        from backend.core.database import get_db_context

        reply = QMessageBox.question(
            self,
            "Погодження з кадрами",
            "Підтвердьте, що табель погоджено з кадровою службою.\n\n"
            "Після погодження місяць буде заблоковано для редагування.\n"
            "Всі зміни будуть вноситися в корегуючий табель.\n\n"
            "Продовжити?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with get_db_context() as db:
                approval_service = TabelApprovalService(db)
                approval_service.confirm_approval(
                    month=self._current_month,
                    year=self._current_year,
                    is_correction=False
                )

            self._approval_button.setVisible(False)
            self._check_show_warning()

            QMessageBox.information(
                self,
                "Успіх",
                "Табель погоджено з кадровою службою.\n"
                "Місяць заблоковано для редагування."
            )
