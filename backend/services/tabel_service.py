"""Сервіс для генерації табеля обліку робочого часу."""

import calendar
import decimal
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from sqlalchemy import and_, or_

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

# WeasyPrint executable path
WEASYPRINT_EXE = Path(__file__).parent.parent.parent / 'weasyprint' / 'dist' / 'weasyprint.exe'


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


def get_jinja_env_correction() -> Environment:
    """Get Jinja2 environment with template loader for correction tabel."""
    # Templates are in desktop/templates/tabel_corection/
    template_dir = Path(__file__).parent.parent.parent / "desktop" / "templates" / "tabel_corection"
    return Environment(loader=FileSystemLoader(str(template_dir)))


def format_hours_decimal(hours: Decimal) -> str:
    """Форматує години для відображення (наприклад, 8:15 або 4:30)."""
    total_minutes = int(float(hours) * 60)
    hrs = total_minutes // 60
    mins = total_minutes % 60
    return f"{hrs}:{mins:02d}"


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
    is_correction: bool = False,
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

    Для корегуючого табеля:
    - Дні перед початком контракту: закреслені (новий працівник ретроактивно)
    - Дні після початку контракту: Р (робочі дні)
    - Кінцеві дати контракту: НЕ закреслюються

    Args:
        current_date: Поточна дата
        staff: Об'єкт працівника
        attendance_records: Список записів відвідуваності
        vacations: Список документів відпусток
        weekends: Множина вихідних днів тижня
        is_correction: True якщо це корегуючий табель

    Returns:
        DayStatus: Статус дня
    """
    # For correction mode: only strikethrough BEFORE contract start (retroactive employees)
    # End dates are NOT strikethrough in correction mode
    if is_correction:
        if current_date < staff.term_start:
            # Before contract started - strikethrough, empty
            return DayStatus(code="", strikethrough=True, disabled=True)
        # After contract started (or after end) - show as normal work day
        # No strikethrough for end dates in correction mode
    else:
        # Normal mode: strikethrough for both before start AND after end
        if current_date < staff.term_start:
            return DayStatus(code="", strikethrough=True, disabled=True)
        if current_date > staff.term_end:
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
    is_correction: bool = False,
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
        is_correction: True якщо це корегуючий табель

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

        # Get work hours per day (handle both "8" and "8:15" formats)
        hours_raw = SystemSettings.get_value(db, "tabel_work_hours_per_day", "8")
        try:
            hours_str = str(hours_raw).strip()
            if ':' in hours_str:
                # Parse "8:15" format to decimal hours (8.25)
                parts = hours_str.split(':')
                hours = int(parts[0])
                minutes = int(parts[1]) if len(parts) > 1 else 0
                work_hours_per_day = hours + minutes / 60
            else:
                work_hours_per_day = float(hours_str) if hours_str else 8.0
        except (ValueError, TypeError):
            work_hours_per_day = 8.0

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
        day_status = get_day_status(current_date, staff, attendance_records, vacations, is_correction=is_correction)
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
            'work_days': work_days_first_half + work_days_second_half if work_days_first_half + work_days_second_half > 0 else '',
            'work_hours': total_hours,
            'first_half_work_days': work_days_first_half if work_days_first_half > 0 else '',
            'first_half_work_hours': first_half_hours,
            'second_half_work_days': work_days_second_half if work_days_second_half > 0 else '',
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
        # Ensure emp.totals is a dict (fix type corruption issues)
        if not isinstance(emp.totals, dict):
            logger.warning(f"emp.totals is {type(emp.totals)}, resetting to empty dict")
            emp.totals = {}

        # Handle empty string for work_days
        work_days = emp.totals.get('work_days', 0)
        if work_days and str(work_days).strip():
            totals.work_days += int(work_days)

        # Add to total hours (only for employees with hours calculated)
        try:
            work_hours = str(emp.totals['work_hours']).strip()
            if work_hours:  # Only parse if not empty
                # Handle both "8,25" and "8:15" formats
                if ':' in work_hours:
                    # Parse "8:15" format to decimal hours (8.25)
                    parts = work_hours.split(':')
                    hours = int(parts[0])
                    minutes = int(parts[1]) if len(parts) > 1 else 0
                    emp_hours = Decimal(str(hours + minutes / 60))
                else:
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
    is_correction: bool = False,
    correction_month: int | None = None,
    correction_year: int | None = None,
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
        is_correction: True для корегуючого табеля
        correction_month: Місяць, що коригується (для корегуючих табелів)
        correction_year: Рік, що коригується (для корегуючих табелів)

    Returns:
        str: HTML код табеля
    """
    employees: list[EmployeeData] = []
    _, month_days = calendar.monthrange(year, month)
    responsible_person = ""
    department_head = ""
    hr_person = ""
    department_name = ""

    logger.info(f"Starting generate_tabel_html: month={month}, year={year}, is_correction={is_correction}")

    try:
        with get_db_context() as db:
            # Get department name from settings
            department_name = SystemSettings.get_value(db, "department_name", "")

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

            month_start = date(year, month, 1)
            month_end = date(year, month, month_days)

            if is_correction:
                # CORRECTION MODE: Get attendance records for dates BEFORE the selected month
                # This shows retroactive entries that were added after the fact
                correction_attendance = db.query(Attendance).filter(
                    Attendance.date < month_start,
                ).order_by(Attendance.date).all()

                # Group by staff_id and get unique staff members with correction entries
                staff_ids_with_corrections = set()
                for att in correction_attendance:
                    staff_ids_with_corrections.add(att.staff_id)

                # Get staff records for these employees
                staff_list = db.query(Staff).filter(
                    Staff.id.in_(staff_ids_with_corrections)
                ).order_by(Staff.pib_nom).all() if staff_ids_with_corrections else []

                # Find responsible person and department head (from active staff)
                all_active_staff = db.query(Staff).filter(
                    Staff.is_active == True,
                    Staff.term_end >= month_start
                ).all()
                for staff_member in all_active_staff:
                    pos = staff_member.position.lower()
                    if 'фахівець' in pos and not responsible_person:
                        responsible_person = format_initials(staff_member.pib_nom)

                    if ('завідувач кафедри' in pos or 'в.о завідувача кафедри' in pos) and not department_head:
                        department_head = format_initials(staff_member.pib_nom)

                    if responsible_person and department_head:
                        break

                # Group attendance by staff for easy lookup
                attendance_by_staff = {}
                for att in correction_attendance:
                    if att.staff_id not in attendance_by_staff:
                        attendance_by_staff[att.staff_id] = []
                    attendance_by_staff[att.staff_id].append(att)

                # Generate employee data for each staff with corrections
                for staff in staff_list:
                    attendance = attendance_by_staff.get(staff.id, [])

                    # Get correction month/year from first attendance record
                    if attendance:
                        corr_month = attendance[0].date.month
                        corr_year = attendance[0].date.year
                        # Use correction month for vacation lookup
                        corr_month_start = date(corr_year, corr_month, 1)
                        corr_month_end = date(corr_year, corr_month, calendar.monthrange(corr_year, corr_month)[1])
                    else:
                        corr_month_start = month_start
                        corr_month_end = month_end

                    # Get vacation documents that overlap with correction period
                    vacations = db.query(Document).filter(
                        Document.staff_id == staff.id,
                        Document.doc_type.in_([
                            DocumentType.VACATION_PAID,
                            DocumentType.VACATION_UNPAID
                        ]),
                        Document.status == DocumentStatus.PROCESSED,
                        Document.date_end >= corr_month_start,
                        Document.date_start <= corr_month_end,
                    ).all()

                    # Use the correction month for generating data
                    corr_month_for_data = attendance[0].date.month if attendance else month
                    corr_year_for_data = attendance[0].date.year if attendance else year

                    emp_data = get_employee_data(
                        staff, corr_month_for_data, corr_year_for_data,
                        attendance, vacations, db, is_correction=True
                    )
                    employees.append(emp_data)

            else:
                # NORMAL MODE: Get employees whose contract is valid for current month
                staff_list = db.query(Staff).filter(
                    or_(
                        # Active employees with contract ending this month or later
                        and_(
                            Staff.is_active == True,
                            Staff.term_end >= month_start
                        ),
                        # Inactive employees whose contract ended this month
                        and_(
                            Staff.is_active == False,
                            Staff.term_end >= month_start,
                            Staff.term_end <= month_end
                        )
                    )
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
    logger.debug(f"Total employees: {len(employee_dicts)}, employees_per_page: {employees_per_page}")

    # Calculate date placeholders (needed for both populated and empty tabels)
    today = date.today()
    generation_date = today.strftime("%d.%m.%Y")
    month_start_formatted = date(year, month, 1).strftime("%d.%m.%Y")
    month_end_formatted = date(year, month, month_days).strftime("%d.%m.%Y")

    pages = []
    for i in range(0, len(employee_dicts), employees_per_page):
        page_employees = employee_dicts[i:i + employees_per_page]
        logger.debug(f"Processing page {i // employees_per_page + 1}, employees on page: {len(page_employees)}")

        # Calculate page totals
        page_emp_data = []
        for emp_dict in page_employees:
            try:
                # Debug output for each employee
                logger.debug(f"Employee totals type: {type(emp_dict.get('totals'))}, value: {emp_dict.get('totals')}")
                page_emp_data.append(EmployeeData(**emp_dict))
            except Exception as e:
                logger.error(f"Error creating EmployeeData: {e}, data: {emp_dict}")
                raise

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

        # For correction mode, calculate actual span of attendance records
        correction_start = ""
        correction_end = ""
        if is_correction:
            all_attendance_dates = []
            for emp in employees:
                for day in emp.days:
                    if day.code and not day.strikethrough:
                        # Calculate actual date for this day
                        day_num = emp.days.index(day) + 1
                        if day_num <= month_days:
                            actual_date = date(year, month, day_num)
                            all_attendance_dates.append(actual_date)
            if all_attendance_dates:
                correction_start = min(all_attendance_dates).strftime("%d.%m.%Y")
                correction_end = max(all_attendance_dates).strftime("%d.%m.%Y")

        # For correction tabels, use the correction month/year for title
        if is_correction and correction_month and correction_year:
            title_month = correction_month
            title_year = correction_year
        else:
            title_month = month
            title_year = year

        template_data = {
            'institution_name': institution_name,
            'edrpou_code': edrpou_code,
            'department_name': department_name,
            'month_name': MONTHS_UKR[title_month - 1],
            'month_genitive': MONTHS_GENITIVE[title_month - 1],
            'month_days': month_days,
            'generation_date': generation_date,
            'month_start': month_start_formatted,
            'month_end': month_end_formatted,
            'correction_start': correction_start,
            'correction_end': correction_end,
            'title_year': str(title_year),
            'title_month': title_month,
            'employees': page_employees,
            'page_number': len(pages) + 1,
            'total_pages': (len(employee_dicts) + employees_per_page - 1) // employees_per_page,
            'show_monthly_totals': show_monthly_totals,
            'is_correction': is_correction,
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
        if is_correction:
            env = get_jinja_env_correction()
        else:
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

    # If no employees, render empty template with just headers
    if not pages:
        # For correction tabels, use the correction month/year for title
        if is_correction and correction_month and correction_year:
            title_month = correction_month
            title_year = correction_year
        else:
            title_month = month
            title_year = year

        page_totals = get_tabel_totals([], month_days)
        template_data = {
            'institution_name': institution_name,
            'edrpou_code': edrpou_code,
            'department_name': department_name,
            'month_name': MONTHS_UKR[title_month - 1],
            'month_genitive': MONTHS_GENITIVE[title_month - 1],
            'month_days': month_days,
            'generation_date': generation_date,
            'month_start': month_start_formatted,
            'month_end': month_end_formatted,
            'correction_start': '',
            'correction_end': '',
            'title_year': str(title_year),
            'title_month': title_month,
            'employees': [],
            'page_number': 1,
            'total_pages': 1,
            'show_monthly_totals': False,
            'is_correction': is_correction,
            'totals': {
                'work_days': 0,
                'work_hours': '0,00',
                'days': [0] * 31,
                'absence': AbsenceTotals().to_dict(),
                'overtime': '',
                'night': '',
                'evening': '',
                'weekend': '',
            },
            'responsible_person': responsible_person,
            'department_head': department_head,
            'hr_person': hr_person,
        }
        if is_correction:
            env = get_jinja_env_correction()
        else:
            env = get_jinja_env()
        template = env.get_template('tabel_template.html')
        page_html = template.render(**template_data)
        page_html = page_html.replace(
            '<div class="ritz grid-container"',
            '<div class="ritz grid-container"'
        )
        pages.append(f'<div class="page-container">{page_html}</div>')

    # Join pages with separator (hidden during print)
    html = f'\n<div class="page-separator"></div>\n'.join(pages)

    return html


def save_tabel_to_file(
    html: str,
    month: int,
    year: int,
    generation_date: str = "",
    is_correction: bool = False,
    output_dir: Path | None = None,
) -> Path:
    """
    Зберігає табель у файл.

    Args:
        html: HTML код табеля
        month: Місяць
        year: Рік
        generation_date: Дата формування (dd.mm.yyyy)
        is_correction: True для корегуючого табеля
        output_dir: Директорія для збереження

    Returns:
        Path: Шлях до збереженого файлу
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / "storage" / "tabels"

    output_dir.mkdir(parents=True, exist_ok=True)

    month_name = MONTHS_UKR[month - 1]

    # Format: Табель_Січень_2026 or Табель_корегуючий_Січень_2026
    if is_correction:
        filename = f"Табель_корегуючий_{month_name}_{year}.html"
    else:
        filename = f"Табель_{month_name}_{year}.html"
    filepath = output_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    return filepath


def _wrap_tabel_html_for_pdf(html_content: str) -> str:
    """
    Wraps tabel HTML content with proper head and styles for PDF conversion.
    """
    return f'''<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <title>Табель обліку робочого часу</title>
    <link rel="stylesheet" href="sheet.css">
    <style>
        @page {{
            size: landscape A4;
            margin: 0.5cm;
        }}
        body {{
            font-family: "Times New Roman", Times, serif;
            font-size: 9pt;
            margin: 0;
            padding: 0;
            width: 297mm;
        }}
        .ritz.grid-container {{
            width: 130%;
            max-width: none;
            margin: 0;
        }}
        table.waffle {{
            border-collapse: collapse;
            width: 100%;
        }}
        table.waffle td, table.waffle th {{
            font-family: "Times New Roman", Times, serif;
        }}
        .page-break {{
            page-break-after: always;
        }}
        @media print {{
            .page-break:last-child {{
                page-break-after: avoid;
            }}
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>'''


def populate_title_docx(
    template_path: Path,
    output_path: Path,
    data: dict,
) -> None:
    """
    Populates a DOCX template with data and saves to output path.
    Uses docxtpl for proper merged cell handling.

    Args:
        template_path: Path to the DOCX template
        output_path: Path to save the populated DOCX
        data: Dictionary of placeholders to replace (Jinja2 syntax)
    """
    from docxtpl import DocxTemplate

    # Load template
    doc = DocxTemplate(str(template_path))

    # Render template with data (Jinja2 syntax - handles merged cells properly)
    doc.render(data)

    # Save output
    doc.save(str(output_path))


def convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> None:
    """
    Converts a DOCX file to PDF using LibreOffice or docx2pdf.

    Args:
        docx_path: Path to the DOCX file
        pdf_path: Path to save the PDF
    """
    import subprocess

    # First try docx2pdf (Windows-only, simpler)
    try:
        from docx2pdf import convert
        convert(str(docx_path), str(pdf_path))
        logger.info("Converted DOCX to PDF using docx2pdf")
        return
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"docx2pdf failed: {e}")

    # Fall back to LibreOffice
    libreoffice_path = Path("C:/Program Files/LibreOffice/program/soffice.exe")

    if not libreoffice_path.exists():
        # Try alternative paths
        alternative_paths = [
            Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
            Path("/usr/bin/libreoffice"),
        ]
        for alt_path in alternative_paths:
            if alt_path.exists():
                libreoffice_path = alt_path
                break

    if not libreoffice_path.exists():
        raise RuntimeError(
            f"Для конвертації DOCX в PDF потрібно встановити docx2pdf:\n"
            f"pip install docx2pdf"
        )

    # Create temp directory for LibreOffice
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Run LibreOffice in headless mode to convert
        result = subprocess.run(
            [
                str(libreoffice_path),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(temp_dir_path),
                str(docx_path),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

        # Move the converted PDF to the output path
        pdf_temp_path = temp_dir_path / f"{docx_path.stem}.pdf"
        if pdf_temp_path.exists():
            shutil.move(str(pdf_temp_path), str(pdf_path))
        else:
            raise RuntimeError(f"PDF conversion failed: output file not found")


def merge_pdfs(pdf_paths: list[Path], output_path: Path) -> None:
    """
    Merges multiple PDF files into one.

    Args:
        pdf_paths: List of paths to PDF files to merge
        output_path: Path to save the merged PDF
    """
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()

    for pdf_path in pdf_paths:
        if pdf_path.exists():
            reader = PdfReader(str(pdf_path))
            for page in reader.pages:
                writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)


def generate_tabel_with_title(
    month: int,
    year: int,
    institution_name: str,
    edrpou_code: str,
    employees_per_page: int = 0,
    is_correction: bool = False,
    correction_month: int | None = None,
    correction_year: int | None = None,
    add_title_page: bool = True,
) -> tuple[str, Path, Path | None]:
    """
    Generates a tabel with an optional title page.

    This function:
    1. Generates the HTML tabel
    2. Populates the title page DOCX template (if enabled)
    3. Returns HTML, final path, and title page PDF path (if enabled)

    The UI should:
    - Load the HTML in web view
    - Capture PDF from web view
    - Merge with title page PDF using merge_pdfs()

    Args:
        month: Month number (1-12)
        year: Year
        institution_name: Name of the institution
        edrpou_code: EDRPOU code
        employees_per_page: Number of employees per page (0 = no limit)
        is_correction: True for correction tabel
        correction_month: Month being corrected (for correction tabels)
        correction_year: Year being corrected (for correction tabels)
        add_title_page: True to include title page

    Returns:
        tuple: (HTML content, output PDF path, title_page_pdf_path or None)
    """
    from backend.models.settings import SystemSettings
    from backend.models.staff import Staff

    # Get additional settings for title page
    with get_db_context() as db:
        department_name = SystemSettings.get_value(db, "dept_name", "")

        # Get responsible person (specialist) by ID
        specialist_id = SystemSettings.get_value(db, "dept_specialist_id", None)
        if specialist_id and str(specialist_id) not in ("None", "none", ""):
            if str(specialist_id).startswith("custom:"):
                responsible_person = str(specialist_id)[7:]
            else:
                specialist_staff = db.query(Staff).get(int(specialist_id))
                responsible_person = format_initials(specialist_staff.pib_nom) if specialist_staff else ""
        else:
            responsible_person = ""

        # Get department head by ID
        dept_head_id = SystemSettings.get_value(db, "dept_head_id", None)
        if dept_head_id and str(dept_head_id) not in ("None", "none", ""):
            if str(dept_head_id).startswith("custom:"):
                department_head = str(dept_head_id)[7:]
            else:
                dept_head_staff = db.query(Staff).get(int(dept_head_id))
                department_head = format_initials(dept_head_staff.pib_nom) if dept_head_staff else ""
        else:
            department_head = ""

    # Month names
    month_name = MONTHS_UKR[month - 1]
    month_genitive = MONTHS_GENITIVE[month - 1]  # e.g., "січня" for January

    # Generate HTML tabel
    html = generate_tabel_html(
        month=month,
        year=year,
        institution_name=institution_name,
        edrpou_code=edrpou_code,
        employees_per_page=employees_per_page,
        is_correction=is_correction,
        correction_month=correction_month,
        correction_year=correction_year,
    )

    # Create output directory
    output_dir = Path(__file__).parent.parent.parent / "storage" / "tabels"
    output_dir.mkdir(parents=True, exist_ok=True)

    if is_correction:
        final_filename = f"Табель_корегуючий_{month_name}_{year}.pdf"
    else:
        final_filename = f"Табель_{month_name}_{year}.pdf"
    final_path = output_dir / final_filename

    if not add_title_page:
        # Return HTML only, without title page
        return html, final_path, None

    # Title page data - keys must match DOCX template placeholders
    title_data = {
        "institution_name": institution_name,
        "department_name": department_name,
        "month_name": month_name,
        "month_start": date(year, month, 1).strftime("%d.%m.%Y"),  # First day of month
        "month_end": date(year, month, month_days).strftime("%d.%m.%Y"),  # Last day of month
        "year": str(year),
        "edrpou_code": edrpou_code,
        "generation_date": date.today().strftime("%d.%m.%Y"),
        "responsible_person": responsible_person,
        "department_head": department_head,
    }

    # For correction tabel, add correction period placeholders
    if is_correction:
        # Get min and max dates from correction attendance records
        with get_db_context() as db:
            correction_records = db.query(Attendance).filter(
                Attendance.date < date(year, month, 1)
            ).all()

            if correction_records:
                # Find min and max dates
                min_date = min(r.date for r in correction_records)
                max_date = max(r.date for r in correction_records)

                correction_month = min_date.month
                correction_year = min_date.year
                _, days_in_month = calendar.monthrange(correction_year, correction_month)

                # Determine period range based on min/max dates
                if min_date.day <= 15:
                    # First half included
                    period_start = date(correction_year, correction_month, 1).strftime("%d.%m.%Y")
                else:
                    # Only second half
                    period_start = date(correction_year, correction_month, 16).strftime("%d.%m.%Y")

                if max_date.day >= 16:
                    # Second half included
                    period_end = date(correction_year, correction_month, days_in_month).strftime("%d.%m.%Y")
                else:
                    # Only first half
                    period_end = date(correction_year, correction_month, 15).strftime("%d.%m.%Y")

                correction_period_1 = period_start
                correction_period_2 = period_end
            else:
                correction_period_1 = ""
                correction_period_2 = ""

            title_data["correction_period_1"] = correction_period_1
            title_data["correction_period_2"] = correction_period_2

    # Get template path
    if is_correction:
        template_dir = Path(__file__).parent.parent.parent / "desktop" / "templates" / "tabel_corection"
        docx_template = template_dir / "Title_tabel_corection.docx"
    else:
        template_dir = Path(__file__).parent.parent.parent / "desktop" / "templates" / "tabel"
        docx_template = template_dir / "Title_tabel.docx"

    if docx_template.exists():
        # Create temp directory for title page
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Populate DOCX template
            docx_path = temp_path / "title.docx"
            populate_title_docx(docx_template, docx_path, title_data)

            # Convert to PDF
            title_pdf_path = temp_path / "title.pdf"
            convert_docx_to_pdf(docx_path, title_pdf_path)

            # Copy title page PDF to output directory (UI will merge later)
            title_page_output = output_dir / f"title_page_{final_filename}"
            shutil.copy(title_pdf_path, title_page_output)
            return html, final_path, title_page_output
    else:
        logger.warning(f"DOCX template not found: {docx_template}")
        return html, final_path, None
