"""Головний файл PyQt6 Desktop додатку."""

import sys

from PyQt6.QtWidgets import QApplication

from desktop.ui.main_window import MainWindow


def run_auto_deactivation() -> None:
    """
    Виконує автоматичну деактивацію прострочених контрактів при старті.

    Ця функція викликається перед показом головного вікна.
    """
    from backend.core.database import get_db_context
    from backend.services.staff_service import StaffService

    try:
        with get_db_context() as db:
            service = StaffService(db, changed_by="SYSTEM")
            count = service.auto_deactivate_expired_contracts()
            if count > 0:
                print(f"[SYSTEM] Автоматично деактивовано {count} записів з простроченими контрактами")
    except Exception as e:
        print(f"[ERROR] Помилка авто-деактивації: {e}")


def main() -> int:
    """
    Точка входу в Desktop додаток.

    Returns:
        Код виходу
    """
    app = QApplication(sys.argv)
    app.setApplicationName("VacationManager")
    app.setApplicationVersion("5.5.0")
    app.setOrganizationName("VacationManager")

    # Стиль
    app.setStyle("Fusion")

    # Автоматична деактивація при старті
    run_auto_deactivation()

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
