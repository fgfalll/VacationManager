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
        # Special handling for common position phrases (both nominative and genitive forms)
        # If the phrase is already in genitive, return it unchanged
        phrase_rules = {
            # Nominative -> Genitive
            'В.о завідувач кафедри': 'В.о завідувача кафедри',
            'В.о. завідувач кафедри': 'В.о. завідувача кафедри',
            'в.о завідувач кафедри': 'в.о завідувача кафедри',
            'завідувач кафедри': 'завідувача кафедри',
            'Завідувач кафедри': 'Завідувача кафедри',
            'професор кафедри': 'професора кафедри',
            'Професор кафедри': 'Професора кафедри',
            'доцент кафедри': 'доцента кафедри',
            'Доцент кафедри': 'Доцента кафедри',
            # Already genitive - return unchanged
            'В.о завідувача кафедри': 'В.о завідувача кафедри',
            'В.о. завідувача кафедри': 'В.о. завідувача кафедри',
            'завідувача кафедри': 'завідувача кафедри',
            'Завідувача кафедри': 'Завідувача кафедри',
            'професора кафедри': 'професора кафедри',
            'Професора кафедри': 'Професора кафедри',
            'доцента кафедри': 'доцента кафедри',
            'Доцента кафедри': 'Доцента кафедри',
        }

        if text in phrase_rules:
            return phrase_rules[text]

        words = text.split()
        result = []

        for word in words:
            # Special handling for Ukrainian names first
            genitive = self._inflect_name_genitive(word)
            result.append(genitive)

        return " ".join(result)

    def _inflect_name_genitive(self, word: str) -> str:
        """
        Спеціальна обробка для відмінювання українських імен у родовий відмінок.

        Args:
            word: Слово у називному відмінку

        Returns:
            Слово у родовому відмінку
        """
        # Слова, які вже в родовому відмінку - не змінюємо
        genitive_words = {
            # Department/institution types
            'кафедри', 'інженерії', 'технологій', 'науки', 'мистецтв',
            'факультету', 'інституту', 'коледжу', 'академії', 'університету',
            'управління', 'відділу', 'сектору', 'групи', 'лабораторії',
            'центру', 'бюро', 'офісу', 'департаменту', 'міністерства',
            'комітету', 'ради', 'комісії', 'асоціації', 'спілки',
            # Adjectives (already in genitive)
            'нафтогазової', 'комп\'ютерних', 'інформаційних', 'програмних',
            'економічних', 'гуманітарних', 'природничих', 'технічних',
            'теоретичної', 'прикладної', 'загальної', 'спеціальної',
            # Position titles in genitive form - don't re-inflect
            'завідувача', 'професора', 'доцента', 'асистента', 'викладача',
            'старшого', 'лаборанта', 'ректора', 'декана', 'директора',
            # Conjunctions and particles - never inflect
            'та', 'і', 'або', 'й', 'але', 'бо', 'тобто', 'що', 'як',
        }

        # Якщо слово вже в родовому відмінку або не потребує змін
        word_lower = word.lower()
        if word_lower in genitive_words:
            return word

        # Спеціальні правила для посад (називний → родовий)
        position_rules = [
            (r'^завідувач$', 'завідувача'),
            (r'^Завідувач$', 'Завідувача'),
            (r'^професор$', 'професора'),
            (r'^Професор$', 'Професора'),
            (r'^доцент$', 'доцента'),
            (r'^Доцент$', 'Доцента'),
            (r'^асистент$', 'асистента'),
            (r'^Асистент$', 'Асистента'),
            (r'^викладач$', 'викладача'),
            (r'^Викладач$', 'Викладача'),
            (r'^старший$', 'старшого'),
            (r'^Старший$', 'Старшого'),
            (r'^лаборант$', 'лаборанта'),
            (r'^Лаборант$', 'Лаборанта'),
            (r'^кафедра$', 'кафедри'),
            (r'^Кафедра$', 'Кафедри'),
        ]

        import re
        for pattern, replacement in position_rules:
            if re.match(pattern, word):
                return replacement

        # Спеціальні правила для українських імен (родовий відмінок)
        name_rules = [
            # закінчення -ик → -ика (прізвища)
            (r'^(.*[а-яА-Я])ік$', r'\1ика'),
            (r'^(.*[а-яА-Я])чук$', r'\1чука'),
            (r'^(.*[а-яА-Я])енко$', r'\1енка'),

            # чоловічі імена (називний → родовий)
            (r'^(.*[а-яА-Я])й$', r'\1я'),    # Василь → Василя
            (r'^(.*[а-яА-Я])ій$', r'\1я'),   # Андрій → Андрія

            # жіночі імена (називний → родовий)
            (r'^(.*[а-яА-Я])а$', r'\1и'),   # Ганна → Ганни

            # по батькові (patronymics)
            (r'^(.*[а-яА-Я])ович$', r'\1овича'),  # Іванович → Івановича
            (r'^(.*[а-яА-Я])евич$', r'\1евича'),  # Петрович → Петровича
            (r'^(.*[а-яА-Я])івна$', r'\1івни'),   # Іванівна → Іванівни
            (r'^(.*[а-яА-Я])ївна$', r'\1ївни'),   # Петрівна → Петрівни

            # прізвища на -ський, -цький
            (r'^(.*[а-яА-Я])ський$', r'\1ського'),
            (r'^(.*[а-яА-Я])цький$', r'\1цького'),

            # прізвища на -ко
            (r'^(.*[а-яА-Я])ко$', r'\1ка'),
        ]

        for pattern, replacement in name_rules:
            if re.match(pattern, word):
                return re.sub(pattern, replacement, word)

        # Якщо жодне правило не підійшло, використовуємо pymorphy3
        parsed = self.morph.parse(word)
        if not parsed:
            return word

        best_parse = parsed[0]
        inflected = best_parse.inflect({"gent"})

        if inflected:
            return inflected.word.capitalize()
        else:
            return word

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
            # Special handling for Ukrainian names
            dative = self._inflect_name_dative(word)
            result.append(dative)

        return " ".join(result)

    def _inflect_name_dative(self, word: str) -> str:
        """
        Спеціальна обробка для відмінювання українських імен у давальний відмінок.

        Args:
            word: Слово у називному відмінку

        Returns:
            Слово у давальному відмінку
        """
        # Спеціальні правила для українських імен
        rules = [
            # закінчення -ик → -ику (прізвища на -ик, -чук, -енко тощо)
            (r'^(.*[а-яА-Я])ік$', r'\1ику'),
            (r'^(.*[а-яА-Я])чук$', r'\1чуку'),
            (r'^(.*[а-яА-Я])енко$', r'\1енку'),

            # чоловічі імена на -й, -ій (Василь, Андрій, Дмитро)
            (r'^(.*[а-яА-Я])й$', r'\1ю'),
            (r'^(.*[а-яА-Я])ій$', r'\1ю'),

            # жіночі імена на -а (Ганна, Олена, Марія)
            (r'^(.*[а-яА-Я])а$', r'\1і'),

            # по батькові на -ович, -евич, -івна, -ївна
            (r'^(.*[а-яА-Я])ович$', r'\1овичу'),
            (r'^(.*[а-яА-Я])евич$', r'\1евичу'),
            (r'^(.*[а-яА-Я])івна$', r'\1івні'),
            (r'^(.*[а-яА-Я])ївна$', r'\1ївні'),

            # прізвища на -ський, -цький
            (r'^(.*[а-яА-Я])ський$', r'\1ському'),
            (r'^(.*[а-яА-Я])цький$', r'\1цькому'),

            # прізвища на -ко (Петренко, Shevchenko)
            (r'^(.*[а-яА-Я])ко$', r'\1ку'),
        ]

        import re
        for pattern, replacement in rules:
            if re.match(pattern, word):
                return re.sub(pattern, replacement, word)

        # Якщо жодне правило не підійшло, використовуємо pymorphy3
        parsed = self.morph.parse(word)
        if not parsed:
            return word

        best_parse = parsed[0]
        inflected = best_parse.inflect({"datv"})

        if inflected:
            return inflected.word.capitalize()
        else:
            return word

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
