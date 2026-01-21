"""Сервіс валідації бізнес-правил."""

from datetime import date, timedelta
from typing import Final, List, Optional

from sqlalchemy.orm import Session

from backend.models.staff import Staff
from backend.services.date_parser import DateParser
from shared.constants import (
    WEEKEND_DAYS,
    DEFAULT_VACATION_DAYS,
    DEFAULT_MARTIAL_LAW_VACATION_LIMIT,
    SETTING_MARTIAL_LAW_ENABLED,
    SETTING_MARTIAL_LAW_VACATION_LIMIT,
    SETTING_VACATION_DAYS_SCIENTIFIC_PEDAGOGICAL,
    SETTING_VACATION_DAYS_PEDAGOGICAL,
    SETTING_VACATION_DAYS_ADMINISTRATIVE,
    SETTING_COUNT_HOLIDAYS_AS_VACATION,
)
from shared.exceptions import ValidationError


# Українські державні свята (фіксовані дати)
UKRAINIAN_HOLIDAYS = [
    (1, 1),    # Новий рік
    (1, 7),    # Різдво
    (3, 8),    # Міжнародний жіночий день
    (5, 1),    # День праці
    (5, 8),    # День пам'яті та перемоги
    (6, 28),   # День Конституції
    (8, 24),   # День Незалежності
    (9, 1),    # День знань
    (10, 14),  # День захисників та захисниць
    (12, 25),  # Різдво Христове
]


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

        # Правило 7: Не перетинається з записами відвідуваності на роботу
        ValidationService.validate_no_attendance_overlap(start, end, staff.id, db)

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
    def validate_no_attendance_overlap(start: date, end: date, staff_id: int, db: Session) -> None:
        """
        Перевіряє, що період відпустки не перетинається з записами відвідуваності.

        Будь-який запис відвідуваності (крім "Р" - присутність на роботі) не повинен
        перетинатися з відпусткою, оскільки такі записи вже замінюють робочі дні.

        Args:
            start: Початок відпустки
            end: Кінець відпустки
            staff_id: ID співробітника
            db: Сесія бази даних

        Raises:
            ValidationError: Якщо знайдено перетин
        """
        from backend.models.attendance import Attendance

        # Шукаємо ВСІ записи відвідуваності (крім "Р" - присутність) в цей період
        existing = db.query(Attendance).filter(
            Attendance.staff_id == staff_id,
            Attendance.code != "Р",  # Всі крім присутності на роботі
            # Перевіряємо перетин періодів
            Attendance.date <= end,
        ).all()

        for att in existing:
            att_end = att.date_end or att.date
            # Перевіряємо перетин: відпустка не закінчується до початку запису
            # і не починається після кінця запису
            if not (end < att.date or start > att_end):
                date_str = att.date.strftime('%d.%m.%Y')
                raise ValidationError(
                    f"Період відпустки ({start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}) "
                    f"перетинається з записом відвідуваності '{att.code}' від {date_str}"
                )

    @staticmethod
    def validate_no_vacation_overlap(attendance_date: date, staff_id: int, db: Session) -> None:
        """
        Перевіряє, що дата відвідуваності не перетинається з відпустками працівника.

        Args:
            attendance_date: Дата відвідуваності
            staff_id: ID співробітника
            db: Сесія бази даних

        Raises:
            ValidationError: Якщо знайдено перетин
        """
        from backend.models.document import Document
        from backend.models.attendance import Attendance
        from shared.enums import DocumentStatus

        # Перевіряємо відпустки (всі стани)
        existing = db.query(Document).filter(
            Document.staff_id == staff_id,
        ).all()

        for doc in existing:
            if not (attendance_date < doc.date_start or attendance_date > doc.date_end):
                raise ValidationError(
                    f"Дата {attendance_date.strftime('%d.%m.%Y')} "
                    f"перетинається з відпусткою {doc.date_start.strftime('%d.%m.%Y')} - "
                    f"{doc.date_end.strftime('%d.%m.%Y')} (документ #{doc.id})"
                )

        # Перевіряємо інші записи відвідуваності (крім "Р" - присутність на роботі)
        existing_att = db.query(Attendance).filter(
            Attendance.staff_id == staff_id,
            Attendance.code != "Р",
        ).all()

        for att in existing_att:
            att_end = att.date_end or att.date
            if not (attendance_date < att.date or attendance_date > att_end):
                raise ValidationError(
                    f"Дата {attendance_date.strftime('%d.%m.%Y')} "
                    f"перетинається з записом '{att.code}' від {att.date.strftime('%d.%m.%Y')}"
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

    # ========== Методи для воєнного стану ==========

    @staticmethod
    def is_martial_law_enabled(db: Session) -> bool:
        """
        Перевіряє чи увімкнено режим воєнного стану.

        Args:
            db: Сесія бази даних

        Returns:
            True якщо воєнний стан увімкнено
        """
        from backend.models.settings import SystemSettings
        return SystemSettings.get_value(db, SETTING_MARTIAL_LAW_ENABLED, False)

    @staticmethod
    def get_martial_law_vacation_limit(db: Session) -> int:
        """
        Отримує ліміт днів відпустки під час воєнного стану.

        Args:
            db: Сесія бази даних

        Returns:
            Ліміт днів відпустки (за замовчуванням 24)
        """
        from backend.models.settings import SystemSettings
        return SystemSettings.get_value(
            db, SETTING_MARTIAL_LAW_VACATION_LIMIT, DEFAULT_MARTIAL_LAW_VACATION_LIMIT
        )

    @staticmethod
    def get_vacation_days_for_staff(db: Session, staff: Staff) -> int:
        """
        Отримує річну норму днів відпустки для співробітника.

        Враховує тип посади та налаштування системи.

        Args:
            db: Сесія бази даних
            staff: Співробітник

        Returns:
            Кількість днів відпустки на рік
        """
        from backend.models.settings import SystemSettings

        # Визначаємо тип посади
        position_lower = staff.position.lower() if staff.position else ""

        # Науково-педагогічні працівники
        if any(word in position_lower for word in ["професор", "доцент", "старший викладач", "викладач", "асистент", "завідувач"]):
            return SystemSettings.get_value(
                db, SETTING_VACATION_DAYS_SCIENTIFIC_PEDAGOGICAL,
                DEFAULT_VACATION_DAYS["scientific_pedagogical"]
            )
        # Педагогічні працівники
        elif any(word in position_lower for word in ["педагог", "вихователь", "методист"]):
            return SystemSettings.get_value(
                db, SETTING_VACATION_DAYS_PEDAGOGICAL,
                DEFAULT_VACATION_DAYS["pedagogical"]
            )
        # Адміністративний персонал
        else:
            return SystemSettings.get_value(
                db, SETTING_VACATION_DAYS_ADMINISTRATIVE,
                DEFAULT_VACATION_DAYS["administrative"]
            )

    @staticmethod
    def is_holiday(d: date) -> bool:
        """
        Перевіряє чи є дата державним святом.

        Args:
            d: Дата для перевірки

        Returns:
            True якщо дата є святом
        """
        return (d.month, d.day) in UKRAINIAN_HOLIDAYS

    @staticmethod
    def calculate_calendar_days_counting_holidays(start: date, end: date, count_holidays: bool = True) -> int:
        """
        Обчислює кількість календарних днів у періоді.

        Args:
            start: Початкова дата
            end: Кінцева дата
            count_holidays: Чи включати свята у підрахунок (під час воєнного стану - True)

        Returns:
            Кількість календарних днів
        """
        days = (end - start).days + 1

        if not count_holidays:
            # Підраховуємо скільки свят випадає на період
            holidays_in_range = 0
            current = start
            while current <= end:
                if ValidationService.is_holiday(current):
                    holidays_in_range += 1
                current += timedelta(days=1)
            days -= holidays_in_range

        return days

    @staticmethod
    def calculate_vacation_days(
        start: date,
        end: date,
        db: Session,
        staff: Optional[Staff] = None
    ) -> int:
        """
        Обчислює кількість днів відпустки з урахуванням налаштувань воєнного стану.

        Під час воєнного стану:
        - Всі дні рахуються як відпускні (включаючи вихідні та свята)
        - Діє ліміт 24 дні (або налаштований ліміт)

        В звичайному режимі:
        - Вихідні НЕ рахуються
        - Свята НЕ рахуються

        Args:
            start: Початкова дата
            end: Кінцева дата
            db: Сесія бази даних
            staff: Опціонально - співробітник для додаткових перевірок

        Returns:
            Кількість днів відпустки
        """
        martial_law = ValidationService.is_martial_law_enabled(db)

        if martial_law:
            # Під час воєнного стану - рахуємо всі календарні дні
            return (end - start).days + 1
        else:
            # В звичайному режимі - рахуємо тільки робочі дні (виключаємо вихідні та свята)
            return ValidationService.calculate_calendar_days_counting_holidays(start, end, count_holidays=False)

    @staticmethod
    def validate_vacation_against_balance(
        start: date,
        end: date,
        staff: Staff,
        db: Session
    ) -> tuple[bool, str]:
        """
        Перевіряє чи не перевищує відпустка баланс співробітника.

        Під час воєнного стану враховує ліміт 24 дні.

        Args:
            start: Початок відпустки
            end: Кінець відпустки
            staff: Співробітник
            db: Сесія бази даних

        Returns:
            (True, "") якщо OK, (False, повідомлення про помилку) якщо ні
        """
        requested_days = ValidationService.calculate_vacation_days(start, end, db, staff)
        balance = staff.vacation_balance or 0

        martial_law = ValidationService.is_martial_law_enabled(db)

        if martial_law:
            limit = ValidationService.get_martial_law_vacation_limit(db)
            # Перевіряємо і баланс, і ліміт
            if requested_days > balance:
                return False, (
                    f"Недостатньо днів відпустки. "
                    f"Запитано: {requested_days}, доступно: {balance}"
                )
            if requested_days > limit:
                return False, (
                    f"Під час воєнного стану ліміт відпустки: {limit} днів. "
                    f"Запитано: {requested_days} днів."
                )
        else:
            if requested_days > balance:
                return False, (
                    f"Недостатньо днів відпустки. "
                    f"Запитано: {requested_days}, доступно: {balance}"
                )

        return True, ""

    @staticmethod
    def validate_document_limits(
        staff_id: int,
        doc_type: str,
        exclude_document_id: int | None,
        db: Session,
    ) -> tuple[bool, str]:
        """
        Перевіряє ліміти кількості документів для співробітника.

        Правила:
        - Максимум 1 продовження контракту на підписі
        - Максимум 3 відпустки на підписі

        Args:
            staff_id: ID співробітника
            doc_type: Тип документа (vacation_paid, vacation_unpaid, term_extension)
            exclude_document_id: ID документа який редагується (не враховувати)
            db: Сесія бази даних

        Returns:
            (True, "") якщо OK, (False, повідомлення про помилку) якщо ні
        """
        from backend.models.document import Document
        from shared.enums import DocumentStatus, DocumentType

        # Конвертуємо рядок doc_type в DocumentType
        try:
            doc_type_enum = DocumentType(doc_type)
        except ValueError:
            return True, ""  # Невідомий тип - пропускаємо

        # Підраховуємо документи на підписі для цього співробітника
        query = db.query(Document).filter(
            Document.staff_id == staff_id,
            Document.status.in_([
                DocumentStatus.SIGNED_BY_APPLICANT,
                DocumentStatus.APPROVED_BY_DISPATCHER,
                DocumentStatus.SIGNED_DEP_HEAD,
                DocumentStatus.AGREED,
                DocumentStatus.SIGNED_RECTOR,
            ]),
        )

        # Виключаємо поточний документ при редагуванні
        if exclude_document_id:
            query = query.filter(Document.id != exclude_document_id)

        existing_docs = query.all()

        if doc_type_enum == DocumentType.TERM_EXTENSION:
            # Перевіряємо чи вже є продовження контракту
            term_extensions = [d for d in existing_docs if d.doc_type == DocumentType.TERM_EXTENSION]
            if term_extensions:
                existing = term_extensions[0]
                return False, (
                    f"На підписі вже є продовження контракту "
                    f"(№{existing.id} від {existing.date_start.strftime('%d.%m.%Y')}). "
                    f"Спочатку завершіть або відкликайте попередній документ."
                )

        elif doc_type_enum in (DocumentType.VACATION_PAID, DocumentType.VACATION_UNPAID):
            # Перевіряємо кількість відпусток
            vacations = [d for d in existing_docs if d.doc_type in (
                DocumentType.VACATION_PAID, DocumentType.VACATION_UNPAID
            )]
            if len(vacations) >= 3:
                doc_list = "\n".join([f"- №{d.id} ({d.date_start.strftime('%d.%m.%Y')})" for d in vacations[:3]])
                return False, (
                    f"На підписі вже є 3 відпустки. "
                    f"Спочатку завершіть або відкликайте існуючі документи:\n{doc_list}"
                )

        return True, ""


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
