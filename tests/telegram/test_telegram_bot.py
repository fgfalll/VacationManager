"""Tests for Telegram bot handlers and middleware."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from aiogram.types import Message, CallbackQuery, Update, User


@pytest.fixture
def mock_telegram_user():
    """Mock Telegram user."""
    user = Mock(spec=User)
    user.id = 123456
    user.first_name = "Test"
    user.last_name = "User"
    user.username = "testuser"
    return user


@pytest.fixture
def mock_message(mock_telegram_user):
    """Mock Telegram message."""
    message = Mock(spec=Message)
    message.from_user = mock_telegram_user
    message.chat = Mock()
    message.chat.id = 123456
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query(mock_telegram_user):
    """Mock Telegram callback query."""
    callback = Mock(spec=CallbackQuery)
    callback.from_user = mock_telegram_user
    callback.message = mock_message = Mock(spec=Message)
    callback.data = "test_callback"
    mock_message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_staff():
    """Mock staff member linked to Telegram user."""
    staff = Mock()
    staff.id = 1
    staff.pib_nom = "Тестов Тест Тестович"
    staff.position = "SPECIALIST"
    staff.department = "Кафедра комп'ютерних та інформаційних технологій"
    staff.telegram_user_id = "123456"
    staff.telegram_username = "testuser"
    return staff


@pytest.mark.asyncio
async def test_cmd_start_with_linked_account(mock_message, mock_staff):
    """Test /start command with linked Telegram account."""
    from backend.telegram.handlers.commands import cmd_start

    with patch('backend.telegram.handlers.commands.get_db') as mock_get_db:
        # Mock database to return staff
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_staff
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        await cmd_start(mock_message)

        # Should send welcome message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "Вітаю" in call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_start_without_linked_account(mock_message):
    """Test /start command without linked Telegram account."""
    from backend.telegram.handlers.commands import cmd_start

    with patch('backend.telegram.handlers.commands.get_db') as mock_get_db:
        # Mock database to return None (no linked account)
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        await cmd_start(mock_message)

        # Should prompt to share contact
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "ще не прив'язаний" in call_args[0][0] or "not linked" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_cmd_help(mock_message):
    """Test /help command."""
    from backend.telegram.handlers.commands import cmd_help

    await cmd_help(mock_message)

    # Should send help text
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "Довідка" in call_args[0][0] or "Help" in call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_settings(mock_message):
    """Test /settings command."""
    from backend.telegram.handlers.commands import cmd_settings

    await cmd_settings(mock_message)

    # Should send settings message
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_menu(mock_message):
    """Test /menu command."""
    from backend.telegram.handlers.commands import cmd_menu

    await cmd_menu(mock_message)

    # Should send menu
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "Головне меню" in call_args[0][0] or "Main menu" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_callback_main_menu(mock_callback_query):
    """Test main menu callback handler."""
    from backend.telegram.handlers.callbacks import callback_main_menu

    await callback_main_menu(mock_callback_query)

    # Should edit message with main menu
    mock_callback_query.message.edit_text.assert_called_once()
    mock_callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_documents_today(mock_callback_query):
    """Test today's documents callback handler."""
    from backend.telegram.handlers.callbacks import callback_documents_today

    with patch('backend.telegram.handlers.callbacks.get_db') as mock_get_db:
        # Mock database to return documents
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        from backend.models.document import Document

        # Create mock documents
        mock_doc1 = Mock(spec=Document)
        mock_doc1.id = 1
        mock_doc1.doc_type = "VACATION_PAID"
        mock_doc1.status = "DRAFT"
        mock_doc1.created_at = "2026-01-22"
        mock_doc1.staff = Mock()
        mock_doc1.staff.pib_nom = "Тестов Тест"

        mock_result.scalars.return_value.all.return_value = [mock_doc1]
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        await callback_documents_today(mock_callback_query)

        # Should edit message with documents
        mock_callback_query.message.edit_text.assert_called_once()
        mock_callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_documents_stale(mock_callback_query):
    """Test stale documents callback handler."""
    from backend.telegram.handlers.callbacks import callback_documents_stale

    with patch('backend.telegram.handlers.callbacks.get_db') as mock_get_db:
        # Mock database to return stale documents
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []  # No stale docs
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        await callback_documents_stale(mock_callback_query)

        # Should edit message
        mock_callback_query.message.edit_text.assert_called_once()
        mock_callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_scanner_open(mock_callback_query):
    """Test scanner callback handler."""
    from backend.telegram.handlers.callbacks import callback_scanner_open

    with patch('backend.telegram.handlers.callbacks.get_settings') as mock_settings:
        mock_config = Mock()
        mock_config.telegram_mini_app_url = "https://example.com/app"
        mock_settings.return_value = mock_config

        await callback_scanner_open(mock_callback_query)

        # Should show message with Mini App URL
        mock_callback_query.message.edit_text.assert_called_once()
        mock_callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_attendance_add(mock_callback_query):
    """Test attendance add callback handler."""
    from backend.telegram.handlers.callbacks import callback_attendance_add

    await callback_attendance_add(mock_callback_query)

    # Should show message about using Mini App
    mock_callback_query.message.edit_text.assert_called_once()
    mock_callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_doc_sign(mock_callback_query):
    """Test document sign callback handler."""
    from backend.telegram.handlers.callbacks import callback_doc_sign

    mock_callback_query.data = "doc_sign_123"

    await callback_doc_sign(mock_callback_query)

    # Should show alert
    mock_callback_query.answer.assert_called_once()
    call_args = mock_callback_query.answer.call_args
    assert "show_alert" in call_args[1] or call_args[1].get("show_alert") == True


