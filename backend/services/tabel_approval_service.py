"""Сервіс для управління погодженням табелів."""

import calendar
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.tabel_approval import TabelApproval
from backend.models.attendance import Attendance


class TabelApprovalService:
    """Сервіс для управління погодженням табелів."""

    def __init__(self, db: Session):
        """
        Ініціалізує сервіс.

        Args:
            db: Сесія бази даних
        """
        self.db = db

    def is_month_locked(self, month: int, year: int) -> bool:
        """
        Перевіряє, чи заблоковано місяць для редагування.

        Month M locks at M+1 00:00:00 (e.g., January locks at Feb 1, 2026 00:00:00).
        This is automatic based on current date.

        Args:
            month: Місяць (1-12)
            year: Рік

        Returns:
            bool: True якщо місяць заблоковано
        """
        from datetime import datetime, time

        # Calculate when this month should lock (1st of next month at 00:00:00)
        if month == 12:
            lock_month = 1
            lock_year = year + 1
        else:
            lock_month = month + 1
            lock_year = year

        lock_datetime = datetime.combine(date(lock_year, lock_month, 1), time.min)

        # Month is locked if we're past the lock time
        if datetime.utcnow() >= lock_datetime:
            return True

        # Check for manual approval
        approval = (
            self.db.query(TabelApproval)
            .filter(
                TabelApproval.month == month,
                TabelApproval.year == year,
                TabelApproval.is_correction == False,
                TabelApproval.is_approved == True,
            )
            .first()
        )

        return approval is not None

    def get_locked_months(self) -> list[tuple[int, int]]:
        """
        Отримує список заблокованих місяців.

        Returns:
            list[tuple]: Список кортежів (місяць, рік) для заблокованих місяців
        """
        approvals = (
            self.db.query(TabelApproval)
            .filter(
                TabelApproval.is_correction == False, TabelApproval.is_approved == True
            )
            .all()
        )
        return [(a.month, a.year) for a in approvals]

    def can_edit_attendance(
        self, staff_id: int, attendance_date: date
    ) -> tuple[bool, str]:
        """
        Перевіряє, чи можна редагувати відвідуваність на вказану дату.

        Args:
            staff_id: ID працівника
            attendance_date: Дата запису відвідуваності

        Returns:
            tuple[bool, str]: (дозволено, причина якщо заборонено)
        """
        month = attendance_date.month
        year = attendance_date.year

        if self.is_month_locked(month, year):
            return (
                False,
                "Цей місяць вже погоджено з кадрами. Зміни будуть внесені в корегуючий табель.",
            )

        return True, ""

    def get_correction_months(self) -> list[dict]:
        """
        Отримує список місяців з корегуючими табелями.

        Returns correction tabs grouped by (correction_month, correction_year).
        Each correction tab shows all corrections for that month.
        Max 4 correction tabs at a time (newest first).

        Returns:
            list[dict]: Список словників з ключами correction_month, correction_year
        """
        from datetime import datetime, date

        # Get all locked months (month M is locked at M+1 00:00:00)
        today = date.today()
        locked_months = []

        # Check last 12 months for locked months
        for month_offset in range(0, 12):
            check_month = today.month - month_offset
            check_year = today.year

            while check_month <= 0:
                check_month += 12
                check_year -= 1

            if self.is_month_locked(check_month, check_year):
                locked_months.append((check_month, check_year))

        # Get correction approval records for locked months
        correction_months = {}
        for lock_month, lock_year in locked_months:
            # Get all corrections for this locked month
            corrections = (
                self.db.query(TabelApproval)
                .filter(
                    TabelApproval.is_correction == True,
                    TabelApproval.correction_month == lock_month,
                    TabelApproval.correction_year == lock_year,
                )
                .all()
            )

            if corrections:
                # Get max sequence for this month
                max_seq = max(c.correction_sequence for c in corrections)
                correction_months[(lock_month, lock_year)] = {
                    "correction_month": lock_month,
                    "correction_year": lock_year,
                    "correction_sequence": max_seq,
                    "is_approved": any(c.is_approved for c in corrections),
                    "has_corrections": True,
                }

        # Convert to list and sort by date (newest first), limit to 4
        result = sorted(
            correction_months.values(),
            key=lambda x: (x["correction_year"], x["correction_month"]),
            reverse=True,
        )
        return result[:4]

    def is_correction_locked(
        self, correction_month: int, correction_year: int, correction_sequence: int
    ) -> bool:
        """
        Checks if a specific correction sequence is locked (approved).

        Args:
            correction_month: The month being corrected
            correction_year: The year being corrected
            correction_sequence: The sequence number of the correction

        Returns:
            bool: True if the correction sequence is approved, False otherwise
        """
        approval = (
            self.db.query(TabelApproval)
            .filter(
                TabelApproval.month == correction_month,
                TabelApproval.year == correction_year,
                TabelApproval.is_correction == True,
                TabelApproval.correction_sequence == correction_sequence,
                TabelApproval.is_approved == True,
            )
            .first()
        )

        return approval is not None

    def get_or_create_correction_sequence(
        self, correction_month: int, correction_year: int, create_if_needed: bool = True
    ) -> int:
        """
        Отримує наступний номер послідовності для корекції місяця.
        Якщо всі корекції затверджені, створює новий TabelApproval запис.

        Args:
            correction_month: Місяць що коригується
            correction_year: Рік що коригується
            create_if_needed: Якщо True, створює TabelApproval для нової послідовності

        Returns:
            int: Номер послідовності для нової корекції
        """
        # Find existing corrections for this month/year
        existing = (
            self.db.query(TabelApproval)
            .filter(
                TabelApproval.correction_month == correction_month,
                TabelApproval.correction_year == correction_year,
                TabelApproval.is_correction == True,
            )
            .order_by(TabelApproval.correction_sequence.desc())
            .all()
        )

        if not existing:
            # No corrections exist yet - create first one if requested
            if create_if_needed:
                new_approval = TabelApproval(
                    month=correction_month,
                    year=correction_year,
                    is_correction=True,
                    correction_month=correction_month,
                    correction_year=correction_year,
                    correction_sequence=1,
                    is_approved=False,
                    generated_at=datetime.utcnow(),
                )
                self.db.add(new_approval)
                self.db.flush()
            return 1

        # Check the latest correction
        latest = existing[0]

        # If latest correction is NOT approved, we can reuse it
        if not latest.is_approved:
            return latest.correction_sequence

        # Otherwise, start a new sequence - and CREATE the approval record
        new_sequence = latest.correction_sequence + 1
        if create_if_needed:
            new_approval = TabelApproval(
                month=correction_month,
                year=correction_year,
                is_correction=True,
                correction_month=correction_month,
                correction_year=correction_year,
                correction_sequence=new_sequence,
                is_approved=False,
                generated_at=datetime.utcnow(),
            )
            self.db.add(new_approval)
            self.db.flush()
        return new_sequence

    def record_generation(
        self,
        month: int,
        year: int,
        is_correction: bool = False,
        correction_month: Optional[int] = None,
        correction_year: Optional[int] = None,
        correction_sequence: int = 1,
    ) -> TabelApproval:
        """
        Реєструє факт генерації табеля.

        Args:
            month: Місяць табеля
            year: Рік табеля
            is_correction: Чи є корегуючим табелем
            correction_month: Місяць, що коригується (для корегуючих)
            correction_year: Рік, що коригується (для корегуючих)
            correction_sequence: Номер послідовності корекції

        Returns:
            TabelApproval: Створений або оновлений запис
        """
        # Build query with optional correction month/year/sequence filters
        query = self.db.query(TabelApproval).filter(
            TabelApproval.month == month,
            TabelApproval.year == year,
            TabelApproval.is_correction == is_correction,
        )

        if is_correction:
            query = query.filter(
                TabelApproval.correction_month == correction_month,
                TabelApproval.correction_year == correction_year,
                TabelApproval.correction_sequence == correction_sequence,
            )
        else:
            # For non-correction, match NULL correction_month/year/sequence
            query = query.filter(
                TabelApproval.correction_month.is_(None),
                TabelApproval.correction_year.is_(None),
                TabelApproval.correction_sequence == 1,
            )

        approval = query.first()

        if approval:
            # Update generated timestamp if not approved yet
            if not approval.is_approved:
                approval.generated_at = datetime.utcnow()
        else:
            approval = TabelApproval(
                month=month,
                year=year,
                is_correction=is_correction,
                correction_month=correction_month,
                correction_year=correction_year,
                correction_sequence=correction_sequence,
                is_approved=False,
                generated_at=datetime.utcnow(),
            )
            self.db.add(approval)

        self.db.commit()
        return approval

    def delete_correction(self, correction_month: int, correction_year: int) -> bool:
        """
        Видаляє запис про корегуючий табель.

        Args:
            correction_month: Місяць корекції
            correction_year: Рік корекції

        Returns:
            bool: True якщо видалено успішно
        """
        corrections = (
            self.db.query(TabelApproval)
            .filter(
                TabelApproval.is_correction == True,
                TabelApproval.correction_month == correction_month,
                TabelApproval.correction_year == correction_year,
            )
            .all()
        )

        if not corrections:
            return False

        for c in corrections:
            self.db.delete(c)

        self.db.commit()
        return True

    def confirm_approval(
        self,
        month: int,
        year: int,
        is_correction: bool = False,
        correction_month: int | None = None,
        correction_year: int | None = None,
        correction_sequence: int = 1,
        user: str = "user",
    ) -> TabelApproval:
        """
        Підтверджує погодження табеля з кадровою службою.

        Args:
            month: Місяць табеля
            year: Рік табеля
            is_correction: Чи є корегуючим табелем
            correction_month: Місяць що коригується (для корегуючих)
            correction_year: Рік що коригується (для корегуючих)
            correction_sequence: Номер послідовності корекції
            user: Логін користувача, що підтвердив

        Returns:
            TabelApproval: Оновлений запис

        Raises:
            ValueError: Якщо табель вже погоджено
        """
        query = self.db.query(TabelApproval).filter(
            TabelApproval.month == month,
            TabelApproval.year == year,
            TabelApproval.is_correction == is_correction,
        )

        if is_correction:
            query = query.filter(
                TabelApproval.correction_month == correction_month,
                TabelApproval.correction_year == correction_year,
                TabelApproval.correction_sequence == correction_sequence,
            )
        else:
            # For non-correction, ensure we match the main record (NULL corrections)
            query = query.filter(
                TabelApproval.correction_month.is_(None),
                TabelApproval.correction_year.is_(None),
                TabelApproval.correction_sequence == 1,
            )

        approval = query.first()

        # Check if already approved
        if approval and approval.is_approved:
            raise ValueError("Табель вже погоджено")

        if not approval:
            raise ValueError("Табель не знайдено. Спочатку згенеруйте табель.")

        approval.is_approved = True
        approval.approved_at = datetime.utcnow()
        approval.approved_by = user
        self.db.commit()

        return approval

    def should_show_warning(self, month: int, year: int) -> bool:
        """
        Перевіряє, чи потрібно показувати попередження про необхідність згенерувати табель.

        Показується з 1 по 10 число місяця, якщо табель ще не згенеровано.

        Args:
            month: Місяць
            year: Рік

        Returns:
            bool: True якщо потрібно показати попередження
        """
        today = date.today()

        # Check if we're in the same month/year and before 10th
        if today.month != month or today.year != year:
            return False

        if today.day > 10:
            return False

        # Check if tabel has been generated
        approval = (
            self.db.query(TabelApproval)
            .filter(
                TabelApproval.month == month,
                TabelApproval.year == year,
                TabelApproval.is_correction == False,
            )
            .first()
        )

        # Show warning if not generated yet
        return approval is None

    def get_approval_status(
        self,
        month: int,
        year: int,
        is_correction: bool = False,
        correction_month: int | None = None,
        correction_year: int | None = None,
    ) -> Optional[dict]:
        """
        Отримує статус погодження для табеля.

        Args:
            month: Місяць
            year: Рік
            is_correction: Чи є корегуючим табелем
            correction_month: Місяць що коригується (для корегуючих)
            correction_year: Рік що коригується (для корегуючих)

        Returns:
            dict або None: Статус погодження або None якщо не знайдено
        """
        query = self.db.query(TabelApproval).filter(
            TabelApproval.month == month,
            TabelApproval.year == year,
            TabelApproval.is_correction == is_correction,
        )

        if is_correction:
            query = query.filter(
                TabelApproval.correction_month == correction_month,
                TabelApproval.correction_year == correction_year,
            )
        else:
            # For non-correction, ensure we match the main record
            query = query.filter(
                TabelApproval.correction_month.is_(None),
                TabelApproval.correction_year.is_(None),
            )

        approval = query.first()

        if not approval:
            return None

        return {
            "is_generated": approval.generated_at is not None,
            "is_approved": approval.is_approved,
            "generated_at": approval.generated_at,
            "approved_at": approval.approved_at,
            "approved_by": approval.approved_by,
        }
