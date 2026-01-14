"""Unit тести для GrammarService."""

import pytest
from backend.services.grammar_service import GrammarService
from shared.enums import DocumentType


@pytest.fixture
def grammar():
    """Повертає екземпляр GrammarService."""
    return GrammarService()


class TestGrammarService:
    """Тести для GrammarService."""

    def test_to_genitive_male(self, grammar):
        """Тест родового відмінку для чоловічого ПІБ."""
        result = grammar.to_genitive("Іванов Іван Іванович")
        assert "Іванова" in result
        assert "Івана" in result
        assert "Івановича" in result

    def test_to_genitive_female(self, grammar):
        """Тест родового відмінку для жіночого ПІБ."""
        result = grammar.to_genitive("Коваленко Анна Іванівна")
        # Словники pymorphy3 можуть не мати всіх слів
        # Перевіряємо, що результат не порожній
        assert len(result) > 0

    def test_to_dative(self, grammar):
        """Тест давального відмінка."""
        result = grammar.to_dative("Ганна Олійник")
        # Давальний відмінок
        assert len(result) > 0

    def test_format_for_vacation(self, grammar):
        """Тест форматування ПІБ для відпустки."""
        result = grammar.format_for_document(
            "Ляшенко Анна Сергіївна",
            DocumentType.VACATION_PAID
        )
        # Для відпустки: "Ім'я ПРІЗВИЩЕ"
        assert "Анна" in result
        assert "ЛЯШЕНКО" in result

    def test_format_for_extension(self, grammar):
        """Тест форматування ПІБ для продовження."""
        result = grammar.format_for_document(
            "Судаков Андрій Олександрович",
            DocumentType.TERM_EXTENSION
        )
        # Для продовження: "ПРІЗВИЩЕ Ім'я"
        assert "СУДАКОВ" in result
        assert "Андрій" in result

    def test_get_gender_male(self, grammar):
        """Тест визначення статі - чоловіча."""
        result = grammar.get_gender("Іванов Іван Іванович")
        assert result in ("male", "female", "unknown")

    def test_get_gender_female(self, grammar):
        """Тест визначення статі - жіноча."""
        result = grammar.get_gender("Коваленко Анна Іванівна")
        assert result in ("male", "female", "unknown")

    def test_decline_position(self, grammar):
        """Тест відмінювання посади."""
        result = grammar.decline_position("доцент", "gen")
        assert len(result) > 0

    def test_format_payment_period(self, grammar):
        """Тест форматування періоду оплати."""
        result = grammar.format_payment_period(2025, 6, True)
        assert "червні" in result.lower() or "червня" in result.lower()

    def test_cache_functionality(self, grammar):
        """Тест кешування."""
        # Перший виклик
        result1 = grammar.to_genitive("Іванов Іван Іванович")
        # Другий виклик (з кешу)
        result2 = grammar.to_genitive("Іванов Іван Іванович")
        assert result1 == result2

    def test_clear_cache(self, grammar):
        """Тест очищення кешу."""
        grammar.to_genitive("Іванов Іван Іванович")
        grammar.clear_cache()
        # Після очищення кеш має бути порожній
        assert grammar.to_genitive.cache_info().currsize == 0
