"""Сервіс для управління записами відвідуваності працівників."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.attendance import Attendance, WEEKEND_DAYS
from backend.services.tabel_approval_service import TabelApprovalService


class AttendanceConflictError(Exception):
    """Виключення при конфлікті дат у записах відвідуваності."""
    pass


class AttendanceLockedError(Exception):
    """Виключення при спробі змінити заблокований (затверджений) запис."""
    pass


class AttendanceService:
    """Сервіс для CRUD операцій з записами відвідуваності."""

    def __init__(self, db: Session):
        """
        Ініціалізує сервіс.

        Args:
            db: Сесія бази даних
        """
        self.db = db
        self.approval_service = TabelApprovalService(db)

    def check_locking(
        self,
        check_date: date,
        is_correction: bool = False,
        correction_month: Optional[int] = None,
        correction_year: Optional[int] = None,
        correction_sequence: Optional[int] = None,
    ):
        """
        Перевіряє, чи заблокована дата/період для змін.
         Raises AttendanceLockedError if locked.
        """
        if is_correction:
            # Check specific correction sequence
            if correction_month is None or correction_year is None or correction_sequence is None:
                # Should not happen for correction records, but safety check
                return

            if self.approval_service.is_correction_locked(correction_month, correction_year, correction_sequence):
                 raise AttendanceLockedError(
                    f"Коригуючий табель за {correction_month:02}.{correction_year} (версія {correction_sequence}) вже затверджено. Зміни заборонено."
                )
        else:
            # Check regular month
            if self.approval_service.is_month_locked(check_date.month, check_date.year):
                raise AttendanceLockedError(
                    f"Табель за {check_date.strftime('%m.%Y')} вже затверджено. "
                    f"Для внесення змін створіть коригуючий табель."
                )

    def check_conflicts(
        self,
        staff_id: int,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> list[Attendance]:
        """
        Перевіряє наявність конфліктуючих записів для вказаного періоду.

        Args:
            staff_id: ID працівника
            start_date: Початкова дата
            end_date: Кінцева дата (якщо None, перевіряється лише start_date)

        Returns:
            list[Attendance]: Список конфліктуючих записів
        """
        target_date = end_date or start_date

        # Знаходимо всі записи працівника
        all_records = self.db.query(Attendance).filter(
            Attendance.staff_id == staff_id,
        ).all()

        # Фільтруємо записи що перетинаються з вказаним періодом
        result = []
        for record in all_records:
            record_end = record.date_end or record.date
            # Перевіряємо чи є перетин періодів
            # Два періоди перетинаються якщо: A.start <= B.end AND A.end >= B.start
            if not (record_end < start_date or record.date > target_date):
                result.append(record)

        return result

    def get_conflicting_records_info(self, staff_id: int, start_date: date, end_date: Optional[date] = None) -> list[dict]:
        """
        Повертає інформацію про конфліктуючі записи у зручному форматі.

        Args:
            staff_id: ID працівника
            start_date: Початкова дата
            end_date: Кінцева дата

        Returns:
            list[dict]: Список словників з інформацією про конфлікти
        """
        conflicts = self.check_conflicts(staff_id, start_date, end_date)
        result = []
        for record in conflicts:
            if record.date_end:
                date_range = f"{record.date.strftime('%d.%m.%Y')} - {record.date_end.strftime('%d.%m.%Y')}"
            else:
                date_range = record.date.strftime('%d.%m.%Y')
            result.append({
                "id": record.id,
                "date_range": date_range,
                "code": record.code,
                "notes": record.notes,
            })
        return result

    def create_attendance(
        self,
        staff_id: int,
        attendance_date: date,
        code: str,
        hours: Decimal = Decimal("8.0"),
        notes: Optional[str] = None,
        is_correction: bool = False,
        correction_month: Optional[int] = None,
        correction_year: Optional[int] = None,
        correction_sequence: int = 1,
    ) -> Attendance:
        """
        Створює запис відвідуваності для одного дня.

        Args:
            staff_id: ID працівника
            attendance_date: Дата
            code: Літерний код відвідуваності
            hours: Кількість годин
            notes: Примечания
            is_correction: Чи є це записом корегуючого табеля
            correction_month: Місяць, що коригується
            correction_year: Рік, що коригується
            correction_sequence: Номер послідовності корекції

        Returns:
            Attendance: Створений запис

        Raises:
            AttendanceConflictError: Якщо є конфліктуючі записи
            AttendanceLockedError: Якщо місяць/корекція затверджені
        """
        # Перевіряємо блокування
        self.check_locking(
            attendance_date,
            is_correction,
            correction_month,
            correction_year,
            correction_sequence
        )

        # Перевіряємо конфлікти з існуючими записами відвідуваності
        conflicts = self.check_conflicts(staff_id, attendance_date)
        if conflicts:
            conflict_info = self.get_conflicting_records_info(staff_id, attendance_date)
            conflict_str = ", ".join([c["date_range"] for c in conflict_info])
            raise AttendanceConflictError(
                f"На період {attendance_date.strftime('%d.%m.%Y')} вже є записи: {conflict_str}. "
                f"Видаліть конфліктуючі записи перед додаванням нових."
            )

        # Перевіряємо конфлікти з документами відпусток
        if code == "Р" and not is_correction:
            from backend.services.validation_service import ValidationService
            ValidationService.validate_no_vacation_overlap(attendance_date, staff_id, self.db)

        # Створюємо новий запис
        attendance = Attendance(
            staff_id=staff_id,
            date=attendance_date,
            code=code,
            hours=hours,
            notes=notes,
            is_correction=is_correction,
            correction_month=correction_month,
            correction_year=correction_year,
            correction_sequence=correction_sequence,
        )
        self.db.add(attendance)
        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def create_attendance_range(
        self,
        staff_id: int,
        start_date: date,
        end_date: date,
        code: str,
        hours: Decimal = Decimal("8.0"),
        notes: Optional[str] = None,
        skip_weekends: bool = True,
        is_correction: bool = False,
        correction_month: Optional[int] = None,
        correction_year: Optional[int] = None,
        correction_sequence: int = 1,
    ) -> Attendance:
        """
        Створює запис відвідуваності для діапазону дат (один запис з date_end).

        Args:
            staff_id: ID працівника
            start_date: Початкова дата
            end_date: Кінцева дата
            code: Літерний код відвідуваності
            hours: Кількість годин за день
            notes: Примечания
            skip_weekends: Чи пропускати вихідні дні (для візуалізації, не впливає на зберігання)
            is_correction: Чи є це записом корегуючого табеля
            correction_month: Місяць, що коригується
            correction_year: Рік, що коригується
            correction_sequence: Номер послідовності корекції

        Returns:
            Attendance: Створений запис з діапазоном дат

        Raises:
            AttendanceConflictError: Якщо є конфліктуючі записи
            AttendanceLockedError: Якщо місяць/корекція затверджені
        """
        # Перевіряємо блокування
        self.check_locking(
            start_date,
            is_correction,
            correction_month,
            correction_year,
            correction_sequence
        )

        # Перевіряємо на конфлікти
        conflicts = self.check_conflicts(staff_id, start_date, end_date)
        if conflicts:
            conflict_info = self.get_conflicting_records_info(staff_id, start_date, end_date)
            conflict_str = ", ".join([c["date_range"] for c in conflict_info])
            raise AttendanceConflictError(
                f"На період {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')} вже є записи: {conflict_str}. "
                f"Видаліть конфліктуючі записи перед додаванням нових."
            )

        # Перевіряємо конфлікти з документами відпусток
        if code == "Р" and not is_correction:
            from backend.services.validation_service import ValidationService
            # Перевіряємо кожен день у діапазоні
            current = start_date
            while current <= end_date:
                ValidationService.validate_no_vacation_overlap(current, staff_id, self.db)
                current += timedelta(days=1)

        # Створюємо один запис з date_end
        attendance = Attendance(
            staff_id=staff_id,
            date=start_date,
            date_end=end_date,
            code=code,
            hours=hours,
            notes=notes,
            is_correction=is_correction,
            correction_month=correction_month,
            correction_year=correction_year,
            correction_sequence=correction_sequence,
        )
        self.db.add(attendance)
        self.db.commit()
        self.db.refresh(attendance)
        return attendance


    def get_staff_attendance(
        self,
        staff_id: int,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> list[Attendance]:
        """
        Отримує записи відвідуваності працівника.

        Args:
            staff_id: ID працівника
            month: Місяць (опціонально)
            year: Рік (опціонально)

        Returns:
            list[Attendance]: Список записів
        """
        query = self.db.query(Attendance).filter(
            Attendance.staff_id == staff_id
        )

        if month and year:
            from calendar import monthrange
            _, days_in_month = monthrange(year, month)
            month_start = date(year, month, 1)
            month_end = date(year, month, days_in_month)
            query = query.filter(
                Attendance.date >= month_start,
                Attendance.date <= month_end,
            )

        return query.order_by(Attendance.date.desc()).all()

    def get_attendance_by_id(self, attendance_id: int) -> Optional[Attendance]:
        """
        Отримує запис відвідуваності за ID.

        Args:
            attendance_id: ID запису

        Returns:
            Attendance | None: Запис або None
        """
        return self.db.query(Attendance).filter(
            Attendance.id == attendance_id
        ).first()

    def update_attendance(
        self,
        attendance_id: int,
        code: Optional[str] = None,
        hours: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> Optional[Attendance]:
        """
        Оновлює запис відвідуваності.

        Args:
            attendance_id: ID запису
            code: Новий код (опціонально)
            hours: Нова кількість годин (опціонально)
            notes: Нові примечания (опціонально)

        Returns:
            Attendance | None: Оновлений запис або None

        Raises:
            AttendanceLockedError: Якщо запис заблоковано
        """
        attendance = self.get_attendance_by_id(attendance_id)
        if not attendance:
            return None

        # Check if EXISTING record is locked
        self.check_locking(
            attendance.date,
            attendance.is_correction,
            attendance.correction_month,
            attendance.correction_year,
            attendance.correction_sequence
        )

        if code is not None:
            attendance.code = code
        if hours is not None:
            attendance.hours = hours
        if notes is not None:
            attendance.notes = notes

        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def delete_attendance(self, attendance_id: int, notes: str | None = None) -> bool:
        """
        Видаляє запис відвідуваності.

        Args:
            attendance_id: ID запису
            notes: Коментар причини видалення

        Returns:
            bool: True якщо видалено, False якщо не знайдено

        Raises:
            AttendanceLockedError: Якщо запис заблоковано
        """
        attendance = self.get_attendance_by_id(attendance_id)
        if not attendance:
            return False

        # Check locking before delete
        self.check_locking(
            attendance.date,
            attendance.is_correction,
            attendance.correction_month,
            attendance.correction_year,
            attendance.correction_sequence
        )

        # Зберігаємо коментар перед видаленням
        if notes:
            attendance.deletion_notes = notes

        self.db.delete(attendance)
        self.db.commit()
        return True

    def delete_attendance_range(
        self,
        staff_id: int,
        start_date: date,
        end_date: date,
    ) -> int:
        """
        Видаляє записи відвідуваності за діапазоном дат.

        Args:
            staff_id: ID працівника
            start_date: Початкова дата
            end_date: Кінцева дата

        Returns:
            int: Кількість видалених записів

        Raises:
            AttendanceLockedError: Якщо хоча б один запис у діапазоні заблоковано
        """
        # Спочатку знаходимо що видалятимемо, щоб перевірити блокування
        to_delete = self.db.query(Attendance).filter(
            Attendance.staff_id == staff_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        ).all()

        for record in to_delete:
             self.check_locking(
                record.date,
                record.is_correction,
                record.correction_month,
                record.correction_year,
                record.correction_sequence
            )

        deleted = self.db.query(Attendance).filter(
            Attendance.staff_id == staff_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        ).delete()
        self.db.commit()
        return deleted
