"""Сервіс для управління записами відвідуваності працівників."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.attendance import Attendance, WEEKEND_DAYS


class AttendanceService:
    """Сервіс для CRUD операцій з записами відвідуваності."""

    def __init__(self, db: Session):
        """
        Ініціалізує сервіс.

        Args:
            db: Сесія бази даних
        """
        self.db = db

    def create_attendance(
        self,
        staff_id: int,
        attendance_date: date,
        code: str,
        hours: Decimal = Decimal("8.0"),
        notes: Optional[str] = None,
    ) -> Attendance:
        """
        Створює запис відвідуваності для одного дня.

        Args:
            staff_id: ID працівника
            attendance_date: Дата
            code: Літерний код відвідуваності
            hours: Кількість годин
            notes: Примітки

        Returns:
            Attendance: Створений запис
        """
        # Перевіряємо чи вже існує запис на цю дату
        existing = self.db.query(Attendance).filter(
            Attendance.staff_id == staff_id,
            Attendance.date == attendance_date,
        ).first()

        if existing:
            # Оновлюємо існуючий запис
            existing.code = code
            existing.hours = hours
            existing.notes = notes
            self.db.commit()
            return existing

        # Створюємо новий запис
        attendance = Attendance(
            staff_id=staff_id,
            date=attendance_date,
            code=code,
            hours=hours,
            notes=notes,
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
    ) -> Attendance:
        """
        Створює запис відвідуваності для діапазону дат (один запис з date_end).

        Args:
            staff_id: ID працівника
            start_date: Початкова дата
            end_date: Кінцева дата
            code: Літерний код відвідуваності
            hours: Кількість годин за день
            notes: Примітки
            skip_weekends: Чи пропускати вихідні дні (для візуалізації, не впливає на зберігання)

        Returns:
            Attendance: Створений запис з діапазоном дат
        """
        # Видаляємо існуючі записи для цього діапазону
        self.delete_attendance_range(staff_id, start_date, end_date)

        # Створюємо один запис з date_end
        attendance = Attendance(
            staff_id=staff_id,
            date=start_date,
            date_end=end_date,
            code=code,
            hours=hours,
            notes=notes,
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
            notes: Нові примітки (опціонально)

        Returns:
            Attendance | None: Оновлений запис або None
        """
        attendance = self.get_attendance_by_id(attendance_id)
        if not attendance:
            return None

        if code is not None:
            attendance.code = code
        if hours is not None:
            attendance.hours = hours
        if notes is not None:
            attendance.notes = notes

        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def delete_attendance(self, attendance_id: int) -> bool:
        """
        Видаляє запис відвідуваності.

        Args:
            attendance_id: ID запису

        Returns:
            bool: True якщо видалено, False якщо не знайдено
        """
        attendance = self.get_attendance_by_id(attendance_id)
        if not attendance:
            return False

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
        """
        deleted = self.db.query(Attendance).filter(
            Attendance.staff_id == staff_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        ).delete()
        self.db.commit()
        return deleted
