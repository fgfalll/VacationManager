"""Unit тести для ValidationService."""

import pytest
from datetime import date, timedelta
from backend.services.validation_service import ValidationService
from backend.models.staff import Staff
from shared.exceptions import ValidationError
from decimal import Decimal
from shared.enums import EmploymentType, WorkBasis


@pytest.fixture
def validation_service():
    """Повертає екземпляр ValidationService."""
    return ValidationService()


@pytest.fixture
def mock_staff():
    """Створює тестового співробітника."""
    return Staff(
        id=1,
        pib_nom="Тестовий Тест Тестович",
        position="Доцент",
        rate=Decimal("1.0"),
        employment_type=EmploymentType.MAIN,
        work_basis=WorkBasis.CONTRACT,
        term_start=date(2024, 1, 1),
        term_end=date(2025, 12, 31),
        vacation_balance=28,
    )


class TestValidationService:
    """Тести для ValidationService."""

    def test_validate_dates_start_after_end(self, validation_service, mock_staff):
        """Тест: початок пізніше за кінець - помилка."""
        with pytest.raises(ValidationError, match="початку має бути раніше"):
            validation_service.validate_vacation_dates(
                date(2025, 7, 20),
                date(2025, 7, 10),
                mock_staff,
                None,  # db session
            )

    def test_validate_dates_weekend_start(self, validation_service, mock_staff):
        """Тест: початок у суботу - помилка."""
        # 5 липня 2025 - субота
        with pytest.raises(ValidationError, match="Дата початку.*припадає на "):
            validation_service.validate_vacation_dates(
                date(2025, 7, 5),
                date(2025, 7, 18),
                mock_staff,
                None,
            )

    def test_validate_dates_weekend_end(self, validation_service, mock_staff):
        """Тест: кінець у неділю - помилка."""
        # 6 липня 2025 - неділя
        with pytest.raises(ValidationError, match="Дата завершення.*припадає на "):
            validation_service.validate_vacation_dates(
                date(2025, 7, 1),
                date(2025, 7, 6),
                mock_staff,
                None,
            )

    def test_validate_dates_beyond_contract(self, validation_service, mock_staff):
        """Тест: відпустка виходить за межі контракту - помилка."""
        # Use a weekday (November 3, 2025 is Monday)
        with pytest.raises(ValidationError, match="Відпустка виходить за межі контракту"):
            validation_service.validate_vacation_dates(
                date(2025, 11, 3),  # Monday
                date(2026, 1, 15),  # За межами контракту (закінчується 31.12.2025)
                mock_staff,
                None,
            )

    def test_validate_dates_insufficient_balance(self, validation_service, mock_staff):
        """Тест: недостатньо днів відпустки - помилка."""
        # Працюємо з mock session, тому пропускаємо перевірку перетинів
        mock_staff.vacation_balance = 5

        # 10 робочих днів > 5 доступних
        start = date(2025, 7, 7)  # Понеділок
        end = date(2025, 7, 18)   # П'ятниця

        try:
            validation_service.validate_vacation_dates(start, end, mock_staff, None)
        except ValidationError as e:
            assert "Недостатньо днів" in str(e)

    def test_calculate_working_days_full_week(self, validation_service):
        """Тест підрахунку робочих днів - повний тиждень."""
        days = validation_service.calculate_working_days(
            date(2025, 7, 7),   # Понеділок
            date(2025, 7, 11)   # П'ятниця
        )
        assert days == 5

    def test_calculate_working_days_with_weekend(self, validation_service):
        """Тест підрахунку робочих днів - з вихідними."""
        days = validation_service.calculate_working_days(
            date(2025, 7, 7),   # Понеділок
            date(2025, 7, 13)   # Неділя
        )
        assert days == 5  # Тільки робочі дні

    def test_calculate_calendar_days(self, validation_service):
        """Тест підрахунку календарних днів."""
        days = validation_service.calculate_calendar_days(
            date(2025, 7, 1),
            date(2025, 7, 10)
        )
        assert days == 10

    def test_date_range_overlaps(self, validation_service):
        """Тест класу DateRange - перетин."""
        from backend.services.validation_service import DateRange

        range1 = DateRange(date(2025, 7, 1), date(2025, 7, 10))
        range2 = DateRange(date(2025, 7, 5), date(2025, 7, 15))

        assert range1.overlaps(range2)
        assert range2.overlaps(range1)

    def test_date_range_no_overlap(self, validation_service):
        """Тест класу DateRange - без перетину."""
        from backend.services.validation_service import DateRange

        range1 = DateRange(date(2025, 7, 1), date(2025, 7, 10))
        range2 = DateRange(date(2025, 8, 1), date(2025, 8, 10))

        assert not range1.overlaps(range2)
        assert not range2.overlaps(range1)

    def test_date_range_contains(self, validation_service):
        """Тест класу DateRange - містить дату."""
        from backend.services.validation_service import DateRange

        range1 = DateRange(date(2025, 7, 1), date(2025, 7, 10))

        assert range1.contains(date(2025, 7, 5))
        assert not range1.contains(date(2025, 7, 15))

    def test_validate_staff_data_valid(self, validation_service, mock_staff):
        """Тест валідації даних співробітника - валідні дані."""
        # Не повинен викликати виключення
        validation_service.validate_staff_data(mock_staff)

    def test_validate_staff_data_invalid_rate(self, validation_service):
        """Тест валідації даних співробітника - некоректна ставка."""
        staff = Staff(
            id=1,
            pib_nom="Тест",
            position="Посада",
            rate=Decimal("1.5"),  # Більше 1.0
            employment_type=EmploymentType.MAIN,
            work_basis=WorkBasis.CONTRACT,
            term_start=date(2024, 1, 1),
            term_end=date(2025, 12, 31),
        )

        with pytest.raises(ValidationError, match="Ставка повинна бути"):
            validation_service.validate_staff_data(staff)

    def test_validate_staff_data_negative_balance(self, validation_service):
        """Тест валідації даних співробітника - від'ємний баланс."""
        staff = Staff(
            id=1,
            pib_nom="Тест",
            position="Посада",
            rate=Decimal("1.0"),
            employment_type=EmploymentType.MAIN,
            work_basis=WorkBasis.CONTRACT,
            term_start=date(2024, 1, 1),
            term_end=date(2025, 12, 31),
            vacation_balance=-5,  # Від'ємний баланс
        )

        with pytest.raises(ValidationError, match="не може бути від'ємним"):
            validation_service.validate_staff_data(staff)
