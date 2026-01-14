# VacationManager v5.5

Система управління відпустками для університетської кафедри.

## Версія 12.12.2025 - Базовий функціонал

### Проект

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

## Реалізовані модулі (v12.12.2025)

### Backend Models
- `Staff` — модель співробітника з ставкою, типом працевлаштування, балансом відпустки
- `Document` — модель документа (заяви на відпустку) зі статусами
- `AnnualSchedule` — запис у річному графіку відпусток
- `Approvers` — погоджувачі документів
- `SystemSettings` — key-value налаштування системи

### Backend Services
- `GrammarService` — морфологічні перетворення української мови (відмінювання ПІБ, посад)

### API Routes
- `/staff` — CRUD операції над співробітниками

### Desktop Widgets
- `StatusBadge` — кольоровий індикатор статусу документа
- `LivePreview` — live preview заяв

### Shared
- Enums: EmploymentType, WorkBasis, DocumentType, DocumentStatus
- Validators
- Exceptions

## Встановлення

### Клонування репозиторію

```bash
git clone <repository-url>
cd VacationManager
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
VacationManager/
├── backend/            # FastAPI backend
│   ├── core/          # Config, Database, Logging
│   ├── models/        # SQLAlchemy ORM models
│   │   ├── base.py
│   │   ├── staff.py
│   │   ├── document.py
│   │   ├── schedule.py
│   │   └── settings.py
│   ├── schemas/       # Pydantic schemas
│   │   ├── schedule.py
│   │   └── responses.py
│   ├── services/      # Business logic
│   │   └── grammar_service.py
│   └── api/           # API routes
│       ├── dependencies.py
│       └── routes/
│           ├── staff.py
│           └── documents.py
├── desktop/           # PyQt6 Desktop application
│   ├── main.py
│   ├── ui/            # UI components
│   ├── widgets/       # Custom widgets
│   │   ├── status_badge.py
│   │   └── live_preview.py
│   └── utils/         # Utilities
│       ├── theme.py
│       └── sync_manager.py
├── shared/            # Shared code
│   ├── enums.py
│   ├── constants.py
│   ├── exceptions.py
│   └── validators.py
├── templates/         # Word document templates
├── tests/             # Unit and integration tests
└── alembic/           # Database migrations
```

## Ліцензія

© 2025 VacationManager
