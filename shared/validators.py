"""Спільні валідатори для використання в Pydantic моделях та сервісах."""

from datetime import date
from typing import Any


def validate_end_after_start(value: date, values: dict[str, Any]) -> date:
    """
    Перевіряє, що дата завершення пізніше за дату початку.

    Args:
        value: Дата завершення
        values: Словник з іншими значеннями (повинен містити 'date_start')

    Returns:
        Валідну дату завершення

    Raises:
        ValueError: Якщо дата завершення не пізніше дати початку
    """
    if "date_start" in values and value <= values["date_start"]:
        raise ValueError("Дата завершення має бути пізніше за дату початку")
    return value


def validate_rate_range(value: float) -> float:
    """
    Перевіряє, що ставка знаходиться в допустимому діапазоні.

    Args:
        value: Ставка

    Returns:
        Валідну ставку

    Raises:
        ValueError: Якщо ставка не в діапазоні (0, 1]
    """
    if value <= 0 or value > 1:
        raise ValueError("Ставка повинна бути більше 0 і не більше 1")
    return value


def validate_vacation_balance(value: int) -> int:
    """
    Перевіряє, що баланс відпустки не від'ємний.

    Args:
        value: Баланс відпустки

    Returns:
        Валідний баланс

    Raises:
        ValueError: Якщо баланс від'ємний
    """
    if value < 0:
        raise ValueError("Баланс відпустки не може бути від'ємним")
    return value
