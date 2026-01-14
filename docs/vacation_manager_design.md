# Дизайн-документ: Система VacationManager v5.5

## 1. Executive Summary

**VacationManager** — гібридна екосистема (Desktop + Web) для автоматизації кадрового діловодства кафедри університету.

### 1.1. Бізнес-цілі
- Автоматизація повного циклу управління відпустками
- Скорочення часу обробки заяв на 70%
- Забезпечення юридичної коректності документів
- Централізоване зберігання та аудит документообігу

### 1.2. Цільова аудиторія
- **Викладачі**: створення та відстеження заяв
- **Завідувач кафедри**: планування, погодження
- **Секретар**: оцифрування підписаних документів
- **HR-відділ**: звітність, архів

---

## 2. Технологічний стек

### 2.1. Backend
- **Runtime**: Python 3.10+
- **ORM**: SQLAlchemy 2.0+
- **Database**: SQLite (розглянути міграцію на PostgreSQL для >100 користувачів)
- **API Framework**: FastAPI 0.104+
- **Validation**: Pydantic v2

### 2.2. Desktop UI
- **Framework**: PyQt6
- **Web Engine**: QWebEngineView (Live Preview)
- **State Management**: Qt Model/View Architecture

### 2.3. Web Portal
- **Backend**: FastAPI
- **Frontend**: (не вказано — рекомендую Jinja2 templates + HTMX або React)
- **Authentication**: JWT tokens
- **File Upload**: Multipart/form-data (max 10MB)

### 2.4. Document Processing
- **Template Engine**: docxtpl (Jinja2 для .docx)
- **Grammar**: pymorphy3 (морфологія української мови)
- **Date Logic**: python-dateutil
- **PDF Generation**: python-docx → docx2pdf (або LibreOffice headless)

### 2.5. Infrastructure
- **Logging**: structlog
- **Monitoring**: (рекомендую Sentry для error tracking)
- **Backup**: щоденний SQLite dump + ротація на 30 днів
- **Version Control**: Git + Semantic Versioning

---

## 3. Архітектура системи

### 3.1. Компонентна діаграма

```
┌─────────────────────────────────────────────────┐
│           Desktop Application (PyQt6)           │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Staff    │  │ Schedule │  │ Live Builder │  │
│  │ Manager  │  │ Planner  │  │ (Preview)    │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
└──────────────────┬──────────────────────────────┘
                   │ SQLAlchemy ORM
                   ▼
         ┌─────────────────────┐
         │   SQLite Database   │
         └─────────────────────┘
                   ▲
                   │ REST API (FastAPI)
┌──────────────────┴──────────────────────────────┐
│              Web Portal (FastAPI)               │
│  ┌──────────────┐         ┌──────────────────┐  │
│  │ Dashboard    │         │ Upload Service   │  │
│  │ (View Docs)  │ ◄─────► │ (Scan Upload)    │  │
│  └──────────────┘         └──────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 3.2. Потоки даних

**Scenario 1: Створення заяви**
1. Користувач обирає співробітника → конструктор
2. Система валідує дані + генерує прев'ю (HTML)
3. Після підтвердження → .docx файл → статус "Draft"

**Scenario 2: Завантаження скану**
1. Секретар відкриває Web Portal
2. Знаходить документ "На підписі" → Upload
3. FastAPI приймає файл → валідація → зберігання
4. Desktop app отримує WebSocket notification → оновлює статус

---

## 4. Модель даних

### 4.1. ER-діаграма (спрощена)

```
┌──────────────┐       ┌─────────────────┐       ┌──────────────┐
│    Staff     │───┐   │    Document     │   ┌───│   Settings   │
├──────────────┤   │   ├─────────────────┤   │   ├──────────────┤
│ id (PK)      │   └──►│ id (PK)         │   │   │ id (PK)      │
│ pib_nom      │       │ staff_id (FK)   │   │   │ rector_name  │
│ degree       │       │ doc_type        │   │   │ rector_title │
│ position     │       │ status          │   │   │ dept_name    │
│ rate         │       │ date_start      │   │   │ dept_head_id │
│ term_start   │       │ date_end        │   │   └──────────────┘
│ term_end     │       │ file_path       │   │
│ vacation_bal │       │ created_at      │   │
└──────────────┘       │ updated_at      │   │
                       └─────────────────┘   │
                                 │            │
                                 ▼            │
                       ┌─────────────────┐   │
                       │   Approvers     │◄──┘
                       ├─────────────────┤
                       │ id (PK)         │
                       │ position_name   │
                       │ full_name_dav   │
                       │ order_index     │
                       └─────────────────┘
