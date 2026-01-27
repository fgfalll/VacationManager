"""Middleware for Telegram bot authentication."""

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from typing import Any, Callable, Dict, Awaitable, Optional, Set
from collections import deque

from backend.core.database import get_db
from backend.models.staff import Staff
from sqlalchemy import select


# Messages that should trigger chat cleanup (entry points)
CLEANUP_TRIGGER_MESSAGES = {
    "📄 Мої документи",
    "📋 Сьогоднішні",
    "⚠️ Проблемні",
    "👤 Профіль",
    "❓ Допомога",
}

# In-memory store for tracking bot messages per user
# Format: {user_id: deque([message_id, ...])}
_user_message_history: Dict[int, deque] = {}
_MAX_HISTORY_SIZE = 50  # Keep track of last 50 messages per user


class TrackedBot:
    """Wrapper for Bot that tracks all sent messages."""

    def __init__(self, original_bot: Bot, user_id: int):
        self._original = original_bot
        self._user_id = user_id

    async def send_message(self, chat_id, *args, **kwargs):
        """Send message and track it."""
        result = await self._original.send_message(chat_id, *args, **kwargs)
        track_bot_message(self._user_id, result.message_id)
        return result

    async def delete_message(self, chat_id, message_id):
        """Delete message - pass through."""
        return await self._original.delete_message(chat_id, message_id)

    def __getattr__(self, name):
        """Proxy all other attributes to original bot."""
        return getattr(self._original, name)


class TrackedMessage:
    """Wrapper for Message that tracks all bot responses."""

    def __init__(self, original_message: Message, user_id: int, tracked_bot: TrackedBot = None):
        self._original = original_message
        self._user_id = user_id
        self._tracked_bot = tracked_bot

    async def answer(self, *args, **kwargs):
        """Send message and track it."""
        result = await self._original.answer(*args, **kwargs)
        track_bot_message(self._user_id, result.message_id)
        return result

    async def edit_text(self, *args, **kwargs):
        """Edit message - don't track edits, only new messages."""
        return await self._original.edit_text(*args, **kwargs)

    async def edit_reply_markup(self, *args, **kwargs):
        """Edit reply markup - don't track edits."""
        return await self._original.edit_reply_markup(*args, **kwargs)

    async def reply(self, *args, **kwargs):
        """Reply to message and track it."""
        result = await self._original.reply(*args, **kwargs)
        track_bot_message(self._user_id, result.message_id)
        return result

    @property
    def bot(self):
        """Return tracked bot if available."""
        return self._tracked_bot if self._tracked_bot else self._original.bot

    def __getattr__(self, name):
        """Proxy all other attributes to original message."""
        return getattr(self._original, name)


def _get_user_history(user_id: int) -> deque:
    """Get or create message history for user."""
    if user_id not in _user_message_history:
        _user_message_history[user_id] = deque(maxlen=_MAX_HISTORY_SIZE)
    return _user_message_history[user_id]


async def _delete_messages_safe(bot: Bot, chat_id: int, message_ids: Set[int]) -> None:
    """Safely delete multiple messages, ignoring errors for already deleted messages."""
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            # Message already deleted or doesn't exist - ignore
            pass


async def clear_chat_history(bot: Bot, chat_id: int, user_id: int) -> None:
    """
    Clear all tracked bot messages for a user.

    Args:
        bot: Aiogram bot instance
        chat_id: Telegram chat ID
        user_id: Telegram user ID
    """
    history = _get_user_history(user_id)
    if history:
        await _delete_messages_safe(bot, chat_id, set(history))
        history.clear()


def track_bot_message(user_id: int, message_id: int) -> None:
    """
    Track a bot message for potential cleanup.

    Args:
        user_id: Telegram user ID
        message_id: ID of the message sent by bot
    """
    history = _get_user_history(user_id)
    history.append(message_id)


async def answer_tracked(
    message: Message,
    text: str,
    user_id: int,
    **kwargs
) -> Message:
    """
    Send a message and track it for cleanup.

    Args:
        message: Original message object
        text: Text to send
        user_id: User ID for tracking
        **kwargs: Additional arguments for message.answer()

    Returns:
        Sent message object
    """
    sent = await message.answer(text, **kwargs)
    track_bot_message(user_id, sent.message_id)
    return sent


