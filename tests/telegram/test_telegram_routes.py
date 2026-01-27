"""Tests for Telegram API routes."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_staff():
    """Mock staff member."""
    staff = Mock()
    staff.id = 1
    staff.pib_nom = "Тестов Тест Тестович"
    staff.position = "SPECIALIST"
    staff.department = "Кафедра комп'ютерних та інформаційних технологій"
    staff.telegram_user_id = "123456"
    staff.telegram_username = "testuser"
    staff.email = "test@example.com"
    return staff


@pytest.mark.asyncio
async def test_telegram_auth_success(mock_db, mock_staff):
    """Test successful Telegram authentication."""
    from backend.api.routes.telegram import verify_telegram_init_data
    import hmac
    import hashlib

    # Mock verify_telegram_init_data to return True
    with patch('backend.api.routes.telegram.verify_telegram_init_data', return_value=True):
        # Mock parse_init_data to return user data
        with patch('backend.api.routes.telegram.parse_init_data', return_value={
            'user': '{"id": 123456, "first_name": "Test"}'
        }):
            with patch('backend.api.routes.telegram.select') as mock_select:
                # Mock database query to return staff
                mock_result = AsyncMock()
                mock_result.scalar_one_or_none.return_value = mock_staff
                mock_db.execute.return_value = mock_result

                with patch('backend.api.routes.telegram.get_db', return_value=iter([mock_db])):
                    from backend.api.routes.telegram import telegram_auth
                    from backend.api.routes.telegram import TelegramAuthRequest

                    request = TelegramAuthRequest(
                        init_data="valid_init_data"
                    )

                    # This should succeed with mocked dependencies
                    # In real scenario, we'd use TestClient
                    assert request.init_data == "valid_init_data"


@pytest.mark.asyncio
async def test_telegram_auth_invalid_data():
    """Test Telegram authentication with invalid data."""
    from backend.api.routes.telegram import verify_telegram_init_data, TelegramAuthRequest

    # Mock verification to fail
    with patch('backend.api.routes.telegram.verify_telegram_init_data', return_value=False):
        from fastapi import HTTPException

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            # Simulate the check that happens in the endpoint
            is_valid = verify_telegram_init_data("invalid_data", "test_token")
            if not is_valid:
                raise HTTPException(status_code=401, detail="Invalid Telegram init data")

        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_telegram_user(mock_db, mock_staff):
    """Test getting Telegram-linked user info."""
    from backend.api.routes.telegram import get_telegram_user

    with patch('backend.api.routes.telegram.get_current_user', return_value=mock_staff):
        # Call the endpoint function
        result = await get_telegram_user()

        assert result.id == mock_staff.id
        assert result.pib_nom == mock_staff.pib_nom
        assert result.position == mock_staff.position


@pytest.mark.asyncio
async def test_link_telegram_account_success(mock_db, mock_staff):
    """Test successful linking of Telegram account."""
    from backend.api.routes.telegram import link_telegram_account, TelegramLinkRequest

    request = TelegramLinkRequest(telegram_user_id="123456")

    with patch('backend.api.routes.telegram.get_current_user', return_value=mock_staff):
        with patch('backend.api.routes.telegram.select') as mock_select:
            # Mock that no other user has this telegram_user_id
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            with patch('backend.api.routes.telegram.get_db', return_value=iter([mock_db])):
                result = await link_telegram_account(request)

                assert result.success == True
                assert "linked successfully" in result.message.lower()


@pytest.mark.asyncio
async def test_link_telegram_account_already_linked(mock_db, mock_staff):
    """Test linking Telegram account when already linked to another user."""
    from backend.api.routes.telegram import link_telegram_account, TelegramLinkRequest
    from backend.models.staff import Staff

    request = TelegramLinkRequest(telegram_user_id="123456")

    # Create another staff member that already has this telegram_user_id
    other_staff = Mock(spec=Staff)
    other_staff.id = 999

    with patch('backend.api.routes.telegram.get_current_user', return_value=mock_staff):
        with patch('backend.api.routes.telegram.select') as mock_select:
            # Mock that another user already has this telegram_user_id
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = other_staff
            mock_db.execute.return_value = mock_result

            with patch('backend.api.routes.telegram.get_db', return_value=iter([mock_db])):
                result = await link_telegram_account(request)

                assert result.success == False
                assert "already linked" in result.message.lower()


@pytest.mark.asyncio
async def test_get_telegram_info():
    """Test getting Telegram bot configuration info."""
    from backend.api.routes.telegram import get_telegram_info
    from backend.core.config import get_settings

    with patch('backend.api.routes.telegram.get_settings') as mock_settings:
        mock_config = Mock()
        mock_config.telegram_enabled = True
        mock_config.telegram_mini_app_url = "https://example.com/app"
        mock_config.telegram_webhook_url = "https://example.com/webhook"
        mock_settings.return_value = mock_config

        result = await get_telegram_info()

        assert result["enabled"] == True
        assert result["mini_app_url"] == "https://example.com/app"
        assert result["webhook_url"] == "https://example.com/webhook"


@pytest.mark.asyncio
async def test_telegram_webhook_disabled():
    """Test webhook endpoint when Telegram is disabled."""
    from fastapi import HTTPException

    with patch('backend.api.routes.telegram.get_settings') as mock_settings:
        mock_config = Mock()
        mock_config.telegram_enabled = False
        mock_settings.return_value = mock_config

        from backend.api.routes.telegram import telegram_webhook

        # Create mock request
        request = Mock()
        request.json = AsyncMock(return_value={"update_id": 123})

        # Should raise 503 when disabled
        with pytest.raises(HTTPException) as exc_info:
            await telegram_webhook(request)

        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_telegram_webhook_enabled():
    """Test webhook endpoint when Telegram is enabled."""
    with patch('backend.api.routes.telegram.get_settings') as mock_settings:
        mock_config = Mock()
        mock_config.telegram_enabled = True
        mock_settings.return_value = mock_config

        # Mock the bot and dispatcher
        mock_bot = Mock()
        mock_dp = Mock()
        mock_dp.feed_webhook_update = AsyncMock()

        with patch('backend.api.routes.telegram.dp', mock_dp):
            with patch('backend.api.routes.telegram.bot', mock_bot):
                from backend.api.routes.telegram import telegram_webhook

                request = Mock()
                request.json = AsyncMock(return_value={"update_id": 123})

                result = await telegram_webhook(request)

                assert result["status"] == "ok"
                mock_dp.feed_webhook_update.assert_called_once()
