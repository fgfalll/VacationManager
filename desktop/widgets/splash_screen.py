"""Splash screen з індикатором завантаження."""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QLinearGradient
from PyQt6.QtWidgets import (
    QSplashScreen,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
)


class SplashScreen(QSplashScreen):
    """
    Екран завантаження при старті додатку.

    Показує прогрес ініціалізації додатку.
    """

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self.setEnabled(False)  # Заблокувати взаємодію

    def _setup_ui(self):
        """Налаштовує інтерфейс сплеш-скріна."""
        self.setFixedSize(400, 250)

        # Створюємо піксельну карту з градієнтом фоном
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("#2c3e50"))

        # Додаємо заголовок на фон
        painter = QPainter(pixmap)
        painter.setPen(QColor("#ecf0f1"))

        # Заголовок додатку
        title_font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(
            pixmap.rect().adjusted(0, 60, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "VacationManager"
        )

        # Версія
        version_font = QFont("Segoe UI", 12)
        painter.setFont(version_font)
        painter.drawText(
            pixmap.rect().adjusted(0, 90, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "v6.0"
        )
        painter.end()

        self.setPixmap(pixmap)

        # Основний лейаут
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 100, 20, 40)
        layout.setSpacing(10)

        # Лейбл статусу
        self.status_label = QLabel("Ініціалізація...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 14px;
                font-family: Segoe UI;
            }
        """)
        layout.addWidget(self.status_label)

        # Прогрес бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.2);
                text-align: center;
                color: #ecf0f1;
                height: 20px;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background-color: #3498db;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Додаємо лейаут до головного віджету
        container = QFrame()
        container.setLayout(layout)
        container.setStyleSheet("background: transparent;")

        # Встановлюємо лейаут
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container)
        main_layout.setContentsMargins(0, 0, 0, 0)

    def show_message(self, message: str, progress: int = None):
        """
        Показує повідомлення та оновлює прогрес.

        Args:
            message: Текст повідомлення
            progress: Значення прогресу (0-100), якщо None - не змінюється
        """
        self.status_label.setText(message)
        if progress is not None:
            self.progress_bar.setValue(progress)
        self.repaint()  # Примусове перемалювання

    def set_progress(self, progress: int):
        """
        Встановлює значення прогресу.

        Args:
            progress: Значення від 0 до 100
        """
        self.progress_bar.setValue(progress)
        self.repaint()

    def increment_progress(self, delta: int = 5):
        """
        Збільшує прогрес на вказане значення.

        Args:
            delta: Значення для додавання (за замовчуванням 5)
        """
        new_value = min(100, self.progress_bar.value() + delta)
        self.set_progress(new_value)
