"""Схеми Pydantic для відвідуваності."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AttendanceResponse(BaseModel):
    """Схема відповіді відвідуваності."""
    id: int
    staff_id: int
    date: datetime | date
    code: str = Field(..., description="Літерний код (Р, В, тощо)")
    hours: float = Field(..., description="Кількість годин")
    notes: Optional[str] = None
    
    # Correction fields
    is_correction: bool = False
    correction_month: Optional[int] = None
    correction_year: Optional[int] = None

    class Config:
        from_attributes = True


class DailyAttendanceResponse(BaseModel):
    """Схема відповіді денної відвідуваності."""
    items: List[AttendanceResponse]
    total: int
    date: str
    present: int = 0
    absent: int = 0
    late: int = 0
    remote: int = 0


class AttendanceCreate(BaseModel):
    """Схема створення відвідуваності."""
    staff_id: int
    date: datetime
    status: str
    check_in: Optional[str] = None
    check_out: Optional[str] = None


class AttendanceCorrection(BaseModel):
    """Схема виправлення відвідуваності."""
    id: Optional[int] = None
    staff_id: int
    attendance_id: int
    correction_type: str
    original_value: str
    new_value: str
    reason: str
    status: str = "pending"
    created_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    processed_by: Optional[int] = None


class TabelResponse(BaseModel):
    """Схема табелю."""
    id: int
    year: int
    month: int
    status: str
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    attendance_records: List[AttendanceResponse] = []

    class Config:
        from_attributes = True