```

### 4.2. Таблиці бази даних

#### 4.2.1. `staff` (Персонал)

| Поле | Тип | Обмеження | Опис |
|------|-----|-----------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | Унікальний ідентифікатор |
| `pib_nom` | VARCHAR(200) | NOT NULL, UNIQUE | ПІБ у називному відмінку |
| `degree` | VARCHAR(50) | NULL | Вчений ступінь (к.т.н., д.т.н.) |
| `rate` | DECIMAL(3,2) | CHECK (rate > 0 AND rate <= 1) | Ставка (0.25, 0.5, 1.0) |
| `position` | VARCHAR(100) | NOT NULL | Посада (Доцент, Професор) |
| `employment_type` | ENUM | NOT NULL | Основне / Зовнішній / Внутрішній сумісник |
| `work_basis` | VARCHAR(100) | NOT NULL | Контракт / Конкурсна основа / Заява |
| `term_start` | DATE | NOT NULL | Початок договору |
| `term_end` | DATE | NOT NULL, CHECK (term_end > term_start) | Кінець договору |
| `vacation_balance` | INTEGER | DEFAULT 0, CHECK (>= 0) | Залишок днів відпустки |
| `is_active` | BOOLEAN | DEFAULT TRUE | Soft delete |
| `created_at` | TIMESTAMP | DEFAULT NOW() | |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | |

**Індекси:**
- `idx_staff_active` на `(is_active, term_end)` — для швидкого пошуку активних співробітників

#### 4.2.2. `documents` (Документи)

| Поле | Тип | Обмеження | Опис |
|------|-----|-----------|------|
| `id` | INTEGER | PK | |
| `staff_id` | INTEGER | FK → staff.id | Співробітник |
| `doc_type` | ENUM | NOT NULL | vacation_paid / vacation_unpaid / term_extension |
| `status` | ENUM | NOT NULL | draft / on_signature / signed / processed |
| `date_start` | DATE | NOT NULL | |
| `date_end` | DATE | NOT NULL | |
| `days_count` | INTEGER | COMPUTED | |
| `payment_period` | VARCHAR(100) | NULL | "у першій половині червня" |
| `custom_text` | TEXT | NULL | Manual override |
| `file_docx_path` | VARCHAR(500) | NULL | Шлях до .docx |
| `file_scan_path` | VARCHAR(500) | NULL | Шлях до скану |
| `created_at` | TIMESTAMP | | |
| `updated_at` | TIMESTAMP | | |
| `signed_at` | TIMESTAMP | NULL | |
| `processed_at` | TIMESTAMP | NULL | |

**Індекси:**
- `idx_docs_staff_status` на `(staff_id, status)`
- `idx_docs_created` на `(created_at DESC)`

#### 4.2.3. `annual_schedule` (Річний графік)

| Поле | Тип | Опис |
|------|-----|------|
| `id` | INTEGER | PK |
| `year` | INTEGER | Рік графіку |
| `staff_id` | INTEGER | FK → staff.id |
| `planned_start` | DATE | Плановий початок |
| `planned_end` | DATE | Плановий кінець |
| `is_used` | BOOLEAN | Чи створено заяву на основі цього запису |

**Унікальність:** `UNIQUE(year, staff_id)`

#### 4.2.4. `settings` (Налаштування)

| Поле | Тип | Опис |
|------|-----|------|
| `id` | INTEGER | PK |
| `key` | VARCHAR(100) | UNIQUE (rector_name, dept_name) |
| `value` | TEXT | JSON для складних об'єктів |

**Приклади:**
```json
{
  "rector_name": "Ганні ОЛІЙНИК",
  "rector_title": "в.о. ректора Полтавського державного аграрного університету",
  "dept_name": "Кафедра інформаційних систем і технологій",
  "dept_head_id": 5
}
```

#### 4.2.5. `approvers` (Погоджувачі)

| Поле | Тип | Опис |
|------|-----|------|
| `id` | INTEGER | PK |
| `position_name` | VARCHAR(200) | "Директор ННІНГ" |
| `full_name_dav` | VARCHAR(200) | ПІБ у давальному відмінку |
| `order_index` | INTEGER | Порядок в документі |

---

## 5. Функціональні модулі

### 5.1. Модуль «Річний графік відпусток»

**Вхідні дані:**
- Рік планування (наступний рік)
- Список активних співробітників

**Бізнес-правила:**
1. Автоматично включаються:
   - Співробітники зі ставкою = 1.0
   - Внутрішні сумісники
2. Можливість ручного додавання інших
3. **Валідація:**
   - Початок/кінець не можуть бути у вихідні (субота/неділя)
   - Тривалість > 0 днів
   - Не перетинається з іншими відпустками того ж співробітника
   - Не виходить за межі `term_end`

**Алгоритм розподілу:**
```python
def auto_distribute_vacations(year: int, staff_list: List[Staff]):
    """
    Рівномірно розподіляє відпустки по місяцях,
    уникаючи перевантаження одного періоду
    """
    # Ваша логіка тут
