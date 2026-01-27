"""Маршрути автентифікації."""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend.core.config import get_settings
from backend.core.dependencies import get_current_user
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from backend.schemas.auth import (
    MessageResponse,
    RefreshTokenRequest,
    Token,
    TokenData,
    UserCreate,
    UserLogin,
    UserResponse,
    UserRole,
)

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])

# Demo users - password hashes computed lazily
_USERS_DB: Optional[dict] = None


def _get_users_db() -> dict:
    """Lazy initialization of users database with password hashes."""
    global _USERS_DB
    if _USERS_DB is None:
        _USERS_DB = {
            "admin": {
                "password_hash": get_password_hash("admin123"),
                "id": 1,
                "email": "admin@company.com",
                "first_name": "Admin",
                "last_name": "User",
                "role": "admin",
                "staff_id": None,
                "is_active": True,
            },
            "head": {
                "password_hash": get_password_hash("head123"),
                "id": 2,
                "email": "head@department.com",
                "first_name": "Department",
                "last_name": "Head",
                "role": "department_head",
                "staff_id": None,
                "is_active": True,
            },
            "employee": {
                "password_hash": get_password_hash("emp123"),
                "id": 3,
                "email": "employee@company.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "employee",
                "staff_id": 1,
                "is_active": True,
            },
        }
    return _USERS_DB


def get_user_by_username(username: str) -> dict | None:
    """Отримує користувача за іменем."""
    return _get_users_db().get(username)


def authenticate_user(username: str, password: str) -> dict | None:
    """Автентифікує користувача."""
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


@router.post("/login", response_model=Token)
async def login(login_data: UserLogin):
    """
    Автентифікація користувача та видача токенів (Login).

    Перевіряє ім'я користувача та пароль. У разі успіху видає пару JWT токенів.
    Access token використовується для авторизації запитів (header `Authorization: Bearer <token>`).
    Refresh token використовується для отримання нових access token, коли старий спливає.

    Parameters:
    - **login_data** (UserLogin): JSON з `username` та `password`.

    Returns:
    - **access_token** (str): Токен доступу (короткоживучий).
    - **refresh_token** (str): Токен оновлення (довгоживучий).
    - **token_type** (str): завжди "bearer".

    Errors:
    - **401 Unauthorized**: Невірний логін або пароль.
    """
    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": str(user["id"]),
            "username": login_data.username,
            "role": user["role"],
        },
        expires_delta=access_token_expires,
    )

    refresh_token = create_refresh_token(
        data={
            "sub": str(user["id"]),
            "type": "refresh",
        }
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshTokenRequest):
    """
    Оновити Access Token (Refresh Token Exchange).

    Використовує валідний Refresh Token для отримання нової пари токенів.
    Це дозволяє користувачу залишатися залогіненим без повторного введення пароля.

    Parameters:
    - **request** (RefreshTokenRequest): JSON з `refresh_token`.

    Returns:
    - Нова пара access_token та refresh_token.

    Errors:
    - **401 Unauthorized**: Якщо refresh token невірний, прострочений або користувач заблокований.
    """
    token_data = decode_token(request.refresh_token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = token_data.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token data",
        )

    # Find user
    user = None
    for username, user_data in _get_users_db().items():
        if str(user_data["id"]) == str(user_id):
            user = user_data
            break

    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": str(user["id"]),
            "username": list(_get_users_db().keys())[list(_get_users_db().values()).index(user)],
            "role": user["role"],
        },
        expires_delta=access_token_expires,
    )

    refresh_token = create_refresh_token(
        data={
            "sub": str(user["id"]),
            "type": "refresh",
        }
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout", response_model=MessageResponse)
async def logout():
    """
    Вихід із системи (Logout).

    Наразі це "stateless" вихід - клієнт просто видаляє токени.
    У майбутньому тут можна додати логіку інвалідації токенів (blacklist).

    Returns:
    - Повідомлення про успішний вихід.
    """
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """
    Отримати інформацію про поточного користувача.

    Повертає профіль користувача, витягнутий з токена авторизації.
    Використовується фронтендом для відображення імені та прав доступу.
    """
    user = get_user_by_username(current_user.username or "")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=user["id"],
        username=current_user.username or "",
        email=user["email"],
        first_name=user["first_name"],
        last_name=user["last_name"],
        role=user["role"],
        staff_id=user["staff_id"],
        is_active=user["is_active"],
        created_at=None,
        updated_at=None,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Реєстрація нового користувача в системі.

    Створює обліковий запис, який може бути прив'язаний до існуючого співробітника (staff_id).
    За замовчуванням новий користувач активний.

    Parameters:
    - **user_data** (UserCreate): Дані нового користувача.

    Errors:
    - **400 Bad Request**: Якщо username вже зайнятий.
    """
    if get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    new_user = {
        "password_hash": get_password_hash(user_data.password),
        "id": len(_get_users_db()) + 1,
        "email": user_data.email,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "role": user_data.role,
        "staff_id": user_data.staff_id,
        "is_active": True,
    }

    _get_users_db()[user_data.username] = new_user

    return UserResponse(
        id=new_user["id"],
        username=user_data.username,
        email=user_data.email,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role,
        staff_id=user_data.staff_id,
        is_active=True,
        created_at=None,
        updated_at=None,
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    old_password: str,
    new_password: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Зміна пароля користувача.

    Дозволяє авторизованому користувачу змінити свій пароль.
    Вимагає введення старого пароля для підтвердження.

    Parameters:
    - **old_password**: Поточний пароль.
    - **new_password**: Новий пароль.
    
    Errors:
    - **400 Bad Request**: Якщо старий пароль невірний.
    """
    username = current_user.username
    user = get_user_by_username(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not verify_password(old_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    # Update password hash
    _get_users_db()[username]["password_hash"] = get_password_hash(new_password)

    return {"message": "Password changed successfully"}
