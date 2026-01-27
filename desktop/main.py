"""Головний файл PyQt6 Desktop додатку."""

import sys
import argparse

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from PyQt6.QtCore import Qt

from desktop.ui.main_window import MainWindow
from desktop.widgets.splash_screen import SplashScreen
from desktop.utils.system_tray import SystemTrayManager


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


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="VacationManager Desktop Application")
    parser.add_argument(
        "--tray-only",
        action="store_true",
        help="Run in tray-only mode (services only, no window)"
    )
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="Disable system tray (quit when window closes)"
    )
    parser.add_argument(
        "--enable-telegram",
        action="store_true",
        help="Enable Telegram bot service"
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        help="Backend port (default: 8000)"
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=5173,
        help="Web UI port (default: 5173)"
    )
    return parser.parse_args()


def main() -> int:
    """
    Точка входу в Desktop додаток.

    Returns:
        Код виходу
    """
    args = parse_args()

    # Single instance check
    if not SystemTrayManager.check_single_instance():
        print("VacationManager is already running!")
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("VacationManager")
    app.setApplicationVersion("7.7.4")
    app.setOrganizationName("VacationManager")

    # Set quit on last window closed to False for tray mode
    app.setQuitOnLastWindowClosed(not args.tray_only)

    # Стиль
    app.setStyle("Fusion")

    # Автоматична деактивація при старті (без splash для tray-only mode)
    if not args.tray_only:
        count = run_auto_deactivation()
        if count > 0:
            print(f"[SYSTEM] Автоматично деактивовано {count} записів з простроченими контрактами")

    # Create system tray manager
    tray_manager = None
    if not args.no_tray and QSystemTrayIcon.isSystemTrayAvailable():
        tray_manager = SystemTrayManager(
            app=app,
            main_window=None,  # Will be set later if not tray-only
            backend_port=args.backend_port,
            web_port=args.web_port,
            enable_telegram=args.enable_telegram,
        )

        if not tray_manager.show():
            print("[SYSTEM] System tray initialization failed")
            tray_manager = None
        else:
            # Start background services
            if not tray_manager.start_all_services():
                print("[SYSTEM] Some services failed to start")

    # Tray-only mode
    if args.tray_only:
        print("[SYSTEM] Running in tray-only mode")
        print(f"[SYSTEM] Backend: http://127.0.0.1:{args.backend_port}")
        print(f"[SYSTEM] Web UI: http://127.0.0.1:{args.web_port}")
        print("[SYSTEM] Close tray icon to exit")
        ret = app.exec()
        SystemTrayManager.cleanup_socket()
        return ret

    # Normal mode with window
    # Показуємо сплеш-скрін одразу
    splash = SplashScreen()
    splash.show()
    app.processEvents()  # Примусове оновлення інтерфейсу

    # Завантаження з прогресом
    splash.show_message("Ініціалізація...", 5)
    app.processEvents()

    splash.show_message("Створення вікна...", 30)
    app.processEvents()

    # Створюємо головне вікно (без _refresh_data)
    window = MainWindow(show_splash=False)
    app.processEvents()

    # Update tray manager with main window
    if tray_manager:
        tray_manager.main_window = window
        # Reconnect close event to minimize to tray
        window.closeEvent = lambda event: tray_manager._on_close_event(event)

        # Update tray menu
        menu = tray_manager._create_menu()
        tray_manager.tray_icon.setContextMenu(menu)

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

    ret = app.exec()

    # Cleanup
    SystemTrayManager.cleanup_socket()
    return ret


if __name__ == "__main__":
    sys.exit(main())
