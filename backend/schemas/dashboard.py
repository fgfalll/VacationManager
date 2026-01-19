"""Dashboard schemas."""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Schema for dashboard statistics."""
    total_staff: int
    active_staff: int
    pending_documents: int
    upcoming_vacations: int
