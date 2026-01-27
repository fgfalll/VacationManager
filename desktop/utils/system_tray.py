"""System tray functionality for VacationManager.

Keeps backend, Telegram polling, and web UI running when desktop app is closed.
"""

import os
import sys
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QSystemTrayIcon,
    QMenu,
    QApplication,
)
from PyQt6.QtCore import QIODevice, QSocketNotifier, QTimer
from PyQt6.QtGui import QAction, QIcon, QPainter, QColor, QFont


class SystemTrayManager:
    """
    Manages system tray icon and background services.

    Features:
    - Shows tray icon with menu (Show/Hide/Quit)
    - Keeps backend, Telegram bot, and web UI running
    - Single instance detection via local socket
    - Can open desktop app from tray
    """

    # Socket for single-instance detection
    _socket: Optional[socket.socket] = None

    def __init__(
        self,
        app: QApplication,
        main_window=None,
        backend_port: int = 8000,
        web_port: int = 5173,
        enable_telegram: bool = False,
    ):
        """
        Initialize system tray manager.

        Args:
            app: QApplication instance
            main_window: MainWindow instance (can be None for tray-only mode)
            backend_port: Port for backend server
            web_port: Port for web UI
            enable_telegram: Whether to start Telegram bot
        """
        self.app = app
        self.main_window = main_window
        self.backend_port = backend_port
        self.web_port = web_port
        self.enable_telegram = enable_telegram

        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.backend_process: Optional[subprocess.Popen] = None
        self.web_process: Optional[subprocess.Popen] = None
        self.telegram_process: Optional[subprocess.Popen] = None

        self._is_tray_only = main_window is None

    def _create_icon(self) -> QIcon:
        """Create a simple icon (TODO: add custom icon file later)."""
        # Return a generic icon - replace with custom icon file later
        # For now, use the application's style icon
        return self.app.style().standardIcon(
            self.app.style().StandardPixmap.SP_ComputerIcon
        )

    def _create_menu(self) -> QMenu:
        """Create context menu for tray icon."""
        menu = QMenu()

        if self.main_window:
            # Show/Hide window action
            self.show_action = QAction("Відкрити VacationManager", self.app)
            self.show_action.triggered.connect(self._toggle_window)
            menu.addAction(self.show_action)
        else:
            # Open desktop app action
            open_action = QAction("Відкрити додаток", self.app)
            open_action.triggered.connect(self._open_desktop_app)
            menu.addAction(open_action)

        menu.addSeparator()

        # Status info
        self.status_action = QAction("Статус: Запуск...", self.app)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)

        # Open Web Portal
        web_action = QAction("Відкрити Web Portal", self.app)
        web_action.triggered.connect(self._open_web_portal)
        menu.addAction(web_action)

        menu.addSeparator()

        # Quit action
        quit_action = QAction("Вихід", self.app)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        return menu

    def _toggle_window(self):
        """Toggle main window visibility."""
        if not self.main_window:
            self._open_desktop_app()
            return

        if self.main_window.isVisible():
            self.main_window.hide()
            if hasattr(self, 'show_action'):
                self.show_action.setText("Відкрити VacationManager")
        else:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
            if hasattr(self, 'show_action'):
                self.show_action.setText("Приховати вікно")

    def _open_desktop_app(self):
        """Open the desktop app (tray-only mode)."""
        # Import here to avoid circular dependency
        from desktop.ui.main_window import MainWindow
        from desktop.widgets.splash_screen import SplashScreen

        if self.main_window is None:
            # Show splash
            splash = SplashScreen()
            splash.show()
            self.app.processEvents()

            # Create main window
            self.main_window = MainWindow(show_splash=False)

            # Load data
            splash.show_message("Завантаження даних...", 50)
            self.app.processEvents()
            self.main_window.staff_tab.refresh()
            self.app.processEvents()

            splash.show_message("Завантаження графіку...", 70)
            self.app.processEvents()
            self.main_window.schedule_tab.refresh()
            self.app.processEvents()

            splash.show_message("Завантаження конструктора...", 85)
            self.app.processEvents()
            self.main_window.builder_tab.refresh()
            self.app.processEvents()

            splash.show_message("Завантаження табелю...", 95)
            self.app.processEvents()
            self.main_window.tabel_tab.refresh()
            self.app.processEvents()

            # Show window
            self.main_window.show()
            splash.finish(self.main_window)

            # Reconnect close event to minimize to tray
            self.main_window.closeEvent = self._on_close_event

            # Update menu
            if self.tray_icon:
                menu = self._create_menu()
                self.tray_icon.setContextMenu(menu)

    def _open_web_portal(self):
        """Open web portal in browser."""
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{self.backend_port}")

    def _on_close_event(self, event):
        """Handle main window close event - minimize to tray instead of closing."""
        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            if self.main_window:
                self.main_window.hide()
            # Show notification
            if self.tray_icon.supportsMessages():
                self.tray_icon.showMessage(
                    "VacationManager",
                    "Додаток продовжує працювати в треї. Натисніть на іконку для відкриття.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
        else:
            event.accept()

    def _quit(self):
        """Quit application, stopping all background services."""
        # Stop all processes
        self.stop_all_services()

        # Quit application
        if self.main_window:
            self.main_window.close()

        self.app.quit()

    def _check_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return True
            except OSError:
                return False

    def _find_available_port(self, start_port: int, max_attempts: int = 100) -> int:
        """Find an available port starting from start_port."""
        for port in range(start_port, start_port + max_attempts):
            if self._check_port_available(port):
                return port
        return start_port

    def _update_status(self):
        """Update status text in menu."""
        if not hasattr(self, 'status_action'):
            return

        status_parts = []
        if self.backend_process:
            status_parts.append("API")
        if self.web_process:
            status_parts.append("Web")
        if self.telegram_process:
            status_parts.append("Telegram")

        if status_parts:
            self.status_action.setText(f"Активно: {', '.join(status_parts)}")
        else:
            self.status_action.setText("Статус: Очікування")

    def start_backend_service(self) -> bool:
        """Start the backend API server."""
        if self.backend_process and self.backend_process.poll() is None:
            return True  # Already running

        try:
            # Find available port if needed
            if not self._check_port_available(self.backend_port):
                self.backend_port = self._find_available_port(self.backend_port)

            cmd = [
                sys.executable, "-m", "uvicorn",
                "backend.main:app",
                "--host", "127.0.0.1",
                "--port", str(self.backend_port),
                "--log-level", "warning",
            ]

            env = os.environ.copy()
            self.backend_process = subprocess.Popen(
                cmd,
                cwd=Path(__file__).parent.parent.parent,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Wait a moment to check if it started successfully
            time.sleep(1)
            if self.backend_process.poll() is None:
                self._update_status()
                return True
            else:
                self.backend_process = None
                return False

        except Exception as e:
            print(f"[TRAY] Failed to start backend: {e}")
            return False

    def start_web_service(self) -> bool:
        """Start the web UI dev server."""
        if self.web_process and self.web_process.poll() is None:
            return True  # Already running

        try:
            # Find available port if needed
            if not self._check_port_available(self.web_port):
                self.web_port = self._find_available_port(self.web_port)

            # Find npm
            npm = self._find_npm()
            if not npm:
                print("[TRAY] npm not found, skipping web UI")
                return False

            cmd = [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(self.web_port)]

            env = os.environ.copy()
            env["VITE_API_URL"] = f"http://127.0.0.1:{self.backend_port}"

            self.web_process = subprocess.Popen(
                cmd,
                cwd=Path(__file__).parent.parent.parent / "web",
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Wait a moment to check if it started successfully
            time.sleep(2)
            if self.web_process.poll() is None:
                self._update_status()
                return True
            else:
                self.web_process = None
                return False

        except Exception as e:
            print(f"[TRAY] Failed to start web UI: {e}")
            return False

    def start_telegram_service(self) -> bool:
        """Start the Telegram bot (polling mode)."""
        if self.telegram_process and self.telegram_process.poll() is None:
            return True  # Already running

        if not self.enable_telegram:
            return False

        try:
            # Check if Telegram is enabled in database
            from pathlib import Path
            import sqlite3

            db_path = Path(__file__).parent.parent.parent / "vacation_manager.db"
            if not db_path.exists():
                return False

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'telegram_enabled'")
            result = cursor.fetchone()
            enabled = result and result[0] and result[0].lower() in ('true', '1', 'yes')

            cursor.execute("SELECT value FROM settings WHERE key = 'telegram_bot_token'")
            result = cursor.fetchone()
            bot_token = result[0] if result else ""

            conn.close()

            if not enabled or not bot_token:
                print("[TRAY] Telegram not enabled or no token, skipping")
                return False

            cmd = [
                sys.executable, "-m", "backend.telegram.run_bot",
                "--log-level", "warning",
            ]

            env = os.environ.copy()
            env["VM_TELEGRAM_ENABLED"] = "true"
            env["VM_TELEGRAM_BOT_TOKEN"] = bot_token

            self.telegram_process = subprocess.Popen(
                cmd,
                cwd=Path(__file__).parent.parent.parent,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Wait a moment to check if it started successfully
            time.sleep(1)
            if self.telegram_process.poll() is None:
                self._update_status()
                return True
            else:
                self.telegram_process = None
                return False

        except Exception as e:
            print(f"[TRAY] Failed to start Telegram bot: {e}")
            return False

    def _find_npm(self) -> Optional[str]:
        """Find npm executable."""
        import shutil

        npm = shutil.which("npm")
        if npm:
            return npm

        # Windows-specific paths
        npm_paths = [
            os.path.expandvars(r"%ProgramFiles%\nodejs\npm.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\nodejs\npm.exe"),
            os.path.expandvars(r"%LocalAppData%\Programs\nodejs\npm.exe"),
        ]

        for path in npm_paths:
            if os.path.exists(path):
                return path

        return None

    def start_all_services(self) -> bool:
        """Start all background services."""
        success = True

        if not self.start_backend_service():
            print("[TRAY] Failed to start backend service")
            success = False

        if not self.start_web_service():
            print("[TRAY] Failed to start web service")
            # Web UI is optional, don't fail completely

        if self.enable_telegram:
            if not self.start_telegram_service():
                print("[TRAY] Failed to start Telegram service")
                # Telegram is optional, don't fail completely

        return success

    def stop_all_services(self):
        """Stop all background services."""
        for name, proc in [
            ("Backend", self.backend_process),
            ("Web UI", self.web_process),
            ("Telegram", self.telegram_process),
        ]:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                    print(f"[TRAY] {name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    proc.kill()
                    print(f"[TRAY] {name} force killed")

        self.backend_process = None
        self.web_process = None
        self.telegram_process = None
        self._update_status()

    def show(self) -> bool:
        """
        Show system tray icon.

        Returns:
            True if successful, False if system tray is not supported
        """
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[TRAY] System tray is not available on this platform")
            return False

        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(self._create_icon())
        self.tray_icon.setContextMenu(self._create_menu())

        # Set tooltip
        self.tray_icon.setToolTip("VacationManager - Керування відпустками")

        # Handle tray icon activation (double-click to show/hide)
        self.tray_icon.activated.connect(self._on_tray_activated)

        # Show the tray icon
        self.tray_icon.show()

        # Connect close event to minimize to tray
        if self.main_window:
            self.main_window.closeEvent = self._on_close_event

        return True

    def hide(self):
        """Hide system tray icon."""
        if self.tray_icon:
            self.tray_icon.hide()

    def _on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_window()

    @classmethod
    def check_single_instance(cls) -> bool:
        """
        Check if another instance is already running.

        Uses a local socket for single-instance detection.

        Returns:
            True if this is the first instance, False if already running
        """
        # Try to connect to existing instance
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            test_socket.connect(('127.0.0.1', 38117))
            # If connected, another instance is running
            test_socket.close()
            return False
        except (ConnectionRefusedError, OSError):
            # No existing instance, this is the first one
            pass

        # Create server socket for single-instance detection
        try:
            cls._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cls._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            cls._socket.bind(('127.0.0.1', 38117))
            cls._socket.listen(1)
            return True
        except Exception as e:
            print(f"[TRAY] Single instance check failed: {e}")
            return False

    @classmethod
    def cleanup_socket(cls):
        """Cleanup the single-instance socket."""
        if cls._socket:
            try:
                cls._socket.close()
            except Exception:
                pass
            cls._socket = None
