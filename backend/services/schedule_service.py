"""Сервіс для управління річним графіком відпусток."""

import datetime
from collections import defaultdict
from typing import List

from sqlalchemy.orm import Session

from backend.models.schedule import AnnualSchedule
from backend.models.staff import Staff
from backend.services.validation_service import ValidationService
from shared.enums import EmploymentType


class ScheduleService:
    """
    Сервіс для управління річним графіком відпусток.

    Відповідає за автоматичний розподіл відпусток,
    валідацію графіку та планування.
    """

    def __init__(self, db: Session):
        """
        Ініціалізує сервіс.

        Args:
            db: Сесія бази даних
        """
        self.db = db
        self.validation = ValidationService()


    def get_staff_for_schedule(self, year: int) -> List[Staff]:
        """
        Отримує список співробітників для включення в графік.

        Включає:
        - Співробітників з ставкою 1.0
        - Внутрішніх сумісників
        - Всіх активних співробітників

        Args:
            year: Рік графіку

        Returns:
            Список співробітників
        """
        # Отримуємо всіх активних співробітників
        staff_list = (
            self.db.query(Staff)
            .filter(Staff.is_active == True)
            .order_by(Staff.pib_nom)
            .all()
        )

        # Фільтруємо за правилами
        result = []
        for staff in staff_list:
            # Включаємо: повна ставка OR внутрішній сумісник
            if staff.rate >= 1.0 or staff.employment_type == EmploymentType.INTERNAL:
                result.append(staff)

        return result

    def auto_distribute(
        self,
        year: int,
        staff_list: List[Staff] | None = None
    ) -> dict[str, any]:
        """
        Автоматично розподіляє відпустки по місяцях.

        Алгоритм:
        1. Рівномірно розподіляє по місяцях
        2. Уникає вихідних днів
        3. Уникає перетинів відпусток
        4. Перевіряє termin дії контракту

        Args:
            year: Рік планування
            staff_list: Список співробітників (якщо None - отримує автоматично)

        Returns:
            Словник з результатом:
            - entries_created: кількість створених записів
            - warnings: список попереджень
        """
        if staff_list is None:
            staff_list = self.get_staff_for_schedule(year)

        entries_created = 0
        warnings = []

        # Розподіляємо співробітників по місяцях
        # Простий алгоритм: рівномірно розподіляємо 2-тижневі відпустки
        # по всіх місяців, уникаючи пікових періодів (липень, серпень)

        # Визначаємо пріоритетні місяці (червень-вересень для відпусток)
        vacation_months = [6, 7, 8, 9]  # червень - вересень

        # Рахуємо скільки людей на кожен місяць
        month_counts = defaultdict(int)
        staff_month_map = {}  # staff_id -> month

        for i, staff in enumerate(staff_list):
            # Перевіряємо чи вже є запис
            existing = (
                self.db.query(AnnualSchedule)
                .filter(
                    AnnualSchedule.year == year,
                    AnnualSchedule.staff_id == staff.id,
                )
                .first()
            )
            if existing:
                warnings.append(f"{staff.pib_nom} - запис вже існує")
                continue

            # Вибираємо місяць з найменшою кількістю
            month = self._select_month_with_least_staff(vacation_months, month_counts)

            # Знаходимо перший понеділок місяця
            start_date = self._find_first_monday(year, month)

            # Розраховуємо кінець (14 днів = 2 тижні)
            end_date = start_date + datetime.timedelta(days=13)

            # Перевіряємо чи не виходить за межі контракту
            if start_date > staff.term_end:
                warnings.append(f"{staff.pib_nom} - контракт закінчується до відпустки")
                continue

            # Коригуємо якщо end_date > term_end
            if end_date > staff.term_end:
                end_date = staff.term_end
                days = (end_date - start_date).days + 1
                if days < 7:  # Менше тижня
                    warnings.append(f"{staff.pib_nom} - замало днів до кінця контракту")
                    continue

            # Перевіряємо перетини з існуючими записами
            if self._check_overlaps(staff.id, start_date, end_date):
                warnings.append(f"{staff.pib_nom} - перетин з існуючою відпусткою")
                continue

            # Створюємо запис
            entry = AnnualSchedule(
                year=year,
                staff_id=staff.id,
                planned_start=start_date,
                planned_end=end_date,
            )
            self.db.add(entry)
            month_counts[month] += 1
            entries_created += 1

        self.db.commit()

        return {
            "entries_created": entries_created,
            "warnings": warnings,
        }

    def _select_month_with_least_staff(
        self,
        months: List[int],
        month_counts: dict[int, int]
    ) -> int:
        """
        Вибирає місяць з найменшою кількістю призначених співробітників.

        Args:
            months: Список місяців для вибору
            month_counts: Поточні лічильники по місяцях

        Returns:
            Номер місяця (1-12)
        """
        return min(months, key=lambda m: month_counts[m])

    def _find_first_monday(self, year: int, month: int) -> datetime.date:
        """
        Знаходить перший понеділок в місяці.

        Args:
            year: Рік
            month: Місяць

        Returns:
            Дата першого понеділка
        """
        start_date = datetime.date(year, month, 1)

        # Якщо 1 число - понеділок, повертаємо його
        if start_date.weekday() == 0:
            return start_date

        # Інакше шукаємо перший понеділок
        while start_date.weekday() != 0:
            start_date += datetime.timedelta(days=1)

        return start_date

    def _check_overlaps(
        self,
        staff_id: int,
        start_date: datetime.date,
        end_date: datetime.date
    ) -> bool:
        """
        Перевіряє чи перетинається нова відпустка з існуючими.

        Args:
            staff_id: ID співробітника
            start_date: Початок нової відпустки
            end_date: Кінець нової відпустки

        Returns:
            True якщо є перетин, False якщо ні
        """
        existing = (
            self.db.query(AnnualSchedule)
            .filter(AnnualSchedule.staff_id == staff_id)
            .all()
        )

        for entry in existing:
            # Перевіряємо перетин відрізків
            if not (end_date < entry.planned_start or start_date > entry.planned_end):
                return True

        return False

    def validate_schedule_entry(
        self,
        staff_id: int,
        planned_start: datetime.date,
        planned_end: datetime.date
    ) -> tuple[bool, List[str]]:
        """
        Валідає запис графіку.

        Args:
            staff_id: ID співробітника
            planned_start: Плановий початок
            planned_end: Плановий кінець

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Отримуємо співробітника
        staff = self.db.query(Staff).filter(Staff.id == staff_id).first()
        if not staff:
            errors.append("Співробітника не знайдено")
            return False, errors

        # Валідація дат
        date_errors = self.validation.validate_vacation_dates(
            planned_start,
            planned_end,
            staff
        )
        errors.extend(date_errors)

        # Перевірка на перетини
        if self._check_overlaps(staff_id, planned_start, planned_end):
            errors.append("Перетин з існуючою відпусткою")

        # Перевірка termin дії контракту
        if planned_start > staff.term_end:
            errors.append("Початок відпустки перевищує termin дії контракту")

        # Тривалість (мінімум 7 днів)
        duration = (planned_end - planned_start).days + 1
        if duration < 7:
            errors.append("Відпустка має бути не менше 7 днів")

        return len(errors) == 0, errors

    def get_schedule_statistics(self, year: int) -> dict:
        """
        Отримує статистику по графіку на рік.

        Args:
            year: Рік

        Returns:
            Словник зі статистикою
        """
        entries = (
            self.db.query(AnnualSchedule)
            .filter(AnnualSchedule.year == year)
            .all()
        )

        total = len(entries)
        used = sum(1 for e in entries if e.is_used)
        unused = total - used

        # Розподіл по місяцях
        monthly_distribution = defaultdict(int)
        for entry in entries:
            month = entry.planned_start.month
            monthly_distribution[month] += 1

        return {
            "total": total,
            "used": used,
            "unused": unused,
            "monthly_distribution": dict(monthly_distribution),
        }
