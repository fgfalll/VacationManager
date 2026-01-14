"""Custom exceptions for VacationManager."""


class VacationManagerError(Exception):
    """Базовий клас для всіх винятків системи."""

    pass


class ValidationError(VacationManagerError):
    """Виникає при валідації даних."""

    pass


class GrammarError(VacationManagerError):
    """Виникає при помилках морфологічного перетворення."""

    pass


class DocumentGenerationError(VacationManagerError):
    """Виникає при помилках генерації документів."""

    pass


class StaffNotFoundError(VacationManagerError):
    """Виникає коли співробітника не знайдено."""

    pass


class DocumentNotFoundError(VacationManagerError):
    """Виникає коли документ не знайдено."""

    pass
