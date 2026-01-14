"""Віджет для відображення статусу документа."""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from shared.enums import DocumentStatus
from shared.constants import STATUS_COLORS, STATUS_ICONS


class StatusBadge(QLabel):
    """
    Кольоровий індикатор статусу документа.

    Відображає статус з відповідним кольором та іконкою.
    """

    def __init__(self, status: DocumentStatus, parent=None):
        """
        Ініціалізує бейдж.

        Args:
            status: Статус документа
            parent: Батьківський віджет
        """
        super().__init__(parent)
        self.set_status(status)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_status(self, status: DocumentStatus):
        """
        Оновлює відображення статусу.

        Args:
            status: Новий статус
        """
        color = STATUS_COLORS.get(status.value, "#888888")
        icon = STATUS_ICONS.get(status.value, "📄")
        text = status.value.replace("_", " ").title()

        self.setText(f"{icon} {text}")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