```

### 5.2. Візуальний конструктор (Live Builder)

**Компоненти інтерфейсу:**

1. **Блок 1: Вибір типу документа**
   - Radio buttons: Відпустка оплачувана / без збереження / Продовження терміну
   
2. **Блок 2: Даті та період**
   - Date pickers з валідацією вихідних
   - Auto-compute днів
   
3. **Блок 3: Підстави**
   - Завантажується текст на основі `work_basis`
   
4. **Блок 4: Оплата**
   - Auto-fill фрази "у першій/другій половині [місяця]"
   
5. **Блок 5: Live Preview**
   - HTML рендер з CSS стилізацією
   - Manual override textarea

**Технічна реалізація:**
```python
class LiveBuilderWidget(QWidget):
    def __init__(self):
        self.web_view = QWebEngineView()
        self.template_engine = TemplateEngine()
        
    def on_field_change(self):
        """Оновлює preview при зміні будь-якого поля"""
        html = self.template_engine.render(self.get_form_data())
        self.web_view.setHtml(html)
```

### 5.3. Grammar Engine (Морфологія)

**Завдання:**
- Відмінювання ПІБ (називний → родовий/давальний)
- Відмінювання посад
- Форматування ПІБ згідно типу документа

**Приклад коду:**
```python
from pymorphy3 import MorphAnalyzer

class UkrainianGrammar:
    def __init__(self):
        self.morph = MorphAnalyzer(lang='uk')
    
    def to_genitive(self, full_name: str) -> str:
        """Іванов Іван Іванович → Іванова Івана Івановича"""
        words = full_name.split()
        return ' '.join([
            self.morph.parse(w)[0].inflect({'gent'}).word
            for w in words
        ])
    
    def format_for_vacation(self, full_name: str) -> str:
        """Іванов Іван Іванович → Іван ІВАНОВ"""
        parts = full_name.split()
        return f"{parts[1]} {parts[0].upper()}"
```

### 5.4. Система статусів документа

**Діаграма переходів:**

```
     ┌─────────┐
     │  Draft  │ (синій)
     └────┬────┘
          │ [Роздрукувати]
          ▼
  ┌───────────────┐
  │ On Signature  │ (помаранчевий)
  └───────┬───────┘
          │ [Завантажити скан]
          ▼
     ┌─────────┐
     │ Signed  │ (зелений)
     └────┬────┘
          │ [Списати з табелю]
          ▼
   ┌──────────┐
   │Processed │ (темно-зелений)
   └──────────┘
   
   [Будь-який статус] ──► [Draft] (ручне повернення)
```

**Правила переходів:**

| З статусу | У статус | Дія | Побічні ефекти |
|-----------|----------|-----|----------------|
| Draft | On Signature | Друк .docx | `file_docx_path` встановлено |
| On Signature | Signed | Upload скану | `file_scan_path`, `signed_at` |
| Signed | Processed | Списати дні | `vacation_balance -= days`, `processed_at` |
| Any | Draft | Rollback | Видалення файлів, переміщення скану в `obsolete/` |

### 5.5. Критичні сповіщення

**Trigger:** `term_end - CURRENT_DATE < 30`

**Поведінка:**
1. Рядок співробітника у списку підсвічується червоним
2. При відкритті картки — попап з пропозицією створити заяву на продовження
3. Email нотифікація завідувачу (якщо налаштовано)

---

## 6. Web-інтерфейс (Upload Portal)

### 6.1. Архітектура

**Endpoint:** `https://your-domain.com/upload-portal`

**Технології:**
- Backend: FastAPI
- Frontend: Jinja2 + HTMX (рекомендовано) або чистий JS
- Auth: JWT tokens (виданий Desktop app)

### 6.2. API Endpoints

