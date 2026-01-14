"""Сервіс для розбору складних форматів дат.

Дозволяє парсити рядки з датами у різних форматах:
- Одиночна дата: "12 березня"
- Кілька дат через кому: "12, 14, 19 березня"
- Діапазони: "12-19 березня"
- Комбінація: "12, 14, 19-21 березня"
"""

import re
from datetime import date, datetime, timedelta
from typing import List, Tuple


class DateParser:
    """
    Парсер складних форматів дат.

    Example:
        >>> parser = DateParser()
        >>> dates = parser.parse("12, 14, 19-21 березня 2025")
        >>> print(dates)
        [date(2025, 3, 12), date(2025, 3, 14), date(2025, 3, 19), date(2025, 3, 20), date(2025, 3, 21)]
    """

    # Українські назви місяців
    MONTH_NAMES_UA = {
        "січня": 1,
        "лютого": 2,
        "березня": 3,
        "квітня": 4,
        "травня": 5,
        "червня": 6,
        "липня": 7,
        "серпня": 8,
        "вересня": 9,
        "жовтня": 10,
        "листопада": 11,
        "грудня": 12,
        # Скорочені варіанти
        "січ": 1,
        "лют": 2,
        "бер": 3,
        "квіт": 4,
        "трав": 5,
        "черв": 6,
        "лип": 7,
        "серп": 8,
        "вер": 9,
        "жовт": 10,
        "лист": 11,
        "груд": 12,
    }

    # Паттерни для розбору
    # "12 березня" або "12.03" або "12/03"
    SINGLE_DATE_PATTERN = r"(\d{1,2})\.?(\d{1,2})?(?:\.?(\d{2,4}))?|\s*([а-яА-ЯёЁїЇіІєЄґҐ]+)\s*"

    # "12-15" або "12-15 березня"
    RANGE_PATTERN = r"(\d{1,2})\s*[-–]\s*(\d{1,2})"

    def __init__(self, default_year: int | None = None):
        """
        Ініціалізує парсер.

        Args:
            default_year: Рік за замовчуванням (якщо не вказано в даті)
        """
        self.default_year = default_year or date.today().year

    def parse(self, date_string: str, default_year: int | None = None) -> List[date]:
        """
        Розбирає рядок з датами та повертає список дат.

        Args:
            date_string: Рядок з датами
            default_year: Рік за замовчуванням

        Returns:
            Список дат у хронологічному порядку

        Raises:
            ValueError: Якщо не вдалося розібрати дати
        """
        if not date_string or not date_string.strip():
            raise ValueError("Порожній рядок з датами")

        year = default_year or self.default_year

        # Очищаємо рядок
        date_string = date_string.strip()
        date_string = date_string.replace(",", " ")  # Замінуємо коми на пробіли

        # Розбираємо на частини по пробілах
        parts = date_string.split()

        dates = []
        i = 0

        while i < len(parts):
            part = parts[i]

            # Перевіряємо чи це діапазон "12-15" або "12-15 березня"
            range_match = re.match(self.RANGE_PATTERN, part)
            if range_match:
                start_day = int(range_match.group(1))
                end_day = int(range_match.group(2))

                # Перевіряємо чи наступне слово - місяць
                month = self._extract_month(parts, i)

                # Додаємо діапазон
                for day in range(start_day, end_day + 1):
                    try:
                        dates.append(date(year, month, day))
                    except ValueError as e:
                        raise ValueError(f"Некоректна дата: {day}.{month}.{year}") from e

                i += 1
                continue

            # Перевіряємо чи це одиночна дата
            day, month, extracted_year = self._parse_single_date(part, parts, i)
            if day:
                if extracted_year:
                    year = extracted_year
                try:
                    dates.append(date(year, month, day))
                except ValueError as e:
                    raise ValueError(f"Некоректна дата: {day}.{month}.{year}") from e
                i += 1
                continue

            # Якщо не розпізнали - пропускаємо
            i += 1

        if not dates:
            raise ValueError(f"Не вдалося розпізнати дати: {date_string}")

        # Сортуємо та видаляємо дублікати
        dates = sorted(set(dates))
        return dates

    def _parse_single_date(
        self, part: str, parts: List[str], index: int
    ) -> Tuple[int | None, int, int | None]:
        """
        Розбирає одиночну дату.

        Args:
            part: Частина що містить дату
            parts: Всі частини рядка
            index: Поточний індекс

        Returns:
            Кортеж (day, month, year) або (None, None, None)
        """
        # Спроба формату "ДД.ММ" або "ДД.ММ.РРРР"
        dot_match = re.match(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", part)
        if dot_match:
            day = int(dot_match.group(1))
            month = int(dot_match.group(2))
            year_str = dot_match.group(3)
            year = int(year_str) if year_str else None
            return day, month, year

        # Спроба формату "ДД/ММ" або "ДД/ММ/РРРР"
        slash_match = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", part)
        if slash_match:
            day = int(slash_match.group(1))
            month = int(slash_match.group(2))
            year_str = slash_match.group(3)
            year = int(year_str) if year_str else None
            return day, month, year

        # Спроба формату "12 березня"
        if part.isdigit():
            day = int(part)
            month = self._extract_month(parts, index)
            if month:
                return day, month, None

        return None, None, None

    def _extract_month(self, parts: List[str], index: int) -> int | None:
        """
        Витягує номер місяця з частин рядка.

        Args:
            parts: Всі частини рядка
            index: Поточний індекс

        Returns:
            Номер місяця (1-12) або None
        """
        # Перевіряємо наступне слово
        if index + 1 < len(parts):
            next_part = parts[index + 1].lower()
            if next_part in self.MONTH_NAMES_UA:
                return self.MONTH_NAMES_UA[next_part]

        # Перевіряємо поточне слово (якщо воно не число)
        current = parts[index].lower()
        if current in self.MONTH_NAMES_UA:
            return self.MONTH_NAMES_UA[current]

        # За замовчуванням - поточний місяць
        return date.today().month

    def format_as_string(self, dates: List[date], format_type: str = "readable") -> str:
        """
        Форматує список дат у рядок.

        Args:
            dates: Список дат
            format_type: Тип форматування ("readable", "compact", "full")

        Returns:
            Відформатований рядок
        """
        if not dates:
            return ""

        if format_type == "readable":
            return self._format_readable(dates)
        elif format_type == "compact":
            return self._format_compact(dates)
        elif format_type == "full":
            return ", ".join(d.strftime("%d.%m.%Y") for d in dates)
        else:
            return ", ".join(d.strftime("%d.%m") for d in dates)

    def _format_readable(self, dates: List[date]) -> str:
        """Форматує дати у читальному вигляді (12, 14, 19-21 березня)."""
        if not dates:
            return ""

        # Групуємо за місяцями
        grouped = {}
        for d in dates:
            key = (d.year, d.month)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(d.day)

        parts = []
        month_names = {
            1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
            5: "травня", 6: "червня", 7: "липня", 8: "серпня",
            9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня",
        }

        for (year, month), days in sorted(grouped.items()):
            # Знаходимо діапазони
            ranges = self._find_ranges(days)
            range_strs = []
            for r in ranges:
                if len(r) == 1:
                    range_strs.append(str(r[0]))
                else:
                    range_strs.append(f"{r[0]}–{r[-1]}")

            month_name = month_names[month]
            if year == self.default_year:
                parts.append(f"{', '.join(range_strs)} {month_name}")
            else:
                parts.append(f"{', '.join(range_strs)} {month_name} {year}")

        return ", ".join(parts)

    def _format_compact(self, dates: List[date]) -> str:
        """Форматує дати у компактному вигляді (12, 14, 19-21.03)."""
        if not dates:
            return ""

        # Групуємо за місяцями
        grouped = {}
        for d in dates:
            key = d.month
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(d.day)

        parts = []
        for month, days in sorted(grouped.items()):
            ranges = self._find_ranges(days)
            range_strs = []
            for r in ranges:
                if len(r) == 1:
                    range_strs.append(str(r[0]))
                else:
                    range_strs.append(f"{r[0]}–{r[-1]}")
            parts.append(f"{', '.join(range_strs)}.{month:02d}")

        return ", ".join(parts)

    def _find_ranges(self, days: List[int]) -> List[List[int]]:
        """Знаходить діапазони в списку днів."""
        if not days:
            return []

        sorted_days = sorted(set(days))
        ranges = []
        current_range = [sorted_days[0]]

        for i in range(1, len(sorted_days)):
            if sorted_days[i] == sorted_days[i - 1] + 1:
                # Продовжуємо діапазон
                current_range.append(sorted_days[i])
            else:
                # Завершуємо діапазон
                ranges.append(current_range)
                current_range = [sorted_days[i]]

        ranges.append(current_range)
        return ranges

    def count_calendar_days(self, dates: List[date]) -> int:
        """
        Рахує календарні дні з урахуванням діапазонів.

        Args:
            dates: Список дат

        Returns:
            Кількість календарних днів
        """
        if not dates:
            return 0

        # Знаходимо мінімум та максимум
        min_date = min(dates)
        max_date = max(dates)

        # Рахуємо дні в діапазоні
        return (max_date - min_date).days + 1

    def validate_date_range(self, dates: List[date]) -> Tuple[bool, List[str]]:
        """
        Валідує список дат.

        Args:
            dates: Список дат

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        if not dates:
            errors.append("Список дат порожній")
            return False, errors

        # Перевіряємо на вихідні
        for d in dates:
            if d.weekday() >= 5:  # Saturday=5, Sunday=6
                errors.append(f"{d.strftime('%d.%m.%Y')} випадає на вихідний")

        # Перевіряємо на перетин (тут не актуально, але може бути корисно)
        # Перевіряємо чи всі дати в одному році/місяці
        years = set(d.year for d in dates)
        if len(years) > 1:
            errors.append(f"Дати з різних років: {years}")

        return len(errors) == 0, errors


def parse_date_string(date_string: str, default_year: int | None = None) -> List[date]:
    """
    Зручна функція для парсингу рядка з датами.

    Args:
        date_string: Рядок з датами (наприклад, "12, 14, 19-21 березня")
        default_year: Рік за замовчуванням

    Returns:
        Список дат

    Example:
        >>> dates = parse_date_string("12, 14, 19-21 березня 2025")
        >>> print(dates)
        [datetime.date(2025, 3, 12), ...]
    """
    parser = DateParser(default_year)
    return parser.parse(date_string)
