"""Головний файл PyQt6 Desktop додатку."""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from desktop.ui.main_window import MainWindow
from desktop.widgets.splash_screen import SplashScreen


def run_auto_deactivation(splash: SplashScreen = None) -> int:
    """
    Виконує автоматичну деактивацію прострочених контрактів при старті.

    Args:
        splash: Екран завантаження для відображення прогресу

    Returns:
        Кількість деактивованих записів
    """
    from backend.core.database import get_db_context
    from backend.services.staff_service import StaffService

    try:
        with get_db_context() as db:
            service = StaffService(db, changed_by="SYSTEM")
            count = service.auto_deactivate_expired_contracts()
            return count
    except Exception as e:
        print(f"[ERROR] Помилка авто-деактивації: {e}")
        return 0


def main() -> int:
    """
    Точка входу в Desktop додаток.

    Returns:
        Код виходу
    """
    app = QApplication(sys.argv)
    app.setApplicationName("VacationManager")
    app.setApplicationVersion("7.0.0")
    app.setOrganizationName("VacationManager")

    # Стиль
    app.setStyle("Fusion")

    # Показуємо сплеш-скрін одразу
    splash = SplashScreen()
    splash.show()
    app.processEvents()  # Примусове оновлення інтерфейсу

    # Завантаження з прогресом
    splash.show_message("Ініціалізація...", 5)
    app.processEvents()

    # Автоматична деактивація при старті
    splash.show_message("Перевірка контрактів...", 10)
    app.processEvents()
    count = run_auto_deactivation()
    if count > 0:
        print(f"[SYSTEM] Автоматично деактивовано {count} записів з простроченими контрактами")

    splash.show_message("Створення вікна...", 30)
    app.processEvents()

    # Створюємо головне вікно (без _refresh_data)
    window = MainWindow(show_splash=False)
    app.processEvents()

    splash.show_message("Завантаження даних персоналу...", 45)
    app.processEvents()
    window.staff_tab.refresh()
    app.processEvents()

    splash.show_message("Завантаження графіку...", 60)
    app.processEvents()
    window.schedule_tab.refresh()
    app.processEvents()

    splash.show_message("Завантаження конструктора...", 75)
    app.processEvents()
    window.builder_tab.refresh()
    app.processEvents()

    splash.show_message("Завантаження табелю...", 90)
    app.processEvents()
    window.tabel_tab.refresh()
    app.processEvents()

    splash.show_message("Готово!", 100)
    app.processEvents()

    # Невелика затримка, щоб користувач побачив 100%
    import time
    time.sleep(0.3)

    # Показуємо головне вікно
    window.show()

    # Закриваємо сплеш-скрін
    splash.finish(window)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
