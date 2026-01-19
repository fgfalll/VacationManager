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
        from desktop.ui.styles import WINDOW_BG, TEXT_COLOR, SECONDARY_TEXT, get_splash_stylesheet
        
        self.setFixedSize(400, 250)

        # Створюємо піксельну карту з світлим фоном
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor(WINDOW_BG))

        # Додаємо заголовок на фон
        painter = QPainter(pixmap)
        painter.setPen(QColor(TEXT_COLOR))

        # Заголовок додатку - moved up slightly to separate from version
        title_font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(
            pixmap.rect().adjusted(0, 50, 0, 0),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            "VacationManager"
        )

        # Версія - moved down to avoid overlap
        version_font = QFont("Segoe UI", 12)
        painter.setFont(version_font)
        painter.setPen(QColor(SECONDARY_TEXT))
        painter.drawText(
            pixmap.rect().adjusted(0, 95, 0, 0),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            "v6.0"
        )
        painter.end()

        self.setPixmap(pixmap)

        # Основний лейаут
        layout = QVBoxLayout()
        # Increased top margin to clear the painted text (was 100, now 140)
        layout.setContentsMargins(20, 140, 20, 30)
        layout.setSpacing(10)

        # Лейбл статусу
        self.status_label = QLabel("Ініціалізація...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Stylesheet is applied to container/frame usually, or directly to widgets here via get_splash_stylesheet
        # We will apply specific styles here to ensure they stick, or rely on global sheet if set.
        # Let's set inline for specific control derived from styles.py
        
        # Прогрес бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

        # Додаємо лейаут до головного віджету
        container = QFrame()
        container.setLayout(layout)
        container.setStyleSheet(get_splash_stylesheet())

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
