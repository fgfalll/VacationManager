"""Модель відміток про явки/неявки працівників."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.staff import Staff


# Ukrainian timekeeping codes (наказ Мінпраці від 09.02.2021 № 55)
# Full list of valid attendance codes
ATTENDANCE_CODES = {
    # Явки на роботу
    "Р": "01",      # Години роботи, передбачені колдоговором
    "РС": "20",     # Години роботи працівників з неповним робочим днем/тижнем
    "ВЧ": "03",     # Вечірні години роботи
    "РН": "04",     # Нічні години роботи
    "НУ": "05",     # Надурочні години роботи
    "РВ": "06",     # Години роботи у вихідні та святкові дні

    # Відрядження
    "ВД": "10",     # Службове відрядження

    # Відпустки оплачувані
    "В": "08",      # Основна щорічна відпустка (ст.6 Закону)
    "Д": "09",      # Щорічна додаткова відпустка (ст.7, 8 Закону)
    "Ч": "11",      # Додаткова відпустка чорнобильцям (ст.20, 21, 30 Закону)
    "ТВ": "12",     # Творча відпустка (ст.16 Закону)
    "Н": "13",      # Додаткова відпустка у зв'язку з навчанням (ст.13, 14, 15, 151 Закону)
    "ДО": "16",     # Додаткова оплачувана відпустка працівникам з дітьми (ст.19 Закону)
    "ВП": "17",     # Відпустка у зв'язку з вагітністю та пологами / догляд до 3 років (ст.17, 18)
    "ДД": "18",     # Відпустка для догляду за дитиною до 6 років (ст.25 п.3)

    # Відпустки без збереження зарплати
    "НБ": "14",     # Відпустка без збереження зарплати у зв'язку з навчанням (п.12, 13, 17 ст.25)
    "ДБ": "15",     # Додаткова відпустка без збереження зарплати в обов'язковому порядку (ст.25)
    "НА": "21",     # Відпустка без збереження зарплати за згодою сторін (ст.26)
    "БЗ": "22",     # Інші відпустки без збереження заробітної плати

    # Неявки
    "НД": "20",     # Неявки у зв'язку з переведенням на неповний робочий день
    "НП": "21",     # Неявки у зв'язку з тимчасовим переведенням на інше підприємство
    "ІН": "22",     # Інший невідпрацьований час (виконання обов'язків, збори, донорські, відгул)
    "П": "23",      # Простої
    "ПР": "24",     # Прогули
    "С": "25",      # Масові невиходи (страйки)

    # Тимчасова непрацездатність
    "ТН": "26",     # Оплачувана тимчасова непрацездатність
    "НН": "27",     # Неоплачувана тимчасова непрацездатність

    # Інші причини неявок
    "НЗ": "28",     # Неявки з нез'ясованих причин
    "ІВ": "29",     # Інші види неявок за колективними договорами
    "І": "30",      # Інші причини неявок
}

# Reverse mapping: numeric code -> letter code
CODE_TO_LETTER = {v: k for k, v in ATTENDANCE_CODES.items()}

# Weekend days (Saturday=5, Sunday=6)
WEEKEND_DAYS = {5, 6}

# Standard work hours per day
STANDARD_WORK_HOURS = 8.0


class Attendance(Base, TimestampMixin):
    """
    Модель відмітки про явку/неявку працівника за конкретний день.

    Attributes:
        id: Унікальний ідентифікатор
        staff_id: ID працівника (зовнішній ключ)
        date: Дата відмітки
        code: Літерний код (Р, В, ДО, Л, тощо)
        hours: Кількість відпрацьованих годин (0-24)
        notes: Додаткові примітки
    """

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="Р",
        comment="Літерний код: Р-робота, В-відпустка, ДО-без збереження, Л-лікарняний",
    )
    hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        default=Decimal("8.0"),
        comment="Кількість годин (0-24)",
    )
    date_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Кінцева дата для діапазону (якщо None - одна дата)",
    )
    notes: Mapped[str | None] = mapped_column(String(255))
    deletion_notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Коментар при видаленні запису",
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="attendance_records")

    def __repr__(self) -> str:
        return f"<Attendance {self.staff_id}: {self.date} ({self.code})>"

    @property
    def code_number(self) -> str:
        """Повертає числовий код за наказом №55."""
        return ATTENDANCE_CODES.get(self.code, "")

    @property
    def is_weekend(self) -> bool:
        """Чи є день вихідним."""
        return self.date.weekday() in WEEKEND_DAYS

    @property
    def is_work_day(self) -> bool:
        """Чи є робочим днем (Р, РС, ВЧ, РН, НУ, РВ)."""
        return self.code in ("Р", "РС", "ВЧ", "РН", "НУ", "РВ")

    @property
    def is_vacation(self) -> bool:
        """Чи є оплачуваною відпусткою."""
        return self.code in ("В", "Д", "Ч", "ТВ", "Н", "ДО", "ВП", "ДД")

    @property
    def is_unpaid_vacation(self) -> bool:
        """Чи є відпусткою без збереження зарплати."""
        return self.code in ("НБ", "ДБ", "НА", "БЗ")

    @property
    def is_sick_leave(self) -> bool:
        """Чи є лікарняним (оплачуваним або ні)."""
        return self.code in ("ТН", "НН")

    @property
    def is_business_trip(self) -> bool:
        """Чи є відрядженням."""
        return self.code == "ВД"

    @property
    def is_absence(self) -> bool:
        """Чи є неявкою (прогули, страйки)."""
        return self.code in ("ПР", "С")

    @property
    def is_idle(self) -> bool:
        """Чи є простоєм."""
        return self.code == "П"

    @property
    def is_unexcused(self) -> bool:
        """Чи є неявкою з нез'яясованих причин."""
        return self.code == "НЗ"

    @property
    def is_part_time(self) -> bool:
        """Чи працює на умовах неповного робочого дня."""
        return self.code == "РС"

    @property
    def is_evening_hours(self) -> bool:
        """Чи є вечірніми годинами."""
        return self.code == "ВЧ"

    @property
    def is_night_hours(self) -> bool:
        """Чи є нічними годинами."""
        return self.code == "РН"

    @property
    def is_overtime(self) -> bool:
        """Чи є надурочними годинами."""
        return self.code == "НУ"

    @property
    def is_weekend_work(self) -> bool:
        """Чи є роботою у вихідні/святкові дні."""
        return self.code == "РВ"

    def format_hours(self) -> str:
        """Форматує години для відображення (наприклад, 8,00 або 4,00)."""
        return f"{float(self.hours):.2f}".replace(".", ",")