class ChatHistoryCleanupMiddleware(BaseMiddleware):
    """
    Middleware that clears chat history when new requests start.

    Deletes bot messages when:
    - Commands are sent (/, /menu, /docs, etc.)
    - Reply keyboard buttons are pressed

    Automatically tracks all bot messages sent during handler execution.
    Preserves history for:
    - Callback queries (continuing inline keyboard flows)
    - Regular text messages
    """

    def __init__(self):
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Clear chat history for entry point commands/messages.

        Args:
            handler: Event handler
            event: Event (Message, CallbackQuery, etc.)
            data: Context data

        Returns:
            Handler execution result
        """
        bot = data.get("bot")
        should_cleanup = False
        chat_id = None
        user_id = None
        tracked_bot = None
        original_message = None

        if isinstance(event, Update):
            message = event.message
            callback_query = event.callback_query

            # Get chat_id and user_id from message
            if message:
                chat_id = message.chat.id
                user_id = message.from_user.id

                # Cleanup for commands
                if message.text and message.text.startswith("/"):
                    should_cleanup = True

                # Cleanup for reply keyboard messages
                elif message.text in CLEANUP_TRIGGER_MESSAGES:
                    should_cleanup = True

            # Callback queries - optionally cleanup the message being clicked
            elif callback_query:
                chat_id = callback_query.message.chat.id
                user_id = callback_query.from_user.id
                # Don't cleanup for callback queries - they're part of current flow
                should_cleanup = False

        # Perform cleanup before handler runs
        if should_cleanup and bot and chat_id and user_id:
            await clear_chat_history(bot, chat_id, user_id)

        # ALWAYS wrap bot to track all outgoing messages (even for non-cleanup triggers)
        # This ensures ALL bot messages are tracked for future cleanup
        if bot and user_id:
            tracked_bot = TrackedBot(bot, user_id)
            data["bot"] = tracked_bot

            # Also wrap message object if exists (for message handlers)
            if isinstance(event, Update) and event.message:
                original_message = event.message
                tracked_message = TrackedMessage(event.message, user_id, tracked_bot)
                # Update data so handler gets tracked message
                data["message"] = tracked_message
                # Also update the event message
                event.message = tracked_message

            # Also wrap callback message for callback handlers
            elif isinstance(event, Update) and event.callback_query:
                original_message = event.callback_query.message
                tracked_callback_message = TrackedMessage(event.callback_query.message, user_id, tracked_bot)
                # Update the callback's message reference
                event.callback_query.message = tracked_callback_message
                # Also add to data for callback handlers
                data["callback_query"] = event.callback_query

        # Execute handler
        result = await handler(event, data)

        # After handler, also try to delete the user's trigger message for cleaner chat
        if should_cleanup and bot and chat_id:
            try:
                # Delete the trigger message
                msg_to_delete = original_message if original_message else event.message
                await bot.delete_message(chat_id, msg_to_delete.message_id)
            except Exception:
                pass  # Ignore if can't delete (e.g., in private chat with certain message types)

        return result


class TelegramAuthMiddleware(BaseMiddleware):
    """
    Middleware для автентифікації Telegram користувачів.

    Перевіряє, чи прив'язаний Telegram акаунт до співробітника в системі.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Обробляє подію з перевіркою автентифікації.

        Args:
            handler: Обробник події
            event: Подія (Message, CallbackQuery, тощо)
            data: Дані контексту

        Returns:
            Результат виконання обробника або None
        """
        # Отримуємо user_id з події
        if isinstance(event, Update):
            user_id = event.message.from_user.id if event.message else (
                event.callback_query.from_user.id if event.callback_query else None
            )
        else:
            # Для прямого доступу до TelegramObject
            user_id = event.from_user.id if hasattr(event, 'from_user') else None

        if user_id is None:
            return None

        # Перевіряємо, чи є такий користувач в базі
        from backend.core.database import get_db_session
        async for db in get_db_session():
            result = db.execute(
                select(Staff).where(Staff.telegram_user_id == str(user_id))
            )
            staff = result.scalar_one_or_none()

        # Додаємо staff до контексту
        data["staff"] = staff

        # Якщо користувач не знайдений, можна запобігти виконанню обробника
        # або дозволити виконання з відсутнім staff
        return await handler(event, data)


class RequireAuthMiddleware(TelegramAuthMiddleware):
    """
    Middleware, що вимагає обов'язкової автентифікації.

    Якщо користувач не автентифікований, обробник не викликається.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Обробляє подію з перевіркою автентифікації.

        Args:
            handler: Обробник події
            event: Подія (Message, CallbackQuery, тощо)
            data: Дані контексту

        Returns:
            Результат виконання обробника або None
        """
        # Спочатку викликаємо батьківський middleware
        await super().__call__(handler, event, data)

        # Перевіряємо, чи користувач автентифікований
        staff = data.get("staff")
        if staff is None:
            # Користувач не автентифікований - не викликаємо обробник
            return None

        # Користувач автентифікований - викликаємо обробник
        return await handler(event, data)
