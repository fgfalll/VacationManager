"""Ініціалізація ORM моделей."""

# Базові класи та mixins
from backend.models.base import Base, TimestampMixin

# Моделі
from backend.models.staff import Staff
from backend.models.document import Document
from backend.models.schedule import AnnualSchedule
from backend.models.settings import SystemSettings, Approvers

__all__ = [
    "Base",
    "TimestampMixin",
    "Staff",
    "Document",
    "AnnualSchedule",
    "SystemSettings",
    "Approvers",
]
