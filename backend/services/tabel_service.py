"""Сервіс для генерації табеля обліку робочого часу."""

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from backend.core.database import get_db_context
from backend.models import (
    Attendance,
    CODE_TO_LETTER,
    Document,
    DocumentStatus,
    DocumentType,
    Staff,
    SystemSettings,
    WEEKEND_DAYS,
    WorkScheduleType,
)


def format_initials(pib: str) -> str:
    """
    Formats full name (Last First Patronymic) to Last F. P.
    Example: Петренко Тарас Степанович -> Петренко Т. С.
    """
    parts = pib.split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}. {parts[2][0]}."
    elif len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return pib


# Month names in Ukrainian
MONTHS_UKR = [
    "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
    "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"
]

# Logger for this module
logger = logging.getLogger(__name__)

# Month names in genitive case (for header)
MONTHS_GENITIVE = [
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпеня", "вересня", "жовтня", "листопада", "грудня"
]

# Institution info
DEFAULT_INSTITUTION_NAME = "Національний університет «Полтавська політехніка імені Юрія Кондратюка»"
DEFAULT_EDRPOU_CODE = "02065502"

# Standard work hours per day
STANDARD_WORK_HOURS = 8.0


@dataclass
class DayStatus:
    """Статус дня для табеля."""
    code: str  # Літерний код (Р, В, ДО, Л, тощо)
    hours: str = ""  # Кількість годин для відображення
    weekend: bool = False  # Чи вихідний день
    disabled: bool = False  # Чи день за межами контракту (перед початком або після закінчення)
    strikethrough: bool = False  # Чи день повинен бути закреслений (empty cells)


@dataclass
class AbsenceTotals:
    """Підсумки відсутностей за місяць (per half-month for template)."""
    # First half of month (_1 suffix)
    vacation_8_10_1: int = 0
    vacation_11_15_1: int = 0
    vacation_18_1: int = 0
    vacation_19_1: int = 0
    business_trip_1: int = 0
    part_time_1: int = 0
    temp_transfer_1: int = 0
    idle_1: int = 0
    absenteeism_1: int = 0
    strike_1: int = 0
    temp_disability_1: int = 0
    unexcused_1: int = 0

    # Second half of month (_2 suffix)
    vacation_8_10_2: int = 0
    vacation_11_15_2: int = 0
    vacation_18_2: int = 0
    vacation_19_2: int = 0
    business_trip_2: int = 0
    part_time_2: int = 0
    temp_transfer_2: int = 0
    idle_2: int = 0
    absenteeism_2: int = 0
    strike_2: int = 0
    temp_disability_2: int = 0
    unexcused_2: int = 0

    # Monthly totals (for Всього row)
    @property
    def vacation_8_10(self) -> int:
        return self.vacation_8_10_1 + self.vacation_8_10_2

    @property
    def vacation_11_15(self) -> int:
        return self.vacation_11_15_1 + self.vacation_11_15_2

    @property
    def vacation_18(self) -> int:
        return self.vacation_18_1 + self.vacation_18_2

    @property
    def vacation_19(self) -> int:
        return self.vacation_19_1 + self.vacation_19_2

    @property
    def business_trip(self) -> int:
        return self.business_trip_1 + self.business_trip_2

    @property
    def part_time(self) -> int:
        return self.part_time_1 + self.part_time_2

    @property
    def temp_transfer(self) -> int:
        return self.temp_transfer_1 + self.temp_transfer_2

    @property
    def idle(self) -> int:
        return self.idle_1 + self.idle_2

    @property
    def absenteeism(self) -> int:
        return self.absenteeism_1 + self.absenteeism_2

    @property
    def strike(self) -> int:
        return self.strike_1 + self.strike_2

    @property
    def temp_disability(self) -> int:
        return self.temp_disability_1 + self.temp_disability_2

    @property
    def unexcused(self) -> int:
        return self.unexcused_1 + self.unexcused_2

    def to_dict(self) -> dict[str, int | str]:
        """Convert to dictionary for template."""
        return {
            # First half
            'vacation_8_10_1': self.vacation_8_10_1 or '',
            'vacation_11_15_1': self.vacation_11_15_1 or '',
            'vacation_18_1': self.vacation_18_1 or '',
            'vacation_19_1': self.vacation_19_1 or '',
            'business_trip_1': self.business_trip_1 or '',
            'part_time_1': self.part_time_1 or '',
            'temp_transfer_1': self.temp_transfer_1 or '',
            'idle_1': self.idle_1 or '',
            'absenteeism_1': self.absenteeism_1 or '',
            'strike_1': self.strike_1 or '',
            'temp_disability_1': self.temp_disability_1 or '',
            'unexcused_1': self.unexcused_1 or '',
            # Second half
            'vacation_8_10_2': self.vacation_8_10_2 or '',
            'vacation_11_15_2': self.vacation_11_15_2 or '',
            'vacation_18_2': self.vacation_18_2 or '',
            'vacation_19_2': self.vacation_19_2 or '',
            'business_trip_2': self.business_trip_2 or '',
            'part_time_2': self.part_time_2 or '',
            'temp_transfer_2': self.temp_transfer_2 or '',
            'idle_2': self.idle_2 or '',
            'absenteeism_2': self.absenteeism_2 or '',
            'strike_2': self.strike_2 or '',
            'temp_disability_2': self.temp_disability_2 or '',
            'unexcused_2': self.unexcused_2 or '',
            # Monthly totals
            'vacation_8_10': self.vacation_8_10 or '',
            'vacation_11_15': self.vacation_11_15 or '',
            'vacation_18': self.vacation_18 or '',
            'vacation_19': self.vacation_19 or '',
            'business_trip': self.business_trip or '',
            'part_time': self.part_time or '',
            'temp_transfer': self.temp_transfer or '',
            'idle': self.idle or '',
            'absenteeism': self.absenteeism or '',
            'strike': self.strike or '',
            'temp_disability': self.temp_disability or '',
            'unexcused': self.unexcused or '',
        }


