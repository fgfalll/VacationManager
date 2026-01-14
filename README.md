# VacationManager v5.5

Система управління відпустками для університетської кафедри.

## Проект

**VacationManager** — гібридна екосистема (Desktop + Web) для автоматизації кадрового діловодства кафедри університету.

### Основні функції

- Управління персоналом кафедри
- Річний графік відпусток
- Конструктор заяв з live preview
- Генерація Word документів з українською морфологією
- Web portal для завантаження сканів підписаних документів
- WebSocket синхронізація між Desktop та Web

### Технологічний стек

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.0
- **Desktop**: PyQt6
- **Database**: SQLite
- **Document Generation**: docxtpl (Word templates)
- **Grammar**: pymorphy3 (Ukrainian morphology)

## Встановлення

### Клонування репозиторію

```bash
git clone <repository-url>
cd Вак
```

### Створення віртуального середовища

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Встановлення залежностей

```bash
pip install -r requirements.txt
```

### Налаштування

```bash
copy .env.example .env
```

Відредагуйте `.env` при необхідності.

## Використання

### Ініціалізація бази даних

```bash
# Створення міграції
alembic revision --autogenerate -m "Initial migration"

# Застосування міграцій
alembic upgrade head
```

### Запуск Web сервера

```bash
python -m backend.main
```

API буде доступно за адресою: http://127.0.0.1:8000
Документація API: http://127.0.0.1:8000/docs

### Запуск Desktop додатку

```bash
python -m desktop.main
```

## Тестування

```bash
# Запуск всіх тестів
pytest

# Запуск unit тестів
pytest tests/unit

# Запуск з покриттям
pytest --cov=backend --cov=desktop
```

## Структура проекту

```
Вак/
├── backend/            # FastAPI backend
│   ├── core/          # Config, Database, Logging
│   ├── models/        # SQLAlchemy ORM models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   └── api/           # API routes
├── desktop/           # PyQt6 Desktop application
│   ├── ui/            # UI components
│   ├── widgets/       # Custom widgets
│   └── utils/         # Utilities
├── shared/            # Shared code (enums, validators)
├── templates/         # Word document templates
├── tests/             # Unit and integration tests
└── alembic/           # Database migrations
```

## Ліцензія

© 2025 VacationManager
