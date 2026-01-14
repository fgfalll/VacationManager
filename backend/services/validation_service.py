"""Сервіс валідації бізнес-правил."""

from datetime import date, timedelta
from typing import Final, List

from sqlalchemy.orm import Session

from backend.models.staff import Staff
from backend.services.date_parser import DateParser
from shared.constants import WEEKEND_DAYS
from shared.exceptions import ValidationError


class ValidationService:
    """
    Сервіс для валідації бізнес-правил системи.

    Включає перевірки:
    - Валідність дат (початок < кінець)
    - Дати не можуть бути вихідними
    - Відпустка не виходить за межі контракту
    - Достатній баланс відпустки
    - Немає перетинів з іншими відпустками
    """

    # Мінімальна тривалість відпустки в днях
    MIN_VACATION_DAYS: Final = 1

    # Максимальна тривалість відпустки в днях (безперервна)
    MAX_VACATION_DAYS: Final = 59

    @staticmethod
    def validate_vacation_dates(
        start: date,
        end: date,
        staff: Staff,
        db: Session,
    ) -> None:
        """
        Валідує дати відпустки згідно з бізнес-правилами.

        Args:
            start: Початок відпустки
            end: Кінець відпустки
            staff: Співробітник
            db: Сесія бази даних

        Raises:
            ValidationError: Якщо дати не відповідають правилам
        """
        # Правило 1: Початок раніше за кінець
        if start >= end:
            raise ValidationError(
                "Дата початку має бути раніше за дату завершення"
            )

        # Правило 2: Не може бути у вихідні
        if start.weekday() in WEEKEND_DAYS:
            weekday_name = ValidationService._get_weekday_name(start.weekday())
            raise ValidationError(
                f"Дата початку ({start.strftime('%d.%m.%Y')}) "
                f"припадає на {weekday_name}"
            )

        if end.weekday() in WEEKEND_DAYS:
            weekday_name = ValidationService._get_weekday_name(end.weekday())
            raise ValidationError(
                f"Дата завершення ({end.strftime('%d.%m.%Y')}) "
                f"припадає на {weekday_name}"
            )

        # Правило 3: Не виходить за межі контракту
        if end > staff.term_end:
            raise ValidationError(
                f"Відпустка виходить за межі контракту "
                f"(закінчується {staff.term_end.strftime('%d.%m.%Y')})"
            )

        # Правило 4: Тривалість в допустимих межах
        days = ValidationService.calculate_working_days(start, end)
        if days < ValidationService.MIN_VACATION_DAYS:
            raise ValidationError(
                f"Мінімальна тривалість відпустки: {ValidationService.MIN_VACATION_DAYS} день"
            )
        if days > ValidationService.MAX_VACATION_DAYS:
            raise ValidationError(
                f"Максимальна тривалість безперервної відпустки: "
                f"{ValidationService.MAX_VACATION_DAYS} днів"
            )

        # Правило 5: Достатній баланс днів (для оплачуваної відпустки)
        if days > staff.vacation_balance:
            raise ValidationError(
                f"Недостатньо днів відпустки. "
                f"Запитано: {days}, доступно: {staff.vacation_balance}"
            )

        # Правило 6: Не перетинається з іншими відпустками
        ValidationService._validate_no_overlap(start, end, staff.id, db)

    @staticmethod
    def calculate_working_days(start: date, end: date) -> int:
        """
        Обчислює кількість робочих днів між датами включно.

        Враховує суботи та неділі як неробочі дні.
        Державні свята НЕ враховуються (потребує окремого календаря).

        Args:
            start: Початкова дата
            end: Кінцева дата

        Returns:
            Кількість робочих днів

        Example:
            >>> ValidationService.calculate_working_days(date(2025, 7, 7), date(2025, 7, 11))
            5  # Понеділок - П'ятниця
            >>> ValidationService.calculate_working_days(date(2025, 7, 7), date(2025, 7, 13))
            5  # Понеділок - П'ятниця (субота і неділя не рахуються)
        """
        days = 0
        current = start

        while current <= end:
            if current.weekday() not in WEEKEND_DAYS:
                days += 1
            current += timedelta(days=1)

        return days

    @staticmethod
    def calculate_calendar_days(start: date, end: date) -> int:
        """
        Обчислює кількість календарних днів між датами включно.

        Args:
            start: Початкова дата
            end: Кінцева дата

        Returns:
            Кількість календарних днів
        """
        return (end - start).days + 1

    @staticmethod
    def validate_schedule_dates(
        start: date,
        end: date,
        staff: Staff,
        db: Session,
    ) -> None:
        """
        Валідує дати для річного графіка відпусток.

        Менш сувора валідація, ніж для реальних відпусток,
        оскільки графік це лише план.

        Args:
            start: Початок відпустки
            end: Кінець відпустки
            staff: Співробітник
            db: Сесія бази даних

        Raises:
            ValidationError: Якщо дати некоректні
        """
        if start >= end:
            raise ValidationError(
                "Дата початку має бути раніше за дату завершення"
            )

        if start.weekday() in WEEKEND_DAYS:
            raise ValidationError(
                "Початок відпустки не може бути у вихідний день"
            )

        if end.weekday() in WEEKEND_DAYS:
            raise ValidationError(
                "Кінець відпустки не може бути у вихідний день"
            )

        # Перевірка перетинів з іншими записами в графіку
        from backend.models.schedule import AnnualSchedule

        overlaps = db.query(AnnualSchedule).filter(
            AnnualSchedule.staff_id == staff.id,
            AnnualSchedule.year == start.year,
            AnnualSchedule.id != db.query(AnnualSchedule).filter(
                AnnualSchedule.staff_id == staff.id,
                AnnualSchedule.year == start.year,
            ).first().id if db.query(AnnualSchedule).filter(
                AnnualSchedule.staff_id == staff.id,
                AnnualSchedule.year == start.year,
            ).first() else 0,
        ).all()

        for entry in overlaps:
            if not (end < entry.planned_start or start > entry.planned_end):
                raise ValidationError(
                    f"Перетин з існуючим записом у графіку: "
                    f"{entry.planned_start.strftime('%d.%m.%Y')} - "
                    f"{entry.planned_end.strftime('%d.%m.%Y')}"
                )

    @staticmethod
    def validate_staff_data(staff: Staff) -> None:
        """
        Валідує дані співробітника.

        Args:
            staff: Співробітник для валідації

        Raises:
            ValidationError: Якщо дані некоректні
        """
        if staff.term_start >= staff.term_end:
            raise ValidationError(
                "Дата початку контракту має бути раніше за дату завершення"
            )

        if staff.rate <= 0 or staff.rate > 1:
            raise ValidationError(
                "Ставка повинна бути в діапазоні (0, 1]"
            )

        if staff.vacation_balance < 0:
            raise ValidationError(
                "Баланс відпустки не може бути від'ємним"
            )

    @staticmethod
    def _validate_no_overlap(start: date, end: date, staff_id: int, db: Session) -> None:
        """
        Перевіряє відсутність перетинів з іншими відпустками співробітника.

        Args:
            start: Початок нової відпустки
            end: Кінець нової відпустки
            staff_id: ID співробітника
            db: Сесія бази даних

        Raises:
            ValidationError: Якщо знайдено перетин
        """
        from backend.models.document import Document
        from shared.enums import DocumentStatus

        # Шукаємо активні відпустки (не processed)
        existing = db.query(Document).filter(
            Document.staff_id == staff_id,
            Document.status != DocumentStatus.PROCESSED,
        ).all()

        for doc in existing:
            # Перевіряємо перетин: нова не закінчується до початку існуючої
            # і не починається після кінця існуючої
            if not (end < doc.date_start or start > doc.date_end):
                raise ValidationError(
                    f"Перетин з існуючою відпусткою: "
                    f"{doc.date_start.strftime('%d.%m.%Y')} - "
                    f"{doc.date_end.strftime('%d.%m.%Y')} "
                    f"(документ #{doc.id})"
                )

    @staticmethod
    def _get_weekday_name(weekday: int) -> str:
        """
        Повертає назву дня тижня українською.

        Args:
            weekday: День тижня (0 = Понеділок, ..., 6 = Неділя)

        Returns:
            Назва дня тижня
        """
        days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
        return days[weekday]

    @staticmethod
    def parse_complex_dates(
        date_string: str,
        default_year: int | None = None
    ) -> List[date]:
        """
        Розбирає складний рядок з датами.

        Підтримує формати:
        - "12 березня" - одиночна дата
        - "12, 14, 19 березня" - кілька дат
        - "12-19 березня" - діапазон
        - "12, 14, 19-21 березня" - комбінація
        - "12.03.2025" - класичний формат
        - "12/03/2025" - альтернативний роздільник

        Args:
            date_string: Рядок з датами
            default_year: Рік за замовчуванням

        Returns:
            Список дат у хронологічному порядку

        Raises:
            ValidationError: Якщо не вдалося розібрати дати

        Example:
            >>> dates = ValidationService.parse_complex_dates("12, 14, 19-21 березня 2025")
            >>> len(dates)
            5
        """
        parser = DateParser(default_year)
        try:
            return parser.parse(date_string, default_year)
        except ValueError as e:
            raise ValidationError(str(e)) from e

    @staticmethod
    def validate_complex_dates(
        date_string: str,
        staff: Staff,
        default_year: int | None = None
    ) -> tuple[List[date], List[str]]:
        """
        Розбирає та валідує складний рядок з датами.

        Args:
            date_string: Рядок з датами
            staff: Співробітник для перевірки балансу
            default_year: Рік за замовчуванням

        Returns:
            (Список дат, Список попереджень)

        Raises:
            ValidationError: Якщо дати некоректні

        Example:
            >>> dates, warnings = ValidationService.validate_complex_dates(
            ...     "12, 14, 19-21 березня 2025", staff
            ... )
        """
        parser = DateParser(default_year)
        dates = parser.parse(date_string, default_year)

        warnings = []

        # Валідація кожної дати
        for d in dates:
            # Перевіряємо на вихідні
            if d.weekday() in WEEKEND_DAYS:
                weekday_name = ValidationService._get_weekday_name(d.weekday())
                warnings.append(f"{d.strftime('%d.%m.%Y')} припадає на {weekday_name}")

            # Перевіряємо контракт
            if d > staff.term_end:
                warnings.append(
                    f"{d.strftime('%d.%m.%Y')} виходить за межі контракту "
                    f"(до {staff.term_end.strftime('%d.%m.%Y')})"
                )

        # Рахуємо загальну кількість днів
        total_days = len(dates)
        if total_days > staff.vacation_balance:
            warnings.append(
                f"Загальна кількість днів ({total_days}) перевищує баланс ({staff.vacation_balance})"
            )

        return dates, warnings

    @staticmethod
    def format_dates_readable(dates: List[date], format_type: str = "readable") -> str:
        """
        Форматує список дат у рядок.

        Args:
            dates: Список дат
            format_type: Тип форматування ("readable", "compact", "full")

        Returns:
            Відформатований рядок

        Example:
            >>> dates = [date(2025, 3, 12), date(2025, 3, 14)]
            >>> ValidationService.format_dates_readable(dates)
            '12, 14 березня'
        """
        parser = DateParser()
        return parser.format_as_string(dates, format_type)


class DateRange:
    """
    Клас для представлення діапазону дат.

    Attributes:
        start: Початкова дата
        end: Кінцева дата
    """

    def __init__(self, start: date, end: date):
        if start > end:
            raise ValueError("Початкова дата не може бути пізнішою за кінцеву")
        self.start = start
        self.end = end

    def overlaps(self, other: "DateRange") -> bool:
        """
        Перевіряє, чи перетинається цей діапазон з іншим.

        Args:
            other: Інший діапазон дат

        Returns:
            True якщо діапазони перетинаються
        """
        return not (self.end < other.start or self.start > other.end)

    def contains(self, d: date) -> bool:
        """
        Перевіряє, чи входить дата в діапазон.

        Args:
            d: Дата для перевірки

        Returns:
            True якщо дата в діапазоні
        """
        return self.start <= d <= self.end

    @property
    def days(self) -> int:
        """Кількість днів у діапазоні."""
        return (self.end - self.start).days + 1

    def __repr__(self) -> str:
        return f"DateRange({self.start}, {self.end})"
