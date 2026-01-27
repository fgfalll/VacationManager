"""Налаштування додатку через Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Налаштування додатку, що завантажуються з .env файлу або змінних середовища."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="VM_",
        extra="ignore",
    )

    # APP
    app_name: str = Field(default="VacationManager", description="Назва додатку")
    app_version: str = Field(default="5.5.0", description="Версія додатку")
    debug: bool = Field(default=False, description="Режим налагодження")

    # DATABASE
    database_url: str = Field(
        default="sqlite:///./vacation_manager.db",
        description="URL бази даних (SQLite або PostgreSQL)",
    )

    # SECURITY
    secret_key: str = Field(
        default="change-me-in-production-use-secrets-manager",
        description="Секретний ключ для JWT токенів",
    )
    access_token_expire_minutes: int = Field(
        default=24 * 60,  # 24 години
        description="Час життя JWT токена в хвилинах",
    )
    algorithm: str = Field(default="HS256", description="Алгоритм шифрування JWT")

    # WEB SERVER
    host: str = Field(default="127.0.0.1", description="Хост для FastAPI сервера")
    port: int = Field(default=8000, description="Порт для FastAPI сервера")
    reload: bool = Field(default=False, description="Автоматичний перезапуск при зміні коду")

    # STORAGE
    storage_dir: Path = Field(
        default=Path("./storage"),
        description="Директорія для зберігання файлів документів",
    )
    templates_dir: Path = Field(
        default=Path("./templates"),
        description="Директорія з Word шаблонами",
    )

    # LOGGING
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Рівень логування",
    )
    log_format: Literal["json", "console"] = Field(
        default="console",
        description="Формат логування",
    )

    # BACKUP
    backup_enabled: bool = Field(
        default=True,
        description="Чи увімкнено резервне копіювання",
    )
    backup_retention_days: int = Field(
        default=30,
        description="Кількість днів зберігання бекапів",
    )

    # NOTIFICATIONS
    notification_contract_expiry_days: int = Field(
        default=30,
        description="За скільки днів попереджати про закінчення контракту",
    )

    # TELEGRAM
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token для Mini App",
    )
    telegram_webhook_url: str = Field(
        default="",
        description="Webhook URL для Telegram бота",
    )
    telegram_enabled: bool = Field(
        default=False,
        description="Увімкнути Telegram бота",
    )
    telegram_mini_app_url: str = Field(
        default="",
        description="URL Mini App для відкриття в Telegram",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Повертає кешований екземпляр налаштувань.

    Returns:
        Settings: Екземпляр налаштувань додатку
    """
    return Settings()
