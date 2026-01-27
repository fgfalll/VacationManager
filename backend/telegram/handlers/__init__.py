"""Telegram bot handlers module."""

from backend.telegram.handlers.commands import register_command_handlers
from backend.telegram.handlers.callbacks import register_callback_handlers

__all__ = ["register_command_handlers", "register_callback_handlers"]
