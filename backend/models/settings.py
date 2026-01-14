"""Модель налаштувань системи."""

import json
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Approvers(Base):
    """
    Погоджувачі документів (директор ННІ, тощо).

    Attributes:
        id: Унікальний ідентифікатор
        position_name: Назва посади
        full_name_dav: ПІБ у давальному відмінку
        order_index: Порядок в документі
    """

    __tablename__ = "approvers"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_name: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name_dav: Mapped[str] = mapped_column(String(200), nullable=False)
    order_index: Mapped[int] = mapped_column(default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<Approvers {self.id}: {self.position_name} - {self.full_name_dav}>"


class SystemSettings(Base):
    """
    Налаштування системи (key-value store).

    Attributes:
        id: Унікальний ідентифікатор
        key: Ключ налаштування
        value: Значення (JSON для складних об'єктів)
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    @classmethod
    def get_value(cls, session: Any, key: str, default: Any = None) -> Any:
        """
        Отримує значення налаштування.

        Args:
            session: Сесія бази даних
            key: Ключ налаштування
            default: Значення за замовчуванням

        Returns:
            Значення налаштування або default
        """
        setting = session.query(cls).filter(cls.key == key).first()
        if setting is None:
            return default

        try:
            return json.loads(setting.value)
        except json.JSONDecodeError:
            return setting.value

    @classmethod
    def set_value(cls, session: Any, key: str, value: Any) -> None:
        """
        Встановлює значення налаштування.

        Args:
            session: Сесія бази даних
            key: Ключ налаштування
            value: Значення (буде збережено як JSON)
        """
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_str = str(value)

        setting = session.query(cls).filter(cls.key == key).first()
        if setting:
            setting.value = value_str
        else:
            setting = cls(key=key, value=value_str)
            session.add(setting)

        session.commit()

    def __repr__(self) -> str:
        return f"<SystemSettings {self.key}={self.value}>"
