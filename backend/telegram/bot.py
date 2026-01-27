"""Telegram bot setup with aiogram 3.x."""

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from backend.core.config import get_settings

settings = get_settings()

# Only initialize bot if token is provided
# This allows the module to be imported during tests without a valid token
if settings.telegram_bot_token:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
else:
    bot = None

dp = Dispatcher()