@dataclass
class EmployeeData:
    """Дані працівника для табеля."""
    pib: str  # Прізвище, ім'я, по-батькові
    position: str  # Посада
    rate: Decimal | None = None  # Ставка
    days: list[DayStatus] = field(default_factory=list)  # Статус днів (1-31)
    totals: dict[str, Any] = field(default_factory=dict)  # Підсумки
    absence: AbsenceTotals = field(default_factory=AbsenceTotals)  # Відсутності


@dataclass
class TabelTotals:
    """Загальні підсумки по табелю."""
    work_days: int = 0
    work_hours: str = ""
    days: list[int] = field(default_factory=list)  # Підсумки по днях
    absence: AbsenceTotals = field(default_factory=AbsenceTotals)  # Загальні відсутності


def get_jinja_env() -> Environment:
    """Get Jinja2 environment with template loader."""
    # Templates are in desktop/templates/tabel/
    template_dir = Path(__file__).parent.parent.parent / "desktop" / "templates" / "tabel"
    return Environment(loader=FileSystemLoader(str(template_dir)))


def format_hours_decimal(hours: Decimal) -> str:
    """Форматує години для відображення (наприклад, 8,00 або 4,00)."""
    return f"{float(hours):.2f}".replace(".", ",")


def sum_hours(hours_list: list[Decimal]) -> str:
    """Сума годин у форматі для відображення."""
    total = sum(hours_list, Decimal("0"))
    return format_hours_decimal(total)


def get_day_status(
    current_date: date,
    staff: Staff,
    attendance_records: list[Attendance],
    vacations: list[Document],
    weekends: set[int] = WEEKEND_DAYS,
) -> DayStatus:
    """
    Визначає статус дня для працівника.

    Логіка:
    - Дні перед початком контракту: закреслені, порожні
    - Дні після закінчення контракту: закреслені, порожні
    - Вихідні дні (сб, нд): порожньо
    - Відпустки з processed документів: "В" (або інший код відпустки)
    - Відрядження та інші спеціальні коди: з таблиці attendance
    - Робочі дні: "Р" (години показуються лише в підсумках для фахівців)

    Args:
        current_date: Поточна дата
        staff: Об'єкт працівника
        attendance_records: Список записів відвідуваності
        vacations: Список документів відпусток
        weekends: Множина вихідних днів тижня

    Returns:
        DayStatus: Статус дня
    """
    # Check if date is outside contract period (before start or after end)
    # For deactivated employees, term_end is still valid for marking days
    if current_date < staff.term_start:
        # Before contract started - strikethrough, empty
        return DayStatus(code="", strikethrough=True, disabled=True)
    if current_date > staff.term_end:
        # After contract ended - strikethrough, empty
        return DayStatus(code="", strikethrough=True, disabled=True)

    # Check for attendance record first (hand-entered special codes)
    for record in attendance_records:
        record_end = record.date_end or record.date
        if record.date <= current_date <= record_end:
            # Include hours for overtime types, show blank if 0
            hours_val = float(record.hours) if record.hours else 0
            hours_str = str(hours_val) if hours_val > 0 else ""

            return DayStatus(
                code=record.code,
                hours=hours_str,
                weekend=current_date.weekday() in weekends,
            )

    # Check if weekend
    if current_date.weekday() in weekends:
        return DayStatus(code="", weekend=True)

    # Check for vacation (processed documents)
    for vacation in vacations:
        if vacation.date_start <= current_date <= vacation.date_end:
            if vacation.doc_type == DocumentType.VACATION_PAID:
                return DayStatus(code="В")  # Оплачувана відпустка
            elif vacation.doc_type == DocumentType.VACATION_UNPAID:
                return DayStatus(code="НА")  # Відпустка без збереження зарплати за згодою

    # Default: work day (Р only, no hours in cell)
    return DayStatus(code="Р", hours="")


