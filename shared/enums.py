"""Enumerations for VacationManager.

All system-wide enums are defined here.
"""
from enum import Enum


# Mapping dictionaries for UI labels
EMPLOYMENT_TYPE_LABELS: dict[str, str] = {
    "main": "Основне місце роботи",
    "external": "Зовнішній сумісник",
    "internal": "Внутрішній сумісник",
}

WORK_BASIS_LABELS: dict[str, str] = {
    "contract": "Контракт",
    "competitive": "Конкурсна основа",
    "statement": "Заява",
}

STAFF_POSITION_LABELS: dict[str, str] = {
    "head_of_department": "Завідувач кафедри",
    "acting_head": "В.о завідувача кафедри",
    "professor": "Професор",
    "associate_professor": "Доцент",
    "senior_lecturer": "Старший викладач",
    "lecturer": "Асистент",
    "specialist": "Фахівець",
}


def get_position_label(value: str) -> str:
    """Get Ukrainian label for position value."""
    return STAFF_POSITION_LABELS.get(value, value)


def get_employment_type_label(value: str) -> str:
    """Get Ukrainian label for employment type value."""
    return EMPLOYMENT_TYPE_LABELS.get(value, value)


def get_work_basis_label(value: str) -> str:
    """Get Ukrainian label for work basis value."""
    return WORK_BASIS_LABELS.get(value, value)


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


class StaffPosition(str, Enum):
    """Посада співробітника"""
    HEAD_OF_DEPARTMENT = "head_of_department"          # Завідувач кафедри
    ACTING_HEAD_OF_DEPARTMENT = "acting_head"           # В.о завідувача кафедри
    PROFESSOR = "professor"                             # Професор
    ASSOCIATE_PROFESSOR = "associate_professor"         # Доцент
    SENIOR_LECTURER = "senior_lecturer"                 # Старший викладач
    LECTURER = "lecturer"                               # Асистент
    SPECIALIST = "specialist"                           # Фахівець


class DocumentType(str, Enum):
    """Тип документа"""
    VACATION_PAID = "vacation_paid"           # Відпустка оплачувана
    VACATION_UNPAID = "vacation_unpaid"       # Відпустка без збереження зарплати
    TERM_EXTENSION = "term_extension"         # Продовження терміну контракту

    # Оплачувані відпустки
    VACATION_MAIN = "vacation_main"           # Основна щорічна відпустка (код В)
    VACATION_ADDITIONAL = "vacation_additional"  # Додаткова щорічна відпустка (код Д)
    VACATION_CHORNOBYL = "vacation_chornobyl"    # Додаткова відпустка чорнобильцям (код Ч)
    VACATION_CREATIVE = "vacation_creative"      # Творча відпустка (код ТВ)
    VACATION_STUDY = "vacation_study"            # Додаткова відпустка у зв'язку з навчанням (код Н)
    VACATION_CHILDREN = "vacation_children"      # Додаткова оплачувана відпустка працівникам з дітьми (код ДО)
    VACATION_MATERNITY = "vacation_maternity"    # Відпустка у зв'язку з вагітністю та пологами (код ВП)
    VACATION_CHILDCARE = "vacation_childcare"    # Відпустка для догляду за дитиною до 6 років (код ДД)

    # Відпустки без збереження зарплати
    VACATION_UNPAID_STUDY = "vacation_unpaid_study"        # Відпустка без збереження у зв'язку з навчанням (код НБ)
    VACATION_UNPAID_MANDATORY = "vacation_unpaid_mandatory"  # Відпустка без збереження в обов'язковому порядку (код ДБ)
    VACATION_UNPAID_AGREEMENT = "vacation_unpaid_agreement"  # Відпустка без збереження за згодою сторін (код НА)
    VACATION_UNPAID_OTHER = "vacation_unpaid_other"          # Інші відпустки без збереження зарплати (код БЗ)

    # Продовження контракту
    TERM_EXTENSION_CONTRACT = "term_extension_contract"     # Продовження контракту - контрактна основа
    TERM_EXTENSION_COMPETITION = "term_extension_competition"  # Продовження контракту - конкурсна основа
    TERM_EXTENSION_PDF = "term_extension_pdf"               # Продовження контракту - PDF (вручну)

    # Прийом на роботу
    EMPLOYMENT_CONTRACT = "employment_contract"              # Прийом на роботу - контракт
    EMPLOYMENT_COMPETITION = "employment_competition"        # Прийом на роботу - конкурс
    EMPLOYMENT_PDF = "employment_pdf"                        # Прийом на роботу - PDF


class DocumentStatus(str, Enum):
    """Статус документа"""
    DRAFT = "draft"                    # Чернетка
    ON_SIGNATURE = "on_signature"      # На підписі (хоча б один підпис)
    AGREED = "agreed"                  # Погоджено (всі проміжні підписи є)
    SIGNED = "signed"                  # Підписано ректором
    SCANNED = "scanned"                # Відскановано (є скан)
    PROCESSED = "processed"            # Оброблено (додано в табель)


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
