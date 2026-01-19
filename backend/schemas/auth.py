"""Схеми Pydantic для автентифікації."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """Ролі користувачів в системі."""
    ADMIN = "admin"                    # Адміністратор - повний доступ
    DEPARTMENT_HEAD = "department_head"  # Завідувач кафедри - перегляд та затвердження
    EMPLOYEE = "employee"              # Співробітник - тільки свої дані


class Token(BaseModel):
    """Схема для відповіді JWT токена."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Дані, що розшифровуються з токена."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None


class UserLogin(BaseModel):
    """Схема для запиту логіну."""
    username: str = Field(..., min_length=3, max_length=50, description="Ім'я користувача")
    password: str = Field(..., min_length=6, description="Пароль")


class UserCreate(BaseModel):
    """Схема для створення користувача."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    role: UserRole = Field(default=UserRole.EMPLOYEE)
    staff_id: Optional[int] = None


class UserResponse(BaseModel):
    """Схема відповіді користувача."""
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    role: UserRole
    staff_id: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    """Схема для оновлення токена."""
    refresh_token: str


class MessageResponse(BaseModel):
    """Загальна схема відповіді з повідомленням."""
    message: str
