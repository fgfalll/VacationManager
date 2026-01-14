"""Менеджер синхронізації Desktop з Web Portal."""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebSockets import QWebSocket
import json
from typing import Any


class SyncManager(QObject):
    """
    Менеджер синхронізації через WebSocket.

    Підключається до FastAPI WebSocket endpoint для отримання
    real-time оновлень про завантаження сканів документів.
    """

    scan_uploaded = pyqtSignal(int)  # document_id
    document_status_changed = pyqtSignal(int, str)  # document_id, status

    def __init__(self, parent=None):
        """Ініціалізує менеджер синхронізації."""
        super().__init__(parent)
        self.websocket: QWebSocket | None = None
        self.server_url = "ws://127.0.0.1:8000/ws"

    def connect(self):
        """Підключається до WebSocket сервера."""
        if self.websocket is None:
            self.websocket = QWebSocket()
            self.websocket.textMessageReceived.connect(self._on_message_received)
            self.websocket.connected.connect(self._on_connected)
            self.websocket.disconnected.connect(self._on_disconnected)
            self.websocket.errorOccurred.connect(self._on_error)

        self.websocket.open(self.server_url)

    def disconnect(self):
        """Відключається від WebSocket сервера."""
        if self.websocket:
            self.websocket.close()
            self.websocket = None

    def _on_connected(self):
        """Обробляє підключення."""
        print("WebSocket connected")

    def _on_disconnected(self):
        """Обробляє відключення."""
        print("WebSocket disconnected")

    def _on_error(self, error):
        """Обробляє помилку."""
        print(f"WebSocket error: {error}")

    def _on_message_received(self, message: str):
        """
        Обробляє отримане повідомлення.

        Args:
            message: JSON повідомлення
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "document_signed":
                doc_id = data.get("document_id")
                if doc_id:
                    self.scan_uploaded.emit(doc_id)

            elif msg_type == "document_status_changed":
                doc_id = data.get("document_id")
                status = data.get("status")
                if doc_id and status:
                    self.document_status_changed.emit(doc_id, status)

        except json.JSONDecodeError:
            print(f"Invalid JSON received: {message}")

    def send_ping(self):
        """Відправляє ping для keep-alive."""
        if self.websocket and self.websocket.state() == QWebSocket.State.Connected:
            self.websocket.sendTextMessage(json.dumps({"type": "ping"}))
