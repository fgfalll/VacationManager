"""API маршрути для налаштувань."""

from fastapi import APIRouter, Depends

from backend.core.dependencies import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(
    current_user: get_current_user = Depends(get_current_user),
):
    """
    Отримати поточні налаштування користувача.
    """
    return {
        "notifications": {
            "email_enabled": True,
            "document_updates": True,
            "schedule_reminders": True,
        },
        "theme": "light",
    }


@router.put("")
async def update_settings(
    settings_data: dict,
    current_user: get_current_user = Depends(get_current_user),
):
    """
    Оновити налаштування.
    """
    return {"message": "Settings updated", "settings": settings_data}