#### 6.2.1. GET `/api/documents/pending`
**Відповідь:**
```json
[
  {
    "id": 42,
    "staff_name": "Іванов Іван Іванович",
    "doc_type": "vacation_paid",
    "date_start": "2025-07-01",
    "date_end": "2025-07-14",
    "created_at": "2025-06-20T10:30:00"
  }
]
```

#### 6.2.2. POST `/api/documents/{id}/upload`
**Request:**
```
Content-Type: multipart/form-data
file: [binary data]
```

**Validation:**
- Max size: 10MB
- Formats: PDF, JPG, PNG
- Metadata check: чи існує документ і чи його статус = "on_signature"

**Response:**
```json
{
  "success": true,
  "file_path": "/storage/2025/07/signed/ivanov_42.pdf"
}
```

### 6.3. Sync Mechanism

**Опція 1: Polling (проста)**
- Desktop app кожні 30 секунд робить GET `/api/sync`

**Опція 2: WebSockets (рекомендовано)**
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Broadcast при завантаженні скану
```

---

## 7. Безпека

### 7.1. Аутентифікація та авторизація

**Desktop App:**
- Локальна автентифікація (пароль зберігається як bcrypt hash)
- Ролі: Admin / User / Viewer

**Web Portal:**
- JWT token з терміном дії 24 години
- Token генерується Desktop app і передається через QR-код або link

### 7.2. Валідація даних

**Pydantic моделі:**
```python
class DocumentCreate(BaseModel):
    staff_id: int = Field(gt=0)
    doc_type: DocumentType
    date_start: date
    date_end: date
    
    @validator('date_end')
    def end_after_start(cls, v, values):
        if v <= values['date_start']:
            raise ValueError('Дата завершення має бути пізніше початку')
        return v
```

### 7.3. Файлова система

**Структура:**
```
/storage
  /2025
    /01_january
      /draft
      /on_signature
      /signed
      /processed
    /obsolete  ← видалені скани
```

**Permissions:**
- Папка `storage/` доступна тільки Desktop app
- Web Portal має read-only до `on_signature/` та write до `signed/`

---

## 8. Тестування

### 8.1. Unit Tests
- Морфологічний движок (100+ прикладів ПІБ)
- Валідація дат (вихідні, перетини)
- Форматування документів

### 8.2. Integration Tests
- End-to-end flow: створення → друк → upload → обробка
- API endpoints (FastAPI TestClient)

### 8.3. Manual Testing Checklist
- [ ] Створення графіку на наступний рік
- [ ] Генерація всіх типів документів
- [ ] Rollback до Draft з кожного статусу
- [ ] Upload через Web Portal
- [ ] Сповіщення про закінчення терміну

---

## 9. Deployment

### 9.1. Desktop App
**Збірка:**
```bash
pyinstaller --onefile --windowed vacationmanager.py
```

**Оновлення:**
- Auto-update через GitHub Releases
- Або manual download

### 9.2. Web Portal
**Docker Compose:**
```yaml
version: '3.8'
services:
  web:
    image: vacationmanager-web:latest
    ports:
      - "8000:8000"
    volumes:
      - ./storage:/app/storage
      - ./database.db:/app/database.db
    environment:
      - SECRET_KEY=${SECRET_KEY}
```

**Backup Strategy:**
- Щоденний cron job: `sqlite3 database.db .dump > backup.sql`
- Зберігання останніх 30 днів

---

## 10. Roadmap

### v5.5 (Current)
- [x] Базовий функціонал
- [x] Web upload portal

### v6.0 (Q2 2026)
- [ ] Міграція на PostgreSQL
- [ ] Multi-tenancy (кілька кафедр)
- [ ] Email notifications
- [ ] Експорт звітів у Excel

### v7.0 (Q4 2026)
- [ ] Електронний підпис (КЕП)
- [ ] Інтеграція з 1C:ЗУП
- [ ] Mobile app (React Native)

---

## 11. Appendix

### 11.1. Glossary
- **ПІБ**: Прізвище, Ім'я, По батькові
- **Ставка**: Повнота робочого часу (1.0 = повна ставка)
- **Табель**: Облік робочого часу

### 11.2. References
- [pymorphy3 documentation](https://pymorphy3.readthedocs.io/)
- [docxtpl GitHub](https://github.com/elapouya/python-docx-template)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)

### 11.3. Change Log
- **v5.5.0** (2024-12-25): Початкова версія дизайн-документа