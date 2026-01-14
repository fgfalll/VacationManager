"""Спільні схеми відповідей API."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel):
    """Базова схема успішної відповіді."""

    success: bool = True
    message: str = "Операція виконана успішно"


class ErrorResponse(BaseModel):
    """Схема відповіді з помилкою."""

    success: bool = False
    message: str
    detail: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Схема для пагінованої відповіді."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class UploadResponse(BaseModel):
    """Схема відповіді при завантаженні файлу."""

    success: bool
    file_path: str | None = None
    message: str


class ValidationErrorResponse(BaseModel):
    """Схема відповіді з валідаційними помилками."""

    success: bool = False
    message: str = "Помилка валідації даних"
    errors: dict[str, list[str]] = {}


class SettingsResponse(BaseModel):
    """Схема відповіді з налаштуваннями."""

    rector_name_dative: str
    rector_title: str
    dept_name: str
    dept_head_id: int | None
    approvers: list[dict[str, Any]]


class SettingsUpdate(BaseModel):
    """Схема для оновлення налаштувань."""

    rector_name_dative: str | None = None
    rector_title: str | None = None
    dept_name: str | None = None
    dept_head_id: int | None = None
