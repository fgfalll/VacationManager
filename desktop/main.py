"""Головний файл PyQt6 Desktop додатку."""

import sys

from PyQt6.QtWidgets import QApplication

from desktop.ui.main_window import MainWindow


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

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
