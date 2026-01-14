"""Віджет live preview для документа."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import pyqtSignal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


class LivePreviewWidget(QWidget):
    """
    HTML прев'ю документа з можливістю live оновлення.

    Використовує QWebEngineView для рендерингу HTML.
    """

    content_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        """Ініціалізує віджет прев'ю."""
        super().__init__(parent)
        self.web_view = QWebEngineView()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web_view)

        # Jinja2 для HTML шаблонів
        templates_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )

    def render_preview(self, context: dict[str, Any]):
        """
        Рендерить прев'ю заяви.

        Args:
            context: Дані для шаблону (ПІБ, дати, тощо)
        """
        template = self.jinja_env.get_template("document_preview.html")
        html = template.render(**context)

        self.web_view.setHtml(html)

    def set_html(self, html: str):
        """
        Встановлює HTML безпосередньо.

        Args:
            html: HTML контент
        """
        self.web_view.setHtml(html)

    def clear(self):
        """Очищає прев'ю."""
        self.web_view.setHtml("<html><body></body></html>")