def calculate_absence_totals(
    attendance_records: list[Attendance],
    vacations: list[Document],
    month_start: date,
    month_end: date,
) -> AbsenceTotals:
    """
    Обчислює підсумки відсутностей за записами відвідуваності та відпустками.

    Args:
        attendance_records: Список записів відвідуваності
        vacations: Список документів відпусток
        month_start: Початок місяця
        month_end: Кінець місяця

    Returns:
        AbsenceTotals: Підсумки відсутностей
    """
    totals = AbsenceTotals()

    def add_to_half(field_base: str, record_date: date):
        """Додає 1 до відповідного поля залежно від половини місяця."""
        suffix = "_1" if record_date.day <= 15 else "_2"
        field_name = field_base + suffix
        current = getattr(totals, field_name, 0)
        setattr(totals, field_name, current + 1)

    # Count from attendance records
    from datetime import timedelta
    
    for record in attendance_records:
        code = record.code
        
        # Determine range to count (clip to current month)
        rec_start = max(record.date, month_start)
        rec_end = min(record.date_end or record.date, month_end)
        
        current = rec_start
        while current <= rec_end:
            # Skip if out of range (already handled by min/max but safety check)
            if current < month_start or current > month_end:
                current += timedelta(days=1)
                continue

            if code in ("В", "Д"):  # Відпустки оплачувані (щорічна основна та додаткова)
                add_to_half("vacation_8_10", current)
            elif code in ("Ч", "ТВ", "Н", "ДО", "ВП"):  # Інші оплачувані відпустки
                add_to_half("vacation_11_15", current)
            elif code == "ДД":  # Догляд за дитиною до 6 років
                add_to_half("vacation_18", current)
            elif code in ("НБ", "ДБ", "НА", "БЗ"):  # Відпустка без збереження зарплати
                add_to_half("vacation_19", current)
            elif code == "ВД":  # Відрядження
                add_to_half("business_trip", current)
            elif code in ("РС", "НД"):  # Неповний робочий день
                add_to_half("part_time", current)
            elif code == "НП":  # Тимчасовий перевод на інше підприємство
                add_to_half("temp_transfer", current)
            elif code == "П":  # Простої
                add_to_half("idle", current)
            elif code == "ПР":  # Прогули
                add_to_half("absenteeism", current)
            elif code == "С":  # Страйк
                add_to_half("strike", current)
            elif code in ("ТН", "НН"):  # Тимчасова непрацездатність
                add_to_half("temp_disability", current)
            elif code in ("НЗ", "ІВ", "І", "ІН"):  # Неявки різних типів
                add_to_half("unexcused", current)
            
            current += timedelta(days=1)

    # Count from vacation documents
    from datetime import timedelta
    for vacation in vacations:
        if vacation.status == DocumentStatus.PROCESSED:
            # Iterate through each day of the vacation
            vac_start = max(vacation.date_start, month_start)
            vac_end = min(vacation.date_end, month_end)
            current = vac_start
            while current <= vac_end:
                if vacation.doc_type == DocumentType.VACATION_PAID:
                    add_to_half("vacation_8_10", current)
                elif vacation.doc_type == DocumentType.VACATION_UNPAID:
                    add_to_half("vacation_19", current)
    return totals


def format_short_name(full_name: str) -> str:
    """Formats full name 'Last First Middle' to 'Last F. M.'"""
    parts = full_name.split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}. {parts[2][0]}."
    elif len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return full_name


