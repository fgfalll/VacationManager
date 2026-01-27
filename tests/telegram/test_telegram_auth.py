"""Tests for Telegram authentication and signature verification."""

import hmac
import hashlib
from datetime import datetime, timezone


def test_verify_telegram_init_data_valid():
    """Test verification of valid Telegram initData."""
    from backend.api.routes.telegram import verify_telegram_init_data, parse_init_data

    # Create test data
    bot_token = "123456789:ABCDEF"
    user_id = "123456"
    user_data = f'{{"id":{user_id},"first_name":"Test","username":"testuser"}}'

    # Create hash
    data_check_string = f"auth_date={int(datetime.now(tz=timezone.utc).timestamp())}\nquery_id=AABBCCDD\nuser={user_data}"
    secret_key = hmac.new(
        "WebAppData".encode(),
        bot_token.encode(),
        hashlib.sha256
    ).digest()

    hash_value = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    init_data = f"auth_date={int(datetime.now(tz=timezone.utc).timestamp())}&query_id=AABBCCDD&user={user_data}&hash={hash_value}"

    # Should verify successfully
    assert verify_telegram_init_data(init_data, bot_token) == True


def test_verify_telegram_init_data_invalid():
    """Test verification of invalid Telegram initData."""
    from backend.api.routes.telegram import verify_telegram_init_data

    bot_token = "123456789:ABCDEF"
    init_data = "invalid_data"

    # Should fail verification
    assert verify_telegram_init_data(init_data, bot_token) == False


def test_verify_telegram_init_data_no_hash():
    """Test verification without hash parameter."""
    from backend.api.routes.telegram import verify_telegram_init_data

    bot_token = "123456789:ABCDEF"
    init_data = "auth_date=123456&user=test"

    # Should fail verification (no hash)
    assert verify_telegram_init_data(init_data, bot_token) == False


def test_parse_init_data():
    """Test parsing of initData string."""
    from backend.api.routes.telegram import parse_init_data

    init_data = "auth_date=123456&user=test&query_id=AABB"
    result = parse_init_data(init_data)

    assert result["auth_date"] == "123456"
    assert result["user"] == "test"
    assert result["query_id"] == "AABB"


def test_parse_init_data_empty():
    """Test parsing of empty initData."""
    from backend.api.routes.telegram import parse_init_data

    init_data = ""
    result = parse_init_data(init_data)

    assert result == {}


def test_create_access_token_for_telegram():
    """Test JWT token creation for Telegram user."""
    from backend.core.security import create_access_token

    # Create token with Telegram user ID
    staff_id = "123"
    token = create_access_token(data={"sub": staff_id})

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_expiration():
    """Test that access token has proper expiration."""
    import jwt
    from backend.core.security import create_access_token
    from backend.core.config import get_settings

    settings = get_settings()
    staff_id = "123"
    token = create_access_token(data={"sub": staff_id})

    # Decode and check expiration
    decoded = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm]
    )

    assert "exp" in decoded
    assert "sub" in decoded
    assert decoded["sub"] == staff_id
