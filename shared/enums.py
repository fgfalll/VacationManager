"""Enumerations for VacationManager.

All system-wide enums are defined here.
"""
from enum import Enum


class EmploymentType(str, Enum):
    """Тип працевлаштування"""
    MAIN = "main"                      # Основне місце роботи
    EXTERNAL = "external"              # Зовнішній сумісник
    INTERNAL = "internal"              # Внутрішній сумісник


class WorkBasis(str, Enum):
    """Основа роботи"""
    CONTRACT = "contract"              # Контракт
    COMPETITIVE = "competitive"        # Конкурсна основа
    STATEMENT = "statement"            # Заява


class DocumentType(str, Enum):
    """Тип документа"""
    VACATION_PAID = "vacation_paid"           # Відпустка оплачувана
    VACATION_UNPAID = "vacation_unpaid"       # Відпустка без збереження зарплати
    TERM_EXTENSION = "term_extension"         # Продовження терміну контракту


class DocumentStatus(str, Enum):
    """Статус документа"""
    DRAFT = "draft"                    # Чернетка
    ON_SIGNATURE = "on_signature"      # На підписі
    SIGNED = "signed"                  # Підписано
    PROCESSED = "processed"            # Оброблено (дні списано)


class UserRole(str, Enum):
    """Роль користувача"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class StaffActionType(str, Enum):
    """Тип дії над записом співробітника"""
    CREATE = "create"              # Створення запису
    UPDATE = "update"              # Оновлення даних
    DEACTIVATE = "deactivate"      # Деактивація (soft delete)
    RESTORE = "restore"            # Відновлення (створення нового запису)
