"""Залежності для автентифікації."""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import decode_token
from backend.schemas.auth import TokenData

# OAuth2 схема для отримання токена з заголовку
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Залежність для отримання поточного користувача з токена.

    Args:
        token: JWT токен з заголовку Authorization
        db: Сесія бази даних

    Returns:
        Дані користувача

    Raises:
        HTTPException: Якщо токен недійсний
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_token(token)
    if token_data is None:
        raise credentials_exception

    # Тут потрібно отримати користувача з бази
    # Поки повертаємо дані з токена
    user_id = token_data.get("sub")
    if user_id is None:
        raise credentials_exception

    return TokenData(
        user_id=int(user_id),
        username=token_data.get("username"),
        role=token_data.get("role")
    )


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user)
):
    """
    Перевіряє що користувач активний.

    Args:
        current_user: Дані поточного користувача

    Returns:
        Дані користувача

    Raises:
        HTTPException: Якщо користувач неактивний
    """
    # Тут потрібно перевірити чи активний користувач
    return current_user


def require_role(allowed_roles: list):
    """
    Фабрика залежностей для перевірки ролі користувача.

    Args:
        allowed_roles: Список дозволених ролей

    Returns:
        Залежність
    """
    async def role_checker(
        current_user: TokenData = Depends(get_current_user)
    ) -> TokenData:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user

    return role_checker


# Готові залежності для різних ролей
require_admin = require_role(["admin"])
require_hr = require_role(["admin", "hr"])
require_employee = require_role(["admin", "hr", "employee"])
