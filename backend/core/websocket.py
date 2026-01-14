"""WebSocket менеджер для real-time синхронізації."""

import json
import logging
from typing import Set
from fastapi import WebSocket
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WebSocketMessage(BaseModel):
    """Модель WebSocket повідомлення."""
    type: str
    document_id: int | None = None
    status: str | None = None
    data: dict | None = None


class ConnectionManager:
    """
    Менеджер WebSocket з'єднань.

    Керує активними WebSocket з'єднаннями та розсилає повідомлення.
    """

    def __init__(self):
        """Ініціалізує менеджер з'єднань."""
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """
        Приймає нове WebSocket з'єднання.

        Args:
            websocket: WebSocket об'єкт
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Видаляє WebSocket з'єднання.

        Args:
            websocket: WebSocket об'єкт
        """
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """
        Відправляє повідомлення конкретному клієнту.

        Args:
            message: Текст повідомлення
            websocket: WebSocket об'єкт одержувача
        """
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: WebSocketMessage | dict) -> None:
        """
        Розсилає повідомлення всім підключеним клієнтам.

        Args:
            message: Повідомлення для розсилки
        """
        if isinstance(message, WebSocketMessage):
            message_dict = message.model_dump()
        else:
            message_dict = message

        message_json = json.dumps(message_dict, ensure_ascii=False)

        # Видаляємо неактивні з'єднання
        to_remove = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                to_remove.add(connection)

        # Очищаємо неактивні з'єднання
        for connection in to_remove:
            self.disconnect(connection)

        if self.active_connections:
            logger.debug(f"Broadcasted message to {len(self.active_connections)} clients")

    async def notify_document_signed(self, document_id: int, file_path: str) -> None:
        """
        Повідомляє про завантаження підписаного документу.

        Args:
            document_id: ID документа
            file_path: Шлях до файлу скану
        """
        message = WebSocketMessage(
            type="document_signed",
            document_id=document_id,
            data={"file_path": file_path}
        )
        await self.broadcast(message)

    async def notify_document_status_changed(
        self,
        document_id: int,
        status: str,
        old_status: str | None = None
    ) -> None:
        """
        Повідомляє про зміну статусу документа.

        Args:
            document_id: ID документа
            status: Новий статус
            old_status: Попередній статус (опціонально)
        """
        message = WebSocketMessage(
            type="document_status_changed",
            document_id=document_id,
            status=status,
            data={"old_status": old_status}
        )
        await self.broadcast(message)

    async def notify_staff_created(self, staff_id: int, name: str) -> None:
        """
        Повідомляє про створення нового співробітника.

        Args:
            staff_id: ID співробітника
            name: ПІБ співробітника
        """
        message = WebSocketMessage(
            type="staff_created",
            data={"staff_id": staff_id, "name": name}
        )
        await self.broadcast(message)

    async def notify_schedule_updated(self, year: int) -> None:
        """
        Повідомляє про оновлення графіку відпусток.

        Args:
            year: Рік графіку
        """
        message = WebSocketMessage(
            type="schedule_updated",
            data={"year": year}
        )
        await self.broadcast(message)


# Глобальний інстанс менеджера
manager = ConnectionManager()