def get_employee_data(
    staff: Staff,
    month: int,
    year: int,
    attendance_records: list[Attendance],
    vacations: list[Document],
    db=None,
) -> EmployeeData:
    """
    Збирає дані працівника для табеля.

    Args:
        staff: Об'єкт працівника
        month: Місяць
        year: Рік
        attendance_records: Список записів відвідуваності
        vacations: Список документів відпусток
        db: Опціонально - база даних для отримання налаштувань

    Returns:
        EmployeeData: Дані працівника
    """
    _, days_in_month = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    # Get settings for hours calculation
    hours_calc_positions = []
    work_hours_per_day = 8  # Default

    if db:
        # Get positions list (handle both JSON string and list)
        positions_raw = SystemSettings.get_value(db, "tabel_hours_calc_positions", [])
        try:
            if isinstance(positions_raw, str):
                import json
                hours_calc_positions = json.loads(positions_raw)
            elif isinstance(positions_raw, list):
                hours_calc_positions = positions_raw
            else:
                hours_calc_positions = []
        except Exception as e:
            logger.warning(f"Error parsing positions list: {e}, raw value: {positions_raw}")
            hours_calc_positions = []

        # Get work hours per day (handle string conversion)
        hours_raw = SystemSettings.get_value(db, "tabel_work_hours_per_day", 8)
        try:
            work_hours_per_day = int(hours_raw) if hours_raw else 8
        except (ValueError, TypeError):
            work_hours_per_day = 8

    # Check if employee position is in the list for hours calculation
    is_hours_calc = staff.position in hours_calc_positions if staff.position else False

    # Build day statuses
    days = []
    work_days_first_half = 0
    work_days_second_half = 0

    # Overtime counters for first half
    first_half_overtime = 0
    first_half_night = 0
    first_half_evening = 0
    first_half_weekend = 0

    # Overtime counters for second half
    second_half_overtime = 0
    second_half_night = 0
    second_half_evening = 0
    second_half_weekend = 0

    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)
        day_status = get_day_status(current_date, staff, attendance_records, vacations)
        days.append(day_status)

        if day_status.code == "Р":
            # For employees in hours calculation list, show actual hours instead of "Р"
            if is_hours_calc:
                # Calculate hours based on rate (ставка)
                staff_rate = float(staff.rate) if staff.rate else 1.0
                hours_for_day = work_hours_per_day * staff_rate
                day_status.hours = format_hours_decimal(hours_for_day)
            # Count work days for totals (regardless of display)
            if day <= 15:
                work_days_first_half += 1
            else:
                work_days_second_half += 1

        # Count overtime/special hours from attendance records
        if day_status.code == "НУ":  # Надурочні
            hours_val = float(day_status.hours) if day_status.hours else 0
            if day <= 15:
                first_half_overtime += hours_val
            else:
                second_half_overtime += hours_val
        elif day_status.code == "РН":  # Нічні
            hours_val = float(day_status.hours) if day_status.hours else 0
            if day <= 15:
                first_half_night += hours_val
            else:
                second_half_night += hours_val
        elif day_status.code == "ВЧ":  # Вечірні
            hours_val = float(day_status.hours) if day_status.hours else 0
            if day <= 15:
                first_half_evening += hours_val
            else:
                second_half_evening += hours_val
        elif day_status.code == "РВ":  # Вихідні/святкові
            hours_val = float(day_status.hours) if day_status.hours else 0
            if day <= 15:
                first_half_weekend += hours_val
            else:
                second_half_weekend += hours_val

    # Pad to 31 days for template (handle Feb, Apr, Jun, Sep, Nov)
    while len(days) < 31:
        days.append(DayStatus(code="", hours="", weekend=False))

    # Calculate absence totals
    absence = calculate_absence_totals(attendance_records, vacations, month_start, month_end)

    # Check if we should limit hours calculation
    limit_hours_calc = False
    try:
        if db:
            limit_hours_raw = SystemSettings.get_value(db, "tabel_limit_hours_calc", False)
            if isinstance(limit_hours_raw, str):
                limit_hours_calc = limit_hours_raw.lower() in ("true", "1", "yes")
            else:
                limit_hours_calc = bool(limit_hours_raw)
    except Exception as e:
        logger.warning(f"Error reading limit_hours_calc setting: {e}")
        limit_hours_calc = False

    # Calculate total hours using settings value for configured positions
    # If limit_hours_calc is ON, only calculate hours for employees in the positions list
    calculate_hours = not limit_hours_calc or is_hours_calc

    if calculate_hours:
        hours_to_use = work_hours_per_day if is_hours_calc else (staff.daily_work_hours or 8)
        first_half_hours = format_hours_decimal(hours_to_use * work_days_first_half)
        second_half_hours = format_hours_decimal(hours_to_use * work_days_second_half)
        total_hours = format_hours_decimal(hours_to_use * (work_days_first_half + work_days_second_half))
    else:
        # Leave hours blank for employees not in the positions list
        first_half_hours = ''
        second_half_hours = ''
        total_hours = ''

    # Format data
    short_name = format_short_name(staff.pib_nom)
    formatted_rate = str(staff.rate).replace('.', ',') if staff.rate else None
    
    return EmployeeData(
        pib=short_name,
        position=staff.position.lower() if staff.position else "",
        rate=formatted_rate,
        days=days,
        totals={
            'work_days': work_days_first_half + work_days_second_half,
            'work_hours': total_hours,
            'first_half_work_days': work_days_first_half,
            'first_half_work_hours': first_half_hours,
            'second_half_work_days': work_days_second_half,
            'second_half_work_hours': second_half_hours,
            'first_half_overtime': first_half_overtime or '',
            'first_half_night': first_half_night or '',
            'first_half_evening': first_half_evening or '',
            'first_half_weekend': first_half_weekend or '',
            'second_half_overtime': second_half_overtime or '',
            'second_half_night': second_half_night or '',
            'second_half_evening': second_half_evening or '',
            'second_half_weekend': second_half_weekend or '',
        },
        absence=absence,
    )


