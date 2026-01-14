"""Сервіс для морфологічних перетворень українських ПІБ та посад.

Використовує бібліотеку pymorphy3 з українськими словниками для
відмінювання слів відповідно до правил української мови.
"""

from functools import lru_cache
from typing import Final

import pymorphy3
from pymorphy3.tagset import OpencorporaTag

from shared.enums import DocumentType
from shared.exceptions import GrammarError

# Відмінки української мови
CASES: Final = {
    "NOM": "naz",  # Називний
    "GEN": "gen",  # Родовий
    "DAT": "dat",  # Давальний
    "ACC": "acc",  # Знахідний
    "INS": "ins",  # Орудний
    "LOC": "loc",  # Місцевий
}


class GrammarService:
    """
    Сервіс для морфологічних перетворень української мови.

    Використовує pymorphy3 з українськими словниками для відмінювання
    ПІБ, посад та інших слів.

    Example:
        >>> grammar = GrammarService()
        >>> grammar.to_genitive("Іванов Іван Іванович")
        "Іванова Івана Івановича"
        >>> grammar.format_for_document("Ляшенко Анна Сергіївна", DocumentType.VACATION_PAID)
        "Анна ЛЯШЕНКО"
    """

    def __init__(self) -> None:
        """Ініціалізує морфологічний аналізатор для української мови."""
        try:
            self.morph = pymorphy3.MorphAnalyzer(lang="uk")
        except Exception as e:
            raise GrammarError(f"Не вдалося ініціалізувати морфологічний аналізатор: {e}") from e

    @lru_cache(maxsize=2048)
    def to_genitive(self, text: str) -> str:
        """
        Перетворює текст у родовий відмінок.

        Args:
            text: Текст у називному відмінку

        Returns:
            Текст у родовому відмінку

        Example:
            >>> grammar.to_genitive("Іванов Іван Іванович")
            "Іванова Івана Івановича"
            >>> grammar.to_genitive("доцент")
            "доцента"
        """
        words = text.split()
        result = []

        for word in words:
            parsed = self.morph.parse(word)
            if not parsed:
                result.append(word)
                continue

            # Отримуємо найбільш ймовірний варіант
            best_parse = parsed[0]
            inflected = best_parse.inflect({"gent"})

            if inflected:
                result.append(inflected.word.capitalize())
            else:
                # Якщо не вдалося відмінювати, залишаємо оригінал
                result.append(word)

        return " ".join(result)

    @lru_cache(maxsize=2048)
    def to_dative(self, text: str) -> str:
        """
        Перетворює текст у давальний відмінок.

        Args:
            text: Текст у називному відмінку

        Returns:
            Текст у давальному відмінку

        Example:
            >>> grammar.to_dative("Ганна Олійник")
            "Ганні Олійник"
            >>> grammar.to_dative("ректор")
            "ректору"
        """
        words = text.split()
        result = []

        for word in words:
            parsed = self.morph.parse(word)
            if not parsed:
                result.append(word)
                continue

            best_parse = parsed[0]
            inflected = best_parse.inflect({"datv"})

            if inflected:
                result.append(inflected.word.capitalize())
            else:
                result.append(word)

        return " ".join(result)

    @lru_cache(maxsize=1024)
    def format_for_document(self, full_name: str, doc_type: DocumentType) -> str:
        """
        Форматує ПІБ згідно з типом документа.

        Правила форматування:
            - Відпустка (оплачувана/без збереження): "Ім'я ПРІЗВИЩЕ" (наприклад, "Анна ЛЯШЕНКО")
            - Продовження контракту: "ПРІЗВИЩЕ Ім'я" (наприклад, "СУДАКОВ Андрій")

        Args:
            full_name: ПІБ у форматі "Прізвище Ім'я По-батькові"
            doc_type: Тип документа

        Returns:
            Відформатоване ПІБ

        Example:
            >>> grammar.format_for_document("Ляшенко Анна Сергіївна", DocumentType.VACATION_PAID)
            "Анна ЛЯШЕНКО"
            >>> grammar.format_for_document("Судаков Андрій Олександрович", DocumentType.TERM_EXTENSION)
            "СУДАКОВ Андрій"
        """
        parts = full_name.split()

        if len(parts) < 2:
            # Якщо лише прізвище, повертаємо uppercase
            return full_name.upper()

        surname, name = parts[0], parts[1]

        if doc_type in (DocumentType.VACATION_PAID, DocumentType.VACATION_UNPAID):
            # Для відпустки: "Ім'я ПРІЗВИЩЕ"
            return f"{name} {surname.upper()}"
        elif doc_type == DocumentType.TERM_EXTENSION:
            # Для продовження контракту: "ПРІЗВИЩЕ Ім'я"
            return f"{surname.upper()} {name}"

        return full_name

    @lru_cache(maxsize=512)
    def get_gender(self, full_name: str) -> str:
        """
        Визначає стать за ПІБ.

        Args:
            full_name: ПІБ для аналізу

        Returns:
            "male", "female" або "unknown"

        Example:
            >>> grammar.get_gender("Іванов Іван Іванович")
            "male"
            >>> grammar.get_gender("Коваленко Анна Іванівна")
            "female"
        """
        # Аналізуємо прізвище
        surname = full_name.split()[0] if full_name.split() else ""
        parsed = self.morph.parse(surname)

        if not parsed:
            return "unknown"

        best_parse = parsed[0]

        if "masc" in best_parse.tag:
            return "male"
        elif "femn" in best_parse.tag:
            return "female"

        return "unknown"

    def decline_position(self, position: str, case: str = "gen") -> str:
        """
        Відмінює назву посади.

        Args:
            position: Назва посади у називному відмінку
            case: Відмінок ("gen" - родовий, "dat" - давальний)

        Returns:
            Назва посади у вказаному відмінку

        Example:
            >>> grammar.decline_position("доцент", "gen")
            "доцента"
            >>> grammar.decline_position("професор", "dat")
            "професору"
        """
        if case == "gen":
            return self.to_genitive(position)
        elif case == "dat":
            return self.to_dative(position)
        return position

    @lru_cache(maxsize=128)
    def format_payment_period(self, year: int, month: int, first_half: bool = True) -> str:
        """
        Форматує період оплати у вигляді тексту.

        Args:
            year: Рік
            month: Місяць (1-12)
            first_half: True - перша половина місяця, False - друга

        Returns:
            Текст періоду оплати

        Example:
            >>> grammar.format_payment_period(2025, 6, True)
            "у першій половині червня"
            >>> grammar.format_payment_period(2025, 6, False)
            "у другій половині червня"
        """
        months_uk = [
            "січня", "лютого", "березня", "квітня", "травня", "червня",
            "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
        ]

        month_name = months_uk[month - 1]
        half = "першій" if first_half else "другій"

        return f"у {half} половині {month_name}"

    def clear_cache(self) -> None:
        """Очищає кеш LRU."""
        self.to_genitive.cache_clear()
        self.to_dative.cache_clear()
        self.format_for_document.cache_clear()
        self.get_gender.cache_clear()
        self.format_payment_period.cache_clear()
