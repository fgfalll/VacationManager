"""FSM states for Telegram bot conversations."""

from aiogram.fsm.state import State, StatesGroup


class StaleExplanationStates(StatesGroup):
    """States for stale document explanation flow."""
    waiting_for_explanation = State()
    document_id: int = None  # Store document ID in state data instead


class LinkRequestStates(StatesGroup):
    """States for link request approval flow."""
    waiting_for_staff_id = State()
    request_id: int = None


class EmployeeSearchStates(StatesGroup):
    """States for employee search flow (admin only)."""
    waiting_for_employee_name = State()