@pytest.mark.asyncio
async def test_callback_stale_resolve(mock_callback_query):
    """Test stale document resolve callback handler."""
    from backend.telegram.handlers.callbacks import callback_stale_resolve

    mock_callback_query.data = "stale_resolve_456"

    await callback_stale_resolve(mock_callback_query)

    # Should show alert
    mock_callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_settings_profile(mock_callback_query, mock_staff):
    """Test settings profile callback handler."""
    from backend.telegram.handlers.callbacks import callback_settings_profile

    with patch('backend.telegram.handlers.callbacks.get_db') as mock_get_db:
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_staff
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        await callback_settings_profile(mock_callback_query)

        # Should edit message with profile
        mock_callback_query.message.edit_text.assert_called_once()
        mock_callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_telegram_auth_middleware_with_linked_account(mock_message, mock_staff):
    """Test Telegram auth middleware with linked account."""
    from backend.telegram.middleware import TelegramAuthMiddleware

    middleware = TelegramAuthMiddleware()
    handler = AsyncMock(return_value="handler_result")

    with patch('backend.telegram.middleware.get_db') as mock_get_db:
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_staff
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        # Create mock update
        update = Mock(spec=Update)
        update.message = mock_message

        data = {}

        result = await middleware(handler, update, data)

        # Should add staff to data and call handler
        assert data.get("staff") == mock_staff
        assert result == "handler_result"


@pytest.mark.asyncio
async def test_telegram_auth_middleware_without_linked_account(mock_message):
    """Test Telegram auth middleware without linked account."""
    from backend.telegram.middleware import TelegramAuthMiddleware

    middleware = TelegramAuthMiddleware()
    handler = AsyncMock(return_value="handler_result")

    with patch('backend.telegram.middleware.get_db') as mock_get_db:
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        # Create mock update
        update = Mock(spec=Update)
        update.message = mock_message

        data = {}

        result = await middleware(handler, update, data)

        # Should add None staff and still call handler
        assert data.get("staff") is None
        assert result == "handler_result"


@pytest.mark.asyncio
async def test_require_auth_middleware_without_link(mock_message):
    """Test RequireAuthMiddleware blocks unauthenticated users."""
    from backend.telegram.middleware import RequireAuthMiddleware

    middleware = RequireAuthMiddleware()
    handler = AsyncMock(return_value="handler_result")

    with patch('backend.telegram.middleware.get_db') as mock_get_db:
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        # Create mock update
        update = Mock(spec=Update)
        update.message = mock_message

        data = {}

        result = await middleware(handler, update, data)

        # Should NOT call handler
        handler.assert_not_called()
        assert result is None


@pytest.mark.asyncio
async def test_require_auth_middleware_with_link(mock_message, mock_staff):
    """Test RequireAuthMiddleware allows authenticated users."""
    from backend.telegram.middleware import RequireAuthMiddleware

    middleware = RequireAuthMiddleware()
    handler = AsyncMock(return_value="handler_result")

    with patch('backend.telegram.middleware.get_db') as mock_get_db:
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_staff
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value = iter([mock_db])

        # Create mock update
        update = Mock(spec=Update)
        update.message = mock_message

        data = {}

        result = await middleware(handler, update, data)

        # Should call handler
        handler.assert_called_once()
        assert result == "handler_result"
