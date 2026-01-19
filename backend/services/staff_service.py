"""Сервіс управління співробітниками."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.models.document import Document
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
        from shared.enums import StaffPosition

        # Перевірка унікальності посади завідувача (можна тільки одного: завідувач або в.о.)
        head_positions = [
            StaffPosition.HEAD_OF_DEPARTMENT.value,
            "acting_head",
        ]
        if staff_data.get("position") in head_positions:
            existing_head = self.db.query(Staff).filter(
                Staff.position.in_(head_positions),
                Staff.is_active == True
            ).first()
            if existing_head:
                raise ValidationError(
                    f"Посада завідувача кафедри вже зайнята.\n\n"
                    f"Поточний: {existing_head.pib_nom} ({existing_head.position})\n"
                    "Спочатку деактивуйте або змініть посаду поточного запису."
                )

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
        from shared.enums import StaffPosition

        # Перевірка унікальності посади завідувача (якщо змінюється на завідувача)
        head_positions = [
            StaffPosition.HEAD_OF_DEPARTMENT.value,
            "acting_head",
        ]
        new_position = updates.get("position")
        if new_position in head_positions and staff.position not in head_positions:
            # Changing TO head position - check if one already exists
            existing_head = self.db.query(Staff).filter(
                Staff.position.in_(head_positions),
                Staff.is_active == True,
                Staff.id != staff.id
            ).first()
            if existing_head:
                raise ValidationError(
                    f"Посада завідувача кафедри вже зайнята.\n\n"
                    f"Поточний: {existing_head.pib_nom} ({existing_head.position})\n"
                    "Спочатку деактивуйте або змініть посаду поточного запису."
                )

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
        from backend.models.staff_history import StaffHistory
        from backend.models.document import Document
        from backend.models.attendance import Attendance
        from backend.models.schedule import AnnualSchedule

        staff_id = staff.id

        # Спочатку видаляємо всі залежні записи (на випадок, якщо CASCADE не працює)
        self.db.query(StaffHistory).filter(StaffHistory.staff_id == staff_id).delete()
        self.db.query(Document).filter(Document.staff_id == staff_id).delete()
        self.db.query(Attendance).filter(Attendance.staff_id == staff_id).delete()
        self.db.query(AnnualSchedule).filter(AnnualSchedule.staff_id == staff_id).delete()

        # Потім видаляємо сам запис
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
            Staff.term_end <= today,
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

    def process_term_extension(self, document: Document) -> None:
        """
        Processes a term extension document: updates contract end date 
        and reactivates staff if deactivated.
        
        Args:
            document: Term extension document
        """
        try:
            staff = document.staff
            if not staff:
                return

            updates = {}
            
            # Update term_end if document has valid date_end
            if document.date_end:
                updates["term_end"] = document.date_end

            # Reactivate if inactive
            if not staff.is_active:
                updates["is_active"] = True

            if updates:
                self.update_staff(
                    staff, 
                    updates, 
                    comment=f"Автоматичне оновлення через документ {document.doc_type.value} (ID: {document.id})"
                )
                
                import logging
                logging.info(f"Updated staff {staff.id} via term extension document {document.id}: {updates}")
                self.db.commit()
                
        except Exception as e:
            import logging
            import logging
            logging.error(f"Failed to handle term extension for document {document.id}: {e}")
            # Don't raise, just log

    def create_staff_from_document(self, document: Document):
        """
        Creates a new staff record from an employment document's staged data.
        Returns the created Staff object or None.
        """
        if not document.new_employee_data:
            import logging
            logging.warning(f"No new_employee_data in document {document.id}")
            return None

        try:
            from shared.enums import EmploymentType, WorkBasis, DocumentStatus
            from datetime import date, datetime

            data = document.new_employee_data
            
            # Map string values to enums
            employment_type_map = {
                "main": EmploymentType.MAIN,
                "external": EmploymentType.EXTERNAL,
                "internal": EmploymentType.INTERNAL,
            }
            work_basis_map = {
                "contract": WorkBasis.CONTRACT,
                "competitive": WorkBasis.COMPETITIVE,
                "statement": WorkBasis.STATEMENT,
            }

            # Get department from settings
            from backend.models.settings import SystemSettings
            department = SystemSettings.get_value(self.db, "dept_name", "") or "Кафедра"

            # Parse term_start and term_end from string format (DD.MM.YYYY)
            term_start_str = data.get("term_start", "")
            term_end_str = data.get("term_end", "")
            try:
                term_start = datetime.strptime(term_start_str, "%d.%m.%Y").date() if term_start_str else date.today()
                term_end = datetime.strptime(term_end_str, "%d.%m.%Y").date() if term_end_str else date.today()
            except ValueError:
                term_start = date.today()
                term_end = date.today()

            # Handle position being a list [Label, Value] or [Value, Label]
            # Based on error log: ['Старший викладач', 'senior_lecturer'] -> Label, Value
            position_raw = data.get("position", "")
            position = position_raw
            if isinstance(position_raw, list):
                if len(position_raw) > 1:
                    # Prefer the second item as it seems to be the enum value 'senior_lecturer'
                    position = position_raw[1]
                elif len(position_raw) > 0:
                    position = position_raw[0]
                else:
                    position = ""

            # Create staff data dict
            staff_data = {
                "pib_nom": data.get("pib_nom", ""),
                "rate": data.get("rate", 1.0),
                "position": position,
                "department": department,
                "employment_type": employment_type_map.get(
                    data.get("employment_type", "main"), EmploymentType.MAIN
                ),
                "work_basis": work_basis_map.get(
                    data.get("work_basis", "contract"), WorkBasis.CONTRACT
                ),
                "term_start": term_start,
                "term_end": term_end,
                "vacation_balance": data.get("vacation_balance", 0),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "is_active": True,
            }

            # Create staff using create_staff method (handles validation and history)
            staff = self.create_staff(staff_data)
            
            # Link document to new staff
            document.staff_id = staff.id
            document.new_employee_data = None  # Clear staged data
            document.status = DocumentStatus.PROCESSED
            document.blocked_reason = "Документ оброблено - створено запис співробітника"
            
            self.db.commit()
            return staff

        except Exception as e:
            import logging
            logging.error(f"Failed to create staff from document {document.id}: {e}")
            self.db.rollback()
            raise e
