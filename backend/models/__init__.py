"""Ініціалізація ORM моделей."""

# Базові класи та mixins
from backend.models.base import Base, TimestampMixin

# Моделі
from backend.models.staff import Staff, WorkScheduleType
from backend.models.attendance import (
    Attendance,
    ATTENDANCE_CODES,
    CODE_TO_LETTER,
    WEEKEND_DAYS,
    STANDARD_WORK_HOURS,
)
from backend.models.document import Document, DocumentStatus, DocumentType
from backend.models.schedule import AnnualSchedule
from backend.models.settings import SystemSettings, Approvers
from backend.models.staff_history import StaffHistory

__all__ = [
    "Base",
    "TimestampMixin",
    "Staff",
    "WorkScheduleType",
    "Attendance",
    "ATTENDANCE_CODES",
    "CODE_TO_LETTER",
    "WEEKEND_DAYS",
    "STANDARD_WORK_HOURS",
    "Document",
    "DocumentStatus",
    "DocumentType",
    "AnnualSchedule",
    "SystemSettings",
    "Approvers",
    "StaffHistory",
]
