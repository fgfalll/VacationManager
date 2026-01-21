"""Константи VacationManager."""

from pathlib import Path

# Шлях до кореневої директорії проекту
BASE_DIR = Path(__file__).parent.parent

# Назви файлів шаблонів (HTML для WYSIWYG редактора)
TEMPLATE_FILES = {
    "vacation_paid": "vacation_paid.html",
    "vacation_unpaid": "vacation_unpaid.html",
    "term_extension": "term_extension.html",

    # Оплачувані відпустки
    "vacation_main": "vacation_main.html",
    "vacation_additional": "vacation_additional.html",
    "vacation_chornobyl": "vacation_chornobyl.html",
    "vacation_creative": "vacation_creative.html",
    "vacation_study": "vacation_study.html",
    "vacation_children": "vacation_children.html",
    "vacation_maternity": "vacation_maternity.html",
    "vacation_childcare": "vacation_childcare.html",

    # Відпустки без збереження зарплати
    "vacation_unpaid_study": "vacation_unpaid_study.html",
    "vacation_unpaid_mandatory": "vacation_unpaid_mandatory.html",
    "vacation_unpaid_agreement": "vacation_unpaid_agreement.html",
    "vacation_unpaid_other": "vacation_unpaid_other.html",

    # Продовження контракту
    "term_extension_contract": "term_extension_contract.html",
    "term_extension_competition": "term_extension_competition.html",
    "term_extension_pdf": "term_extension_pdf.html",
}

# Директорія для зберігання документів
STORAGE_DIR = BASE_DIR / "storage"

# Директорія шаблонів
TEMPLATES_DIR = BASE_DIR / "templates"

# Лейбли статусів документів українською - повний workflow
STATUS_LABELS = {
    "draft": "Чернетка",
    "signed_by_applicant": "Підписав заявник",
    "approved_by_dispatcher": "Погоджено диспетчером",
    "signed_dep_head": "Підписано зав. кафедри",
    "agreed": "Погоджено",
    "signed_rector": "Підписано ректором",
    "scanned": "Відскановано",
    "processed": "В табелі",
}

# Кольори статусів для UI
STATUS_COLORS = {
    "draft": "#8c8c8f",                  # Сірий
    "signed_by_applicant": "#1890ff",    # Синій
    "approved_by_dispatcher": "#13c2c2",  # Блакитний
    "signed_dep_head": "#52c41a",        # Зелений
    "agreed": "#faad14",                 # Помаранчевий
    "signed_rector": "#722ed1",          # Фіолетовий
    "scanned": "#eb2f96",                # Маджента
    "processed": "#006d75",              # Темно-блакитний
}

# Іконки статусів для UI
STATUS_ICONS = {
    "draft": "📝",
    "signed_by_applicant": "✍️",
    "approved_by_dispatcher": "👨‍💼",
    "signed_dep_head": "📋",
    "agreed": "🤝",
    "signed_rector": "🎓",
    "scanned": "📷",
    "processed": "📁",
}

# Опис статусів для підказок
STATUS_DESCRIPTIONS = {
    "draft": "Документ створено, очікує заповнення та подання",
    "signed_by_applicant": "Підписано заявником",
    "approved_by_dispatcher": "Погоджено диспетчером",
    "signed_dep_head": "Підписано завідувачем кафедри",
    "agreed": "Погоджено (колективні узгодження)",
    "signed_rector": "Підписано ректором",
    "scanned": "Документ відскановано",
    "processed": "Документ додано до табеля",
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

# Налаштування PDF шаблонів
SETTING_PDF_TERM_EXTENSION_TEMPLATE = "pdf_term_extension_template"  # Шлях до PDF шаблону продовження контракту

# Значення за замовчуванням для відпусток (в календарних днях)
DEFAULT_VACATION_DAYS = {
    "scientific_pedagogical": 56,  # Науково-педагогічні працівники
    "pedagogical": 42,              # Педагогічні працівники
    "administrative": 24,           # Адміністративний персонал
}

# Ліміт відпустки під час воєнного стану (за законом 2136)
DEFAULT_MARTIAL_LAW_VACATION_LIMIT = 24
