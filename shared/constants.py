"""Константи VacationManager."""

from pathlib import Path

# Шлях до кореневої директорії проекту
BASE_DIR = Path(__file__).parent.parent

# Назви файлів шаблонів (HTML для WYSIWYG редактора)
TEMPLATE_FILES = {
    "vacation_paid": "vacation_paid.html",
    "vacation_unpaid": "vacation_unpaid.html",
    "term_extension": "term_extension.html",
}

# Директорія для зберігання документів
STORAGE_DIR = BASE_DIR / "storage"

# Директорія шаблонів
TEMPLATES_DIR = BASE_DIR / "templates"

# Кольори статусів для UI
STATUS_COLORS = {
    "draft": "#3B82F6",           # Синій
    "on_signature": "#F59E0B",    # Помаранчевий
    "signed": "#10B981",          # Зелений
    "processed": "#059669",       # Темно-зелений
}

# Іконки статусів для UI
STATUS_ICONS = {
    "draft": "📝",
    "on_signature": "✍️",
    "signed": "✅",
    "processed": "📁",
}

# Обмеження файлів для завантаження
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# Кількість днів для критичного сповіщення про закінчення контракту
CONTRACT_EXPIRY_WARNING_DAYS = 30

# Дні тижня (0 = Понеділок, 6 = Неділя)
WEEKEND_DAYS = {5, 6}  # Субота, Неділя

# Налаштування воєнного стану та відпусток
SETTING_MARTIAL_LAW_ENABLED = "martial_law_enabled"
SETTING_MARTIAL_LAW_VACATION_LIMIT = "martial_law_vacation_limit"
SETTING_VACATION_DAYS_SCIENTIFIC_PEDAGOGICAL = "vacation_days_scientific_pedagogical"
SETTING_VACATION_DAYS_PEDAGOGICAL = "vacation_days_pedagogical"
SETTING_VACATION_DAYS_ADMINISTRATIVE = "vacation_days_administrative"
SETTING_COUNT_HOLIDAYS_AS_VACATION = "count_holidays_as_vacation"

# Значення за замовчуванням для відпусток (в календарних днях)
DEFAULT_VACATION_DAYS = {
    "scientific_pedagogical": 56,  # Науково-педагогічні працівники
    "pedagogical": 42,              # Педагогічні працівники
    "administrative": 24,           # Адміністративний персонал
}

# Ліміт відпустки під час воєнного стану (за законом 2136)
DEFAULT_MARTIAL_LAW_VACATION_LIMIT = 24