def get_tabel_totals(employees: list[EmployeeData], month_days: int) -> TabelTotals:
    """
    Обчислює загальні підсумки по табелю.

    Args:
        employees: Список працівників
        month_days: Кількість днів у місяці

    Returns:
        TabelTotals: Загальні підсумки
    """
    totals = TabelTotals()

    # Initialize day totals
    totals.days = [0] * 31
    total_hours_decimal = Decimal("0")

    # Initialize monthly overtime totals
    total_overtime = 0
    total_night = 0
    total_evening = 0
    total_weekend = 0

    for emp in employees:
        totals.work_days += emp.totals['work_days']

        # Add to total hours (only for employees with hours calculated)
        try:
            work_hours = str(emp.totals['work_hours']).strip()
            if work_hours:  # Only parse if not empty
                emp_hours = Decimal(work_hours.replace(",", "."))
                total_hours_decimal += emp_hours
        except (ValueError, decimal.InvalidOperation):
            pass

        # Sum day totals
        for i, day in enumerate(emp.days):
            if day.code:  # Only count non-empty days
                totals.days[i] += 1

        # Sum monthly overtime totals (first_half + second_half)
        try:
            if emp.totals.get('first_half_overtime'):
                total_overtime += int(emp.totals['first_half_overtime'])
            if emp.totals.get('second_half_overtime'):
                total_overtime += int(emp.totals['second_half_overtime'])
            if emp.totals.get('first_half_night'):
                total_night += int(emp.totals['first_half_night'])
            if emp.totals.get('second_half_night'):
                total_night += int(emp.totals['second_half_night'])
            if emp.totals.get('first_half_evening'):
                total_evening += int(emp.totals['first_half_evening'])
            if emp.totals.get('first_half_weekend'):
                total_weekend += int(emp.totals['first_half_weekend'])
        except (ValueError, TypeError):
            pass

        # Sum absence totals (both halves)
        emp_absence = emp.absence
        totals.absence.vacation_8_10_1 += emp_absence.vacation_8_10_1
        totals.absence.vacation_8_10_2 += emp_absence.vacation_8_10_2
        totals.absence.vacation_11_15_1 += emp_absence.vacation_11_15_1
        totals.absence.vacation_11_15_2 += emp_absence.vacation_11_15_2
        totals.absence.vacation_18_1 += emp_absence.vacation_18_1
        totals.absence.vacation_18_2 += emp_absence.vacation_18_2
        totals.absence.vacation_19_1 += emp_absence.vacation_19_1
        totals.absence.vacation_19_2 += emp_absence.vacation_19_2
        totals.absence.business_trip_1 += emp_absence.business_trip_1
        totals.absence.business_trip_2 += emp_absence.business_trip_2
        totals.absence.part_time_1 += emp_absence.part_time_1
        totals.absence.part_time_2 += emp_absence.part_time_2
        totals.absence.temp_transfer_1 += emp_absence.temp_transfer_1
        totals.absence.temp_transfer_2 += emp_absence.temp_transfer_2
        totals.absence.idle_1 += emp_absence.idle_1
        totals.absence.idle_2 += emp_absence.idle_2
        totals.absence.absenteeism_1 += emp_absence.absenteeism_1
        totals.absence.absenteeism_2 += emp_absence.absenteeism_2
        totals.absence.strike_1 += emp_absence.strike_1
        totals.absence.strike_2 += emp_absence.strike_2
        totals.absence.temp_disability_1 += emp_absence.temp_disability_1
        totals.absence.temp_disability_2 += emp_absence.temp_disability_2
        totals.absence.unexcused_1 += emp_absence.unexcused_1
        totals.absence.unexcused_2 += emp_absence.unexcused_2


    # Format total hours
    totals.work_hours = format_hours_decimal(total_hours_decimal) if total_hours_decimal > 0 else "0,00"

    # Add monthly overtime totals to the totals dict
    totals.__dict__['overtime'] = total_overtime if total_overtime else ''
    totals.__dict__['night'] = total_night if total_night else ''
    totals.__dict__['evening'] = total_evening if total_evening else ''
    totals.__dict__['weekend'] = total_weekend if total_weekend else ''

    return totals


