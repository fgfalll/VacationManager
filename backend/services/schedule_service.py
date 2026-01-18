"""Сервіс для управління річним графіком відпусток."""

import datetime
import random
from collections import defaultdict
from typing import List, Set, Tuple, Optional, Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from backend.models.schedule import AnnualSchedule
from backend.models.document import Document
from backend.models.staff import Staff
from backend.models.attendance import Attendance
from shared.enums import DocumentStatus, DocumentType
from backend.services.validation_service import ValidationService
from shared.enums import EmploymentType


@dataclass
class AutoDistributeSettings:
    """Налаштування для авторозподілу."""
    min_days_per_period: int = 7
    max_days_per_period: int = 14
    use_balance_days: bool = True
    custom_days: int = 24
    max_periods: int = 2
    use_all_balance: bool = True
    create_documents: bool = True
    doc_type: str = "vacation_main"
    all_year: bool = True
    summer_only: bool = False
    winter_only: bool = False
    skip_existing: bool = True
    random_distribution: bool = True


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

    def _is_weekend(self, d: datetime.date) -> bool:
        """Перевіряє чи є день вихідним."""
        return d.weekday() >= 5  # 5 = Saturday, 6 = Sunday

    def _get_booked_dates(self, staff: Staff) -> Set[datetime.date]:
        """
        Отримує всі заброньовані дати для співробітника.

        Включає:
        - Дати документів (на підписі, підписано, оброблено)
        - Дати відвідуваності (крім "Р" - присутність)
        """
        booked_dates = set()

        # Документи
        for doc in staff.documents:
            if doc.status in ('on_signature', 'signed', 'processed'):
                current = doc.date_start
                while current <= doc.date_end:
                    booked_dates.add(current)
                    current += datetime.timedelta(days=1)

        # Відвідуваність (крім "Р")
        atts = self.db.query(Attendance).filter(
            Attendance.staff_id == staff.id,
            Attendance.code != "Р"
        ).all()
        for att in atts:
            att_end = att.date_end or att.date
            current = att.date
            while current <= att_end:
                booked_dates.add(current)
                current += datetime.timedelta(days=1)

        return booked_dates

    def _get_valid_dates(
        self,
        staff: Staff,
        year: int,
        booked_dates: Set[datetime.date],
        all_year: bool = True,
        summer_only: bool = False,
        winter_only: bool = False
    ) -> List[datetime.date]:
        """
        Повертає список доступних дат для відпустки в році.

        Враховує:
        - Броньовані дати
        - Вихідні дні
        - Дати контракту
        - Фільтрація по місяцях
        """
        valid_dates = []

        year_start = datetime.date(year, 1, 1)
        year_end = datetime.date(year, 12, 31)

        # Обмежуємо датами контракту
        search_start = max(year_start, staff.term_start)
        search_end = min(year_end, staff.term_end)

        # Визначаємо дозволені місяці
        if summer_only:
            allowed_months = {6, 7, 8, 9}
        elif winter_only:
            allowed_months = {12, 1, 2}
        elif all_year:
            allowed_months = set(range(1, 13))
        else:
            allowed_months = set(range(1, 13))

        current = search_start
        while current <= search_end:
            # Перевіряємо: не вихідний, не заброньований, в дозволеному місяці
            if (
                not self._is_weekend(current)
                and current not in booked_dates
                and current.month in allowed_months
            ):
                valid_dates.append(current)
            current += datetime.timedelta(days=1)

        return valid_dates

    def _find_vacation_ranges(
        self,
        valid_dates: List[datetime.date],
        booked_dates: Set[datetime.date],
        days_needed: int,
        contract_end: datetime.date,
        shuffle: bool = True
    ) -> List[Tuple[datetime.date, datetime.date]]:
        """
        Знаходить можливі діапазони відпустки на N календарних днів.

        Правила:
        - Рахуємо календарні дні (включаючи вихідні)
        - Початок має бути робочим днем
        - Всі дати НЕ МОЖУТЬ бути заброньовані
        - Кінець НЕ МОЖЕ бути вихідним
        """
        if not valid_dates:
            return []

        if shuffle:
            dates_copy = valid_dates.copy()
            random.shuffle(dates_copy)
        else:
            dates_copy = valid_dates

        possible_ranges = []
        search_start = dates_copy[0]
        search_end = min(contract_end, search_start + datetime.timedelta(days=180))

        current = search_start
        while current <= search_end:
            # Пропускаємо вихідні та заброньовані як початок
            if not self._is_weekend(current) and current not in booked_dates:
                # Цільова кінцева дата (включаючи вихідні)
                target_end = current + datetime.timedelta(days=days_needed - 1)

                # Якщо target_end вихідний — зсуваємо на понеділок
                end = target_end
                while self._is_weekend(end):
                    end += datetime.timedelta(days=1)

                # Перевіряємо, що ВСІ дати в діапазоні не заброньовані
                all_available = True
                check_date = current
                while check_date <= end:
                    if check_date in booked_dates:
                        all_available = False
                        break
                    check_date += datetime.timedelta(days=1)

                if all_available and end <= contract_end:
                    possible_ranges.append((current, end))

            current += datetime.timedelta(days=1)

        return possible_ranges

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
            .options(joinedload(Staff.documents))
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
        staff_list: List[Staff] | None = None,
        settings: Optional[AutoDistributeSettings] = None
    ) -> dict[str, any]:
        """
        Автоматично розподіляє відпустки по всьому році.

        Алгоритм:
        1. Використовує логіку AutoDateRangeDialog
        2. Розподіляє по всьому року (не тільки літо)
        3. Розбиває баланс відпусток на періоди (10-14 днів)
        4. Створює AnnualSchedule + Document для кожного періоду
        5. Уникає заброньованих дат та вихідних
        6. Випадковий розподіл для різноманітності

        Args:
            year: Рік планування
            staff_list: Список співробітників (якщо None - отримує автоматично)
            settings: Налаштування авторозподілу

        Returns:
            Словник з результатом:
            - entries_created: кількість створених записів
            - documents_created: кількість створених документів
            - warnings: список попереджень
        """
        if settings is None:
            settings = AutoDistributeSettings()

        if staff_list is None:
            staff_list = self.get_staff_for_schedule(year)

        entries_created = 0
        documents_created = 0
        warnings = []

        for staff in staff_list:
            # Перевіряємо чи пропускаємо працівників з існуючими записами
            if settings.skip_existing:
                existing = (
                    self.db.query(AnnualSchedule)
                    .filter(
                        AnnualSchedule.year == year,
                        AnnualSchedule.staff_id == staff.id,
                    )
                    .all()
                )
                if existing:
                    existing_days = sum(
                        (e.planned_end - e.planned_start).days + 1
                        for e in existing
                    )
                    warnings.append(f"{staff.pib_nom} - вже має {existing_days} днів")
                    continue

            # Отримуємо заброньовані дати
            booked_dates = self._get_booked_dates(staff)

            # Отримуємо доступні дати з урахуванням фільтрації по місяцях
            valid_dates = self._get_valid_dates(
                staff, year, booked_dates,
                all_year=settings.all_year,
                summer_only=settings.summer_only,
                winter_only=settings.winter_only
            )

            if not valid_dates:
                warnings.append(f"{staff.pib_nom} - немає доступних дат")
                continue

            # Визначаємо загальну кількість днів
            if settings.use_balance_days and staff.vacation_balance:
                total_days = int(staff.vacation_balance)
            else:
                total_days = settings.custom_days

            total_days = max(total_days, settings.min_days_per_period)

            # Розбиваємо на періоди
            periods = []
            remaining_days = total_days
            chunk_num = 1

            # Визначаємо максимальну кількість періодів
            max_periods = settings.max_periods if not settings.use_all_balance else 10

            while remaining_days >= settings.min_days_per_period and chunk_num <= max_periods:
                # Вибираємо розмір періоду в межах мін-макс
                min_days = settings.min_days_per_period
                max_days = min(settings.max_days_per_period, remaining_days)

                if max_days >= min_days:
                    period_days = random.randint(min_days, max_days)
                else:
                    period_days = remaining_days

                periods.append({
                    'chunk': chunk_num,
                    'days': period_days
                })
                remaining_days -= period_days
                chunk_num += 1

            if not periods:
                warnings.append(f"{staff.pib_nom} - замало днів для створення відпусток")
                continue

            # Для кожного періоду шукаємо діапазон
            for period_info in periods:
                period_days = period_info['days']

                # Шукаємо діапазон
                ranges = self._find_vacation_ranges(
                    valid_dates,
                    booked_dates,
                    period_days,
                    staff.term_end,
                    shuffle=settings.random_distribution
                )

                if not ranges:
                    # Спробуємо з меншою кількістю днів
                    for test_days in range(period_days - 1, settings.min_days_per_period - 1, -1):
                        ranges = self._find_vacation_ranges(
                            valid_dates,
                            booked_dates,
                            test_days,
                            staff.term_end,
                            shuffle=settings.random_distribution
                        )
                        if ranges:
                            period_days = test_days
                            break

                if not ranges:
                    warnings.append(
                        f"{staff.pib_nom} - не вдалося знайти дати для періоду "
                        f"{period_info['chunk']}"
                    )
                    continue

                # Вибір з можливих діапазонів
                if settings.random_distribution:
                    start_date, end_date = random.choice(ranges)
                else:
                    start_date, end_date = ranges[0]

                # Перевіряємо перетини з існуючими записами графіку
                if self._check_overlaps(staff.id, start_date, end_date, year):
                    warnings.append(
                        f"{staff.pib_nom} - перетин для періоду {period_info['chunk']}"
                    )
                    continue

                # Оновлюємо заброньовані дати
                current = start_date
                while current <= end_date:
                    booked_dates.add(current)
                    current += datetime.timedelta(days=1)

                # Оновлюємо valid_dates
                valid_dates = [d for d in valid_dates if d not in booked_dates]

                # Створюємо AnnualSchedule
                entry = AnnualSchedule(
                    year=year,
                    staff_id=staff.id,
                    planned_start=start_date,
                    planned_end=end_date,
                    is_used=False,
                )
                self.db.add(entry)
                entries_created += 1

                # Створюємо Document (чернетка)
                if settings.create_documents:
                    doc = Document(
                        staff_id=staff.id,
                        doc_type=DocumentType(settings.doc_type),
                        date_start=start_date,
                        date_end=end_date,
                        days_count=period_days,
                        payment_period="Авторозподіл графіку",
                        status=DocumentStatus.DRAFT,
                    )
                    self.db.add(doc)
                    documents_created += 1

        self.db.commit()

        return {
            "entries_created": entries_created,
            "documents_created": documents_created,
            "warnings": warnings,
        }

    def _check_overlaps(
        self,
        staff_id: int,
        start_date: datetime.date,
        end_date: datetime.date,
        year: int | None = None
    ) -> bool:
        """
        Перевіряє чи перетинається нова відпустка з існуючими.

        Args:
            staff_id: ID співробітника
            start_date: Початок нової відпустки
            end_date: Кінець нової відпустки
            year: Рік фільтрації (опціонально)

        Returns:
            True якщо є перетин, False якщо ні
        """
        query = self.db.query(AnnualSchedule).filter(
            AnnualSchedule.staff_id == staff_id
        )
        if year is not None:
            query = query.filter(AnnualSchedule.year == year)

        existing = query.all()

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
        Валідує запис графіку.

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
