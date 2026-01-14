"""Сервіс управління співробітниками."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.models.staff import Staff
from backend.models.staff_history import StaffHistory
from shared.enums import StaffActionType
from shared.exceptions import ValidationError


class StaffService:
    """
    Сервіс для управління записами співробітників та їхньою історією.

    Відстежує всі зміни в записах, автоматично деактивує прострочені контракти,
    та забезпечує функціональність відновлення.
    """

    def __init__(self, db: Session, changed_by: str = "USER"):
        """
        Ініціалізує сервіс.

        Args:
            db: Сесія бази даних
            changed_by: Ім'я користувача, який вносить зміни
        """
        self.db = db
        self.changed_by = changed_by

    def create_staff(self, staff_data: dict[str, Any]) -> Staff:
        """
        Створює новий запис співробітника з записом в історію.

        Args:
            staff_data: Словник з даними співробітника

        Returns:
            Створений об'єкт Staff

        Raises:
            ValidationError: Якщо дані некоректні
        """
        staff = Staff(**staff_data)

        # Валідація дати
        if staff.term_end <= staff.term_start:
            raise ValidationError("Дата закінчення контракту має бути пізніше за дату початку")

        self.db.add(staff)
        self.db.flush()  # Отримуємо ID

        # Записуємо в історію
        self._log_history(
            staff=staff,
            action_type=StaffActionType.CREATE,
            previous_values={},  # Для CREATE попередніх значень немає
            comment="Створено новий запис",
        )

        # Коміт буде виконаний в get_db_context()
        return staff

    def update_staff(self, staff: Staff, updates: dict[str, Any], comment: str | None = None) -> None:
        """
        Оновлює дані співробітника з записом в історію.

        Args:
            staff: Об'єкт Staff для оновлення
            updates: Словник з оновленнями
            comment: Опціональний коментар

        Raises:
            ValidationError: Якщо дані некоректні
        """
        # Зберігаємо старі значення
        previous_values = {}
        for key in updates:
            if hasattr(staff, key):
                old_value = getattr(staff, key)
                new_value = updates[key]
                if old_value != new_value:
                    previous_values[key] = str(old_value)

        if not previous_values:
            return  # Немає змін

        # Застосовуємо оновлення
        for key, value in updates.items():
            setattr(staff, key, value)

        # Валідація дати
        if staff.term_end <= staff.term_start:
            raise ValidationError("Дата закінчення контракту має бути пізніше за дату початку")

        # Записуємо в історію
        self._log_history(
            staff=staff,
            action_type=StaffActionType.UPDATE,
            previous_values=previous_values,
            comment=comment or f"Оновлено поля: {', '.join(previous_values.keys())}",
        )

        # Коміт буде виконаний в get_db_context()

    def deactivate_staff(self, staff: Staff, reason: str | None = None) -> None:
        """
        Деактивує співробітника (soft delete) з записом в історію.

        Args:
            staff: Об'єкт Staff для деактивації
            reason: Причина деактивації
        """
        previous_values = {"is_active": "True"}

        staff.is_active = False

        self._log_history(
            staff=staff,
            action_type=StaffActionType.DEACTIVATE,
            previous_values=previous_values,
            comment=reason or "Деактивовано запис",
        )

        # Коміт буде виконаний в get_db_context()

    def hard_delete_staff(self, staff: Staff) -> None:
        """
        Повністю видаляє співробітника з бази даних (hard delete).

        УВАГА: Ця дія незворотна - всі дані та історія будуть видалені.

        Args:
            staff: Об'єкт Staff для видалення
        """
        staff_id = staff.id
        self.db.delete(staff)
        # Коміт буде виконаний в get_db_context()

    def restore_staff(self, old_staff: Staff, new_data: dict[str, Any]) -> Staff:
        """
        Відновлює співробітника шляхом реактивації старого запису з новими даними.

        Args:
            old_staff: Старий (неактивний) запис Staff
            new_data: Нові дані для відновленого запису

        Returns:
            Відновлений об'єкт Staff (той самий old_staff, але оновлений)
        """
        # Перевіряємо, чи старий запис дійсно неактивний
        if old_staff.is_active:
            raise ValidationError("Неможливо відновити активний запис. Спочатку деактивуйте його.")

        # Зберігаємо старі значення для історії
        old_values = {}
        for key, new_value in new_data.items():
            if hasattr(old_staff, key):
                old_value = getattr(old_staff, key)
                if old_value != new_value:
                    old_values[key] = str(old_value)

        # Оновлюємо старий запис новими даними
        for key, value in new_data.items():
            setattr(old_staff, key, value)

        # Валідація дати
        if old_staff.term_end <= old_staff.term_start:
            raise ValidationError("Дата закінчення контракту має бути пізніше за дату початку")

        # Записуємо в історію
        self._log_history(
            staff=old_staff,
            action_type=StaffActionType.RESTORE,
            previous_values=old_values,
            comment="Відновлено запис з новими даними",
        )

        # Коміт буде виконаний в get_db_context()
        return old_staff

    def auto_deactivate_expired_contracts(self) -> int:
        """
        Автоматично деактивує співробітників з простроченими контрактами.

        Цей метод викликається при старті desktop додатку.

        Returns:
            Кількість деактивованих записів
        """
        today = date.today()

        # Знаходимо всі активні записи з простроченими контрактами
        expired_staff = self.db.query(Staff).filter(
            Staff.is_active == True,
            Staff.term_end < today,
        ).all()

        count = 0
        for staff in expired_staff:
            days_expired = (today - staff.term_end).days
            reason = f"Автоматична деактивація: контракт закінчився {days_expired} днів тому"

            self.deactivate_staff(staff, reason=reason)
            count += 1

        return count

    def get_staff_history(self, staff_id: int) -> list[StaffHistory]:
        """
        Отримує повну історію змін співробітника.

        Args:
            staff_id: ID співробітника

        Returns:
            Список записів StaffHistory, відсортованих за датою (новіші перші)
        """
        return (
            self.db.query(StaffHistory)
            .filter(StaffHistory.staff_id == staff_id)
            .order_by(StaffHistory.created_at.desc())
            .all()
        )

    def _log_history(
        self,
        staff: Staff,
        action_type: StaffActionType,
        previous_values: dict[str, Any],
        comment: str,
    ) -> None:
        """
        Записує подію в історію.

        Args:
            staff: Об'єкт Staff
            action_type: Тип дії
            previous_values: Старі значення змінених полів
            comment: Коментар
        """
        history = StaffHistory(
            staff_id=staff.id,
            action_type=action_type.value,
            previous_values=previous_values,
            changed_by=self.changed_by,
            comment=comment,
        )
        self.db.add(history)