def generate_tabel_html(
    month: int,
    year: int,
    institution_name: str = DEFAULT_INSTITUTION_NAME,
    edrpou_code: str = DEFAULT_EDRPOU_CODE,
    tabel_number: str = "",
    employees_per_page: int = 0,
) -> str:
    """
    Генерує HTML табеля для заданого місяця та року.

    Args:
        month: Місяць (1-12)
        year: Рік
        institution_name: Назва установи
        edrpou_code: Код ЄДРПОУ
        tabel_number: Номер табеля
        employees_per_page: Кількість працівників на сторінці (0 = без обмеження)

    Returns:
        str: HTML код табеля
    """
    employees: list[EmployeeData] = []
    _, month_days = calendar.monthrange(year, month)
    responsible_person = ""
    department_head = ""
    hr_person = ""

    try:
        with get_db_context() as db:
            # Get settings
            hr_employee_id = SystemSettings.get_value(db, "hr_signature_id", None)
            if hr_employee_id and hr_employee_id not in ("None", "none", ""):
                if str(hr_employee_id).startswith("custom:"):
                    # Користувацьке ім'я - форматуємо напряму
                    custom_name = str(hr_employee_id)[7:]
                    hr_person = format_initials(custom_name)
                else:
                    hr_staff = db.query(Staff).get(int(hr_employee_id))
                    if hr_staff:
                        hr_person = format_initials(hr_staff.pib_nom)

            # Get active staff
            # Include deactivated employees if their contract ends within the current month
            # Exclude them if we're in a month after their contract ended
            month_start = date(year, month, 1)
            month_end = date(year, month, month_days)

            staff_list = db.query(Staff).filter(
                # Active employees OR employees whose contract ended this month
                (Staff.is_active == True) |
                (Staff.term_end >= month_start)
            ).order_by(Staff.pib_nom).all()

            # Find responsible person and department head
            for staff_member in staff_list:
                pos = staff_member.position.lower()
                if 'фахівець' in pos and not responsible_person:
                    responsible_person = format_initials(staff_member.pib_nom)
                
                if ('завідувач кафедри' in pos or 'в.о завідувача кафедри' in pos) and not department_head:
                    department_head = format_initials(staff_member.pib_nom)

                if responsible_person and department_head:
                    break

            for staff in staff_list:
                # Get attendance records for this month
                month_start = date(year, month, 1)
                month_end = date(year, month, month_days)

                attendance = db.query(Attendance).filter(
                    Attendance.staff_id == staff.id,
                    Attendance.date >= month_start,
                    Attendance.date <= month_end,
                ).all()

                # Get vacation documents with processed status
                vacations = db.query(Document).filter(
                    Document.staff_id == staff.id,
                    Document.doc_type.in_([
                        DocumentType.VACATION_PAID,
                        DocumentType.VACATION_UNPAID
                    ]),
                    Document.status == DocumentStatus.PROCESSED,
                    Document.date_end >= month_start,
                    Document.date_start <= month_end,
                ).all()

                emp_data = get_employee_data(staff, month, year, attendance, vacations, db)
                employees.append(emp_data)

    except Exception as e:
        # Log the error for debugging
        logger.exception("Error generating tabel data")
        # Re-raise to be handled by caller
        raise

    # If no pagination needed, render single page
    if employees_per_page <= 0:
        employees_per_page = len(employees)  # All on one page

    # Split employees into pages
    employee_dicts = [emp.__dict__ for emp in employees]
    pages = []
    for i in range(0, len(employee_dicts), employees_per_page):
        page_employees = employee_dicts[i:i + employees_per_page]
        # Calculate page totals
        page_emp_data = [EmployeeData(**emp) for emp in page_employees]
        page_totals = get_tabel_totals(page_emp_data, month_days)

        # Prepare template data for this page
        # Get show_monthly_totals setting
        show_monthly_totals = True
        try:
            with get_db_context() as settings_db:
                show_monthly_totals_raw = SystemSettings.get_value(settings_db, "tabel_show_monthly_totals", True)
                # Convert to boolean
                if isinstance(show_monthly_totals_raw, str):
                    show_monthly_totals = show_monthly_totals_raw.lower() in ("true", "1", "yes")
                else:
                    show_monthly_totals = bool(show_monthly_totals_raw)
        except Exception:
            pass

        template_data = {
            'institution_name': institution_name,
            'edrpou_code': edrpou_code,
            'tabel_number': tabel_number,
            'month_name': MONTHS_UKR[month - 1],
            'month_genitive': MONTHS_GENITIVE[month - 1],
            'year': year,
            'month_days': month_days,
            'employees': page_employees,
            'page_number': len(pages) + 1,
            'total_pages': (len(employee_dicts) + employees_per_page - 1) // employees_per_page,
            'show_monthly_totals': show_monthly_totals,
            'totals': {
                'work_days': page_totals.work_days,
                'work_hours': page_totals.work_hours,
                'days': page_totals.days,
                'absence': page_totals.absence.to_dict(),
                'overtime': page_totals.__dict__.get('overtime', ''),
                'night': page_totals.__dict__.get('night', ''),
                'evening': page_totals.__dict__.get('evening', ''),
                'weekend': page_totals.__dict__.get('weekend', ''),
            },
            'responsible_person': responsible_person,
            'department_head': department_head,
            'hr_person': hr_person,
        }

        # Add missing fields
        for emp_data in template_data['employees']:
            if 'absence' not in emp_data:
                emp_data['absence'] = AbsenceTotals().to_dict()
            if 'totals' not in emp_data:
                emp_data['totals'] = {
                    'work_days': 0,
                    'work_hours': '0,00',
                    'first_half_work_days': 0,
                    'first_half_work_hours': '0,00',
                    'second_half_work_days': 0,
                    'second_half_work_hours': '0,00',
                    'first_half_overtime': '',
                    'first_half_night': '',
                    'first_half_evening': '',
                    'first_half_weekend': '',
                    'second_half_overtime': '',
                    'second_half_night': '',
                }

        # Render this page
        env = get_jinja_env()
        template = env.get_template('tabel_template.html')
        page_html = template.render(**template_data)
        # Wrap in page container for proper preview separation
        # Add page-break class to grid-container for PDF pagination (but not on first page)
        page_break_class = " page-break" if len(pages) > 0 else ""
        page_html = page_html.replace(
            '<div class="ritz grid-container"',
            f'<div class="ritz grid-container{page_break_class}"'
        )
        pages.append(f'<div class="page-container">{page_html}</div>')

    # Join pages with separator (hidden during print)
    html = f'\n<div class="page-separator"></div>\n'.join(pages)

    return html


def save_tabel_to_file(
    html: str,
    month: int,
    year: int,
    output_dir: Path | None = None,
) -> Path:
    """
    Зберігає табель у файл.

    Args:
        html: HTML код табеля
        month: Місяць
        year: Рік
        output_dir: Директорія для збереження

    Returns:
        Path: Шлях до збереженого файлу
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / "storage" / "tabels"

    output_dir.mkdir(parents=True, exist_ok=True)

    month_name = MONTHS_UKR[month - 1].lower()
    filename = f"tabel_{year}_{month:02d}_{month_name}.html"
    filepath = output_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    return filepath
