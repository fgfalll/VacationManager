"""Константи VacationManager."""

from pathlib import Path

# Шлях до кореневої директорії проекту
BASE_DIR = Path(__file__).parent.parent

# Назви файлів шаблонів
TEMPLATE_FILES = {
    "vacation_paid": "vacation_paid.docx",
    "vacation_unpaid": "vacation_unpaid.docx",
    "term_extension": "term_extension.docx",
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
