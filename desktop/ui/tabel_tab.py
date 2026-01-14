"""Tabulir Tab - Monthly timesheet table preview and management."""

import calendar
import os
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal, QMarginsF, QUrl
from PyQt6.QtGui import QAction, QPageLayout, QPageSize, QPagedPaintDevice
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
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
    font-family: "Times New Roman", serif;
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
    font-family: 'Calibri', Arial, sans-serif;
    font-size: 9pt;
    vertical-align: middle;
}
.s15, .s16, .s17, .s18, .s19, .s20, .s22, .s23, .s24 {
    background-color: #fff;
    text-align: left;
    color: #000;
    font-size: 8pt;
    vertical-align: middle;
    white-space: nowrap;
}
.s16, .s18 { border-bottom: 1px solid #000; }
.s18 { text-align: center; }
.s19 { text-align: center; }
.s20 { text-align: left; }
.s23 { text-align: center; font-size: 8pt; }
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
        debug_html_path = Path(output_path).parent / f"{Path(output_path).stem}_debug.html"
        if os.path.exists(html_path):
            shutil.copy(html_path, debug_html_path)
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
        self._setup_ui()
        self._connect_signals()
        self._load_archive_list()
        self._load_tabel()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

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

        toolbar.addSeparator()

        # Zoom control
        toolbar.addWidget(QLabel("Масштаб:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 100)
        self.zoom_slider.setValue(int(self.PRINT_ZOOM * 100))
        self.zoom_slider.setFixedWidth(80)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        toolbar.addWidget(self.zoom_slider)

        self.zoom_label = QLabel(f"{int(self.PRINT_ZOOM * 100)}%")
        self.zoom_label.setFixedWidth(35)
        toolbar.addWidget(self.zoom_label)

        # Width control
        toolbar.addWidget(QLabel("Ширина:"))
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(80, 150)
        self.width_slider.setValue(self.PRINT_WIDTH_PERCENT)
        self.width_slider.setFixedWidth(80)
        self.width_slider.valueChanged.connect(self._on_width_changed)
        toolbar.addWidget(self.width_slider)

        self.width_label = QLabel(f"{self.PRINT_WIDTH_PERCENT}%")
        self.width_label.setFixedWidth(40)
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

    def _on_month_changed(self) -> None:
        """Called when month is selected from combo."""
        self._current_month = self.month_combo.currentIndex() + 1
        self._load_tabel()

    def _on_year_changed(self) -> None:
        """Called when year is changed."""
        self._current_year = self.year_spin.value()
        self._load_tabel()

    def _on_zoom_changed(self, value: int) -> None:
        """Called when zoom slider is moved."""
        self.zoom_label.setText(f"{value}%")
        self.PRINT_ZOOM = value / 100

    def _on_width_changed(self, value: int) -> None:
        """Called when width slider is moved."""
        self.width_label.setText(f"{value}%")
        self.PRINT_WIDTH_PERCENT = value

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

    def _print_pdf(self) -> None:
        """Export tabel to PDF using QWebEnginePage's native print (captures exact layout)."""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtCore import QTimer

        month_name = MONTHS_UKR[self._current_month - 1]
        filename = f"Табель_{self._current_year}_{self._current_month:02d}_{month_name}.pdf"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Зберегти табель PDF",
            filename,
            "PDF Files (*.pdf)"
        )

        if not filepath:
            return

        # Save current zoom
        original_zoom = self.web_view.zoomFactor()
        self._print_filepath = filepath
        self._original_zoom = original_zoom

        # Apply zoom and run JS to minimize empty columns
        self.web_view.setZoomFactor(0.65)
        self._minimize_empty_columns_for_print()

    # Configurable print scaling (per session)
    PRINT_ZOOM = 0.70
    PRINT_WIDTH_PERCENT = 97
    EMPLOYEES_PER_PAGE = 10  # employees per page

    def _minimize_empty_columns_for_print(self) -> None:
        """Run JS to minimize empty columns, then print."""
        zoom = self.PRINT_ZOOM
        width_percent = self.PRINT_WIDTH_PERCENT
        js_code = f"""
        (function() {{
            // Process each container (each page)
            const containers = document.querySelectorAll('.ritz.grid-container');
            containers.forEach((container) => {{
                const headerCells = container.querySelectorAll('td.s5-vertical');
                headerCells.forEach((headerCell) => {{
                    const cellIndex = headerCell.cellIndex;
                    const table = container.closest('table') || container.querySelector('table');
                    if (!table) return;
                    const rows = table.querySelectorAll('tr');
                    let hasData = false;

                    for (let i = 4; i < rows.length - 1; i++) {{
                        const cells = rows[i].querySelectorAll('td, th');
                        if (cells[cellIndex]) {{
                            const text = cells[cellIndex].textContent.trim();
                            if (cellIndex >= 18 && cellIndex <= 29) {{
                                if (text !== '' && text !== '0' && text !== '0,00') {{
                                    hasData = true;
                                    break;
                                }}
                            }}
                        }}
                    }}

                    if (!hasData) {{
                        const col = table.querySelectorAll('colgroup col')[cellIndex];
                        if (col) col.style.width = '8px';
                        headerCell.style.minWidth = '8px';
                        headerCell.style.width = '8px';
                    }}
                }});
            }});

            // Apply print scaling to all containers
            containers.forEach((container) => {{
                container.style.zoom = '{zoom}';
                container.style.width = '{width_percent}%';
            }});
        }})();
        """
        self.web_view.page().runJavaScript(js_code, lambda _: self._do_print_pdf())

    def _do_print_pdf(self) -> None:
        """Actually print to PDF after JS has executed."""
        from PyQt6.QtCore import QTimer

        filepath = self._print_filepath
        original_zoom = self._original_zoom

        # Configure page layout - use 0 margins, rely on CSS template margins
        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Landscape,
            QMarginsF(0, 0, 0, 0),
            QPageLayout.Unit.Millimeter
        )

        # Use QWebEnginePage's printToPdf which captures exact rendered layout
        self.web_view.page().printToPdf(
            filepath,
            page_layout
        )

        # Restore zoom and archive after file is written
        def finish_print():
            self.web_view.setZoomFactor(original_zoom)
            self._archive_tabel()

        QTimer.singleShot(500, finish_print)

        QMessageBox.information(
            self,
            "Успіх",
            f"Табель збережено:\n{filepath}"
        )

    def _archive_tabel(self) -> None:
        """Archive the current tabel."""
        try:
            # Get institution settings
            from backend.models.settings import SystemSettings
            from backend.core.database import get_db_context

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
            )
            save_tabel_to_file(
                html=html,
                month=self._current_month,
                year=self._current_year,
            )
            self._load_archive_list()
        except Exception:
            pass

    def refresh(self) -> None:
        """Refresh tabel data."""
        self._load_archive_list()
        self._load_tabel()
