# VacationManager v5.5

Система управління відпустками для університетської кафедри.

## Версія 14.01.2026 - Розширений функціонал

### Проект

**VacationManager** — гібридна екосистема (Desktop + Web) для автоматизації кадрового діловодства кафедри університету.

### Основні функції

- Управління персоналом кафедри
- Річний графік відпусток з автоматичним розподілом
- Конструктор заяв з live preview
- Генерація документів з українською морфологією
- Web portal для завантаження сканів підписаних документів
- WebSocket синхронізація між Desktop та Web
- **Масова генерація документів**
- **Підтримка воєнного стану**
- **Розширена валідація дат**

### Технологічний стек

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.0
- **Desktop**: PyQt6
- **Database**: SQLite
- **Document Generation**: docxtpl (Word templates)
- **Grammar**: pymorphy3 (Ukrainian morphology)

---

## Новий функціонал (з 12.12.2025 по 14.01.2026)

### Нові Сервіси (Services)

#### 1. BulkDocumentService (`bulk_document_service.py`)
Масова генерація документів для групи співробітників:
- Генерація документів для списку співробітників
- Валідація списку перед генерацією
- Пошук доступних періодів для відпустки
- Форматування імен файлів з українськими назвами місяців

#### 2. ScheduleService (`schedule_service.py`)
Автоматичне управління річним графіком відпусток:
- Автоматичний розподіл відпусток по місяцях
- Вибір першого понеділка місяця для початку відпустки
- Перевірка на перетини з існуючими записами
- Статистика графіку по роках і місяцях
- Валідація записів графіку

#### 3. ValidationService (`validation_service.py`)
Комплексна валідація бізнес-правил:
- **Валідація дат відпустки**: вихідні, перетини, баланс, termin контракту
- **Розрахунок робочих та календарних днів**
- **Парсинг складних форматів дат** українською мовою
- **Підтримка воєнного стану**:
  - Ліміт 24 дні відпустки під час воєнного стану
  - Підрахунок всіх днів (включно з вихідними та святами)
  - Налаштування для різних категорій працівників
- **Визначення українських свят**
- **Перевірка лімітів документів** (макс. 3 відпустки на підписі, 1 продовження контракту)
- Клас `DateRange` для роботи з діапазонами дат

#### 4. DateParser (`date_parser.py`)
Розпізнавання дат українською мовою:
- `12 березня` — одиночна дата
- `12, 14, 19 березня` — кілька дат
- `12-19 березня` — діапазон
- `12, 14, 19-21 березня` — комбінація
- `12.03.2025` — класичний формат
- `12/03/2025` — альтернативний роздільник

#### 5. StaffService (`staff_service.py`)
Ділові операції над співробітниками:
- Create, Update, Delete, Restore
- Фільтрація за статусом, типом працевлаштування
- Пошук з закінчуючими контрактами

#### 6. DocumentService (`document_service.py`)
Операції над документами:
- Створення, оновлення, видалення
- Зміна статусів
- Генерація Word/PDF документів

#### 7. Enhanced GrammarService
Нові методи:
- `format_payment_period()` — форматування періоду оплати українською
- `get_gender()` — визначення статі за ПІБ
- `decline_position()` — відмінювання посад

### Нові Модулі

#### 1. Logging Module (`backend/core/logging.py`)
Налаштування логування:
- JSON або консольний формат
- Рівні логування: DEBUG, INFO, WARNING, ERROR, CRITICAL

#### 2. Enhanced Settings (`backend/core/config.py`)
Додаткові налаштування:
- Налаштування воєнного стану
- Ліміт днів відпустки під час воєнного стану
- Дні відпустки за категоріями працівників
- Чи враховувати свята при підрахунку днів
- Backup налаштування

### Нові Константи

#### Воєнний стан
- `SETTING_MARTIAL_LAW_ENABLED` — увімкнення режиму
- `SETTING_MARTIAL_LAW_VACATION_LIMIT` — ліміт днів (за замовчуванням 24)

#### Дні відпустки за категоріями
- Науково-педагогічні працівники: 56 днів
- Педагогічні працівники: 42 дні
- Адміністративний персонал: 24 дні

#### Українські свята
```
(1, 1) Новий рік
(1, 7) Різдво
(3, 8) Міжнародний жіночий день
(5, 1) День праці
(5, 8) День пам'яті та перемоги
(6, 28) День Конституції
(8, 24) День Незалежності
(9, 1) День знань
(10, 14) День захисників та захисниць
(12, 25) Різдво Христове
```

### Нові Enums

- `UserRole` — ролі користувачів (admin, user, viewer)
- `StaffActionType` — типи дій над записами (create, update, deactivate, restore)

### Розширені Schemas

- `StaffCreate`, `StaffUpdate`, `StaffResponse`, `StaffListResponse`
- `DocumentCreate`, `DocumentUpdate`, `DocumentResponse`
- `ScheduleCreate`, `ScheduleResponse`

---

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
│   │   ├── responses.py
│   │   ├── staff.py
│   │   └── document.py
│   ├── services/      # Business logic
│   │   ├── grammar_service.py
│   │   ├── validation_service.py  # РОЗШИРЕНО
│   │   ├── document_service.py    # НОВЕ
│   │   ├── bulk_document_service.py  # НОВЕ
│   │   ├── schedule_service.py    # НОВЕ
│   │   ├── staff_service.py       # НОВЕ
│   │   └── date_parser.py         # НОВЕ
│   └── api/           # API routes
│       ├── dependencies.py
│       └── routes/
│           ├── staff.py
│           └── documents.py
├── desktop/           # PyQt6 Desktop application
│   ├── ui/            # UI components
│   ├── widgets/       # Custom widgets
│   │   ├── status_badge.py
│   │   └── live_preview.py
│   └── utils/         # Utilities
│       ├── theme.py
│       └── sync_manager.py
├── shared/            # Shared code
│   ├── enums.py       # РОЗШИРЕНО (UserRole, StaffActionType)
│   ├── constants.py   # РОЗШИРЕНО (воєнний стан, свята)
│   ├── exceptions.py
│   └── validators.py
├── templates/         # Word document templates
├── static/            # Static files
├── tests/             # Unit and integration tests
│   ├── unit/
│   │   ├── test_grammar_service.py
│   │   └── test_validation_service.py
│   └── integration/
└── alembic/           # Database migrations
```

## Ліцензія

© 2025-2026 VacationManager
