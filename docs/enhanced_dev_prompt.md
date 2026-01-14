# 🎯 VacationManager v5.5 — Технічне завдання для розробки

## 👨‍💻 Роль
**Senior Full-Stack Python Developer** з експертизою у PyQt6, FastAPI, SQLAlchemy та українській морфології.

---

## 🎨 Філософія проекту

### Принципи розробки
1. **DRY (Don't Repeat Yourself)**: Уникати дублювання логіки
2. **SOLID**: Особливо Single Responsibility та Dependency Injection
3. **Clean Architecture**: Розділення бізнес-логіки, UI та інфраструктури
4. **Type Safety**: Використовувати type hints скрізь (`from typing import ...`)
5. **User-First**: Кожна дія має бути інтуїтивною та прощати помилки

### Code Style
- **PEP 8** для форматування
- **Docstrings**: Google Style для всіх публічних методів
- **Коментарі**: Українською мовою, пояснювати "чому", а не "що"
- **Naming**: 
  - Змінні/функції: `snake_case`
  - Класи: `PascalCase`
  - Константи: `UPPER_SNAKE_CASE`

---

## 🏗️ Архітектура та Технології

### Backend Stack
```python
# requirements.txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
alembic==1.13.1           # Міграції БД
pydantic==2.5.3
pydantic-settings==2.1.0   # Конфігурація через .env
python-multipart==0.0.6    # Для upload файлів
python-jose[cryptography]  # JWT tokens
passlib[bcrypt]            # Хешування паролів
python-dateutil==2.8.2
pymorphy3==1.3.1
pymorphy3-dicts-uk==2.4.1.1.1663094765  # Українські словники
docxtpl==0.16.7
python-docx==1.1.0
pillow==10.2.0             # Обробка зображень сканів
structlog==24.1.0          # Структуроване логування
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0              # Для тестування FastAPI
```

### Desktop Stack
```python
PyQt6==6.6.1
PyQt6-WebEngine==6.6.0
darkdetect==0.8.0          # Автодетект темної теми
qasync==0.27.1             # Async/await у PyQt
```

### Infrastructure
```bash
# Структура проекту
vacation_manager/
├── backend/
│   ├── core/
│   │   ├── config.py           # Pydantic Settings
│   │   ├── database.py         # SQLAlchemy setup
│   │   ├── security.py         # JWT, passwords
│   │   └── logging.py          # Structlog config
│   ├── models/
│   │   ├── staff.py
│   │   ├── document.py
│   │   ├── schedule.py
│   │   └── settings.py
│   ├── schemas/                # Pydantic моделі
│   │   ├── staff.py
│   │   ├── document.py
│   │   └── responses.py
│   ├── services/               # Бізнес-логіка
│   │   ├── grammar_service.py
│   │   ├── document_service.py
│   │   ├── schedule_service.py
│   │   └── validation_service.py
│   ├── api/
│   │   ├── routes/
│   │   │   ├── staff.py
│   │   │   ├── documents.py
│   │   │   ├── schedule.py
│   │   │   └── upload.py
│   │   └── dependencies.py     # Dependency Injection
│   └── templates/              # Jinja2 для web
│       └── upload_portal.html
├── desktop/
│   ├── main.py                 # Entry point
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── staff_tab.py
│   │   ├── schedule_tab.py
│   │   ├── builder_tab.py
│   │   └── settings_dialog.py
│   ├── widgets/
│   │   ├── live_preview.py     # QWebEngineView wrapper
│   │   ├── status_badge.py     # Кольорові індикатори
│   │   └── date_picker.py      # Custom date widget
│   └── utils/
│       ├── sync_manager.py     # WebSocket client
│       └── theme.py            # Темна/світла тема
├── shared/                     # Спільний код
│   ├── constants.py
│   ├── enums.py                # DocumentType, Status, etc.
│   └── validators.py
├── templates/                  # Word шаблони
│   ├── vacation_paid.docx
│   ├── vacation_unpaid.docx
│   └── term_extension.docx
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── alembic/                    # Міграції БД
├── storage/                    # Файли документів
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## 💾 База даних

### ORM Models (SQLAlchemy 2.0 style)

```python
# backend/models/staff.py
from sqlalchemy import String, Numeric, Date, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date
from decimal import Decimal
from .base import Base
from shared.enums import EmploymentType, WorkBasis

class Staff(Base):
    __tablename__ = "staff"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    pib_nom: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    degree: Mapped[str | None] = mapped_column(String(50))
    rate: Mapped[Decimal] = mapped_column(Numeric(3, 2))
    position: Mapped[str] = mapped_column(String(100))
    employment_type: Mapped[EmploymentType] = mapped_column(SQLEnum(EmploymentType))
    work_basis: Mapped[WorkBasis] = mapped_column(SQLEnum(WorkBasis))
    term_start: Mapped[date] = mapped_column(Date)
    term_end: Mapped[date] = mapped_column(Date)
    vacation_balance: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    documents: Mapped[list["Document"]] = relationship(back_populates="staff")
    schedule_entries: Mapped[list["AnnualSchedule"]] = relationship(back_populates="staff")
    
    @property
    def days_until_term_end(self) -> int:
        """Кількість днів до закінчення контракту"""
        from datetime import date
        return (self.term_end - date.today()).days
    
    @property
    def is_term_expiring_soon(self) -> bool:
        """Чи закінчується контракт менш ніж за 30 днів"""
        return self.days_until_term_end < 30
```

```python
# backend/models/document.py
from sqlalchemy import String, Date, Text, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from .base import Base
from shared.enums import DocumentType, DocumentStatus

class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"))
    doc_type: Mapped[DocumentType] = mapped_column(SQLEnum(DocumentType))
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus), 
        default=DocumentStatus.DRAFT
    )
    
    date_start: Mapped[date] = mapped_column(Date)
    date_end: Mapped[date] = mapped_column(Date)
    days_count: Mapped[int] = mapped_column(Integer)  # Обчислюється автоматично
    payment_period: Mapped[str | None] = mapped_column(String(100))
    custom_text: Mapped[str | None] = mapped_column(Text)
    
    file_docx_path: Mapped[str | None] = mapped_column(String(500))
    file_scan_path: Mapped[str | None] = mapped_column(String(500))
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    signed_at: Mapped[datetime | None]
    processed_at: Mapped[datetime | None]
    
    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="documents")
    
    def __repr__(self):
        return f"<Document {self.id} - {self.staff.pib_nom} ({self.status})>"
```

### Alembic Міграції
```python
# alembic/versions/001_initial.py
"""Initial migration

Revision ID: 001
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Створення таблиць
    op.create_table('staff', ...)
    op.create_table('documents', ...)
    # Індекси
    op.create_index('idx_staff_active', 'staff', ['is_active', 'term_end'])
    
def downgrade():
    op.drop_table('documents')
    op.drop_table('staff')
```

---

## 🧠 Ключові сервіси

### 1. Grammar Service (Морфологія)

```python
# backend/services/grammar_service.py
import pymorphy3
from functools import lru_cache
from shared.enums import DocumentType

class GrammarService:
    """
    Сервіс для морфологічних перетворень українських ПІБ та посад.
    Використовує pymorphy3 з українськими словниками.
    """
    
    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer(lang='uk')
    
    @lru_cache(maxsize=1024)
    def to_genitive(self, full_name: str) -> str:
        """
        Перетворює ПІБ з називного у родовий відмінок.
        
        Args:
            full_name: ПІБ у форматі "Прізвище Ім'я По-батькові"
            
        Returns:
            ПІБ у родовому відмінку
            
        Example:
            >>> grammar.to_genitive("Іванов Іван Іванович")
            "Іванова Івана Івановича"
        """
        words = full_name.split()
        result = []
        
        for word in words:
            parsed = self.morph.parse(word)[0]
            inflected = parsed.inflect({'gent'})
            
            if inflected:
                result.append(inflected.word.capitalize())
            else:
                # Фоллбек якщо слово не розпізнано
                result.append(word)
        
        return ' '.join(result)
    
    @lru_cache(maxsize=1024)
    def to_dative(self, full_name: str) -> str:
        """Давальний відмінок для ректора"""
        words = full_name.split()
        result = []
        
        for word in words:
            parsed = self.morph.parse(word)[0]
            inflected = parsed.inflect({'datv'})
            result.append(inflected.word.capitalize() if inflected else word)
        
        return ' '.join(result)
    
    def format_for_document(self, full_name: str, doc_type: DocumentType) -> str:
        """
        Форматує ПІБ згідно з типом документа.
        
        Rules:
            - Vacation: "Ім'я ПРІЗВИЩЕ" (Анна ЛЯШЕНКО)
            - Extension: "ПРІЗВИЩЕ Ім'я" (СУДАКОВ Андрій)
        """
        parts = full_name.split()
        
        if len(parts) < 2:
            return full_name.upper()
        
        surname, name = parts[0], parts[1]
        
        if doc_type in [DocumentType.VACATION_PAID, DocumentType.VACATION_UNPAID]:
            return f"{name} {surname.upper()}"
        elif doc_type == DocumentType.TERM_EXTENSION:
            return f"{surname.upper()} {name}"
        
        return full_name
```

### 2. Document Service

```python
# backend/services/document_service.py
from docxtpl import DocxTemplate
from datetime import date
from pathlib import Path
from sqlalchemy.orm import Session
from models.document import Document
from models.staff import Staff
from .grammar_service import GrammarService
from shared.enums import DocumentType, DocumentStatus

class DocumentService:
    """Сервіс генерації документів з Word шаблонів"""
    
    def __init__(self, db: Session, grammar: GrammarService):
        self.db = db
        self.grammar = grammar
        self.templates_dir = Path("templates")
    
    def generate_document(self, document: Document) -> Path:
        """
        Генерує .docx файл на основі шаблону та даних документа.
        
        Returns:
            Path до створеного файлу
        """
        # Вибір шаблону
        template_map = {
            DocumentType.VACATION_PAID: "vacation_paid.docx",
            DocumentType.VACATION_UNPAID: "vacation_unpaid.docx",
            DocumentType.TERM_EXTENSION: "term_extension.docx",
        }
        
        template_path = self.templates_dir / template_map[document.doc_type]
        doc_template = DocxTemplate(template_path)
        
        # Підготовка контексту
        context = self._build_context(document)
        
        # Рендер
        doc_template.render(context)
        
        # Збереження
        output_path = self._get_output_path(document)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc_template.save(output_path)
        
        # Оновлення документа
        document.file_docx_path = str(output_path)
        document.status = DocumentStatus.ON_SIGNATURE
        self.db.commit()
        
        return output_path
    
    def _build_context(self, document: Document) -> dict:
        """Збирає контекст для шаблону"""
        staff = document.staff
        settings = self._load_settings()
        
        # Базові дані
        context = {
            "rector_name_dav": settings.rector_name_dative,
            "rector_title": settings.rector_title,
            "dept_name": settings.dept_name,
            "applicant_name": self.grammar.format_for_document(
                staff.pib_nom, document.doc_type
            ),
            "applicant_position_gen": self.grammar.to_genitive(staff.position),
            "date_start": document.date_start.strftime("%d.%m.%Y"),
            "date_end": document.date_end.strftime("%d.%m.%Y"),
            "days_count": document.days_count,
            "payment_period": document.payment_period or "",
            "custom_text": document.custom_text or "",
        }
        
        # Блок підпису завідувача (якщо заявник не є завідувачем)
        if staff.id != settings.dept_head_id:
            context["show_dept_head_signature"] = True
            head = self.db.get(Staff, settings.dept_head_id)
            context["dept_head_name"] = head.pib_nom
        else:
            context["show_dept_head_signature"] = False
        
        # Блок погоджувачів
        context["approvers"] = [
            {
                "position": a.position_name,
                "name": a.full_name_dav
            }
            for a in settings.approvers
        ]
        
        return context
    
    def _get_output_path(self, document: Document) -> Path:
        """Генерує шлях для збереження файлу"""
        year = document.date_start.year
        month = document.date_start.strftime("%m_%B").lower()
        status = document.status.value
        
        filename = f"{document.staff.pib_nom.replace(' ', '_')}_{document.id}.docx"
        
        return Path(f"storage/{year}/{month}/{status}/{filename}")
    
    def rollback_to_draft(self, document: Document) -> None:
        """
        Повертає документ у статус Draft, видаляє старі файли.
        """
        # Видалення .docx
        if document.file_docx_path:
            Path(document.file_docx_path).unlink(missing_ok=True)
        
        # Переміщення скану в obsolete
        if document.file_scan_path:
            scan_path = Path(document.file_scan_path)
            obsolete_path = Path("storage/obsolete") / scan_path.name
            obsolete_path.parent.mkdir(exist_ok=True)
            scan_path.rename(obsolete_path)
        
        # Скидання полів
        document.status = DocumentStatus.DRAFT
        document.file_docx_path = None
        document.file_scan_path = None
        document.signed_at = None
        document.processed_at = None
        
        self.db.commit()
```

### 3. Validation Service

```python
# backend/services/validation_service.py
from datetime import date, timedelta
from sqlalchemy.orm import Session
from models.staff import Staff
from shared.exceptions import ValidationError

class ValidationService:
    """Валідація бізнес-правил"""
    
    @staticmethod
    def validate_vacation_dates(
        start: date, 
        end: date, 
        staff: Staff
    ) -> None:
        """
        Валідує дати відпустки згідно з бізнес-правилами.
        
        Raises:
            ValidationError: якщо дати некоректні
        """
        # Правило 1: Початок раніше за кінець
        if start >= end:
            raise ValidationError(
                "Дата початку має бути раніше за дату завершення"
            )
        
        # Правило 2: Не може бути у вихідні
        if start.weekday() in [5, 6]:  # Saturday, Sunday
            raise ValidationError(
                f"Дата початку ({start.strftime('%d.%m.%Y')}) "
                f"припадає на вихідний день"
            )
        
        if end.weekday() in [5, 6]:
            raise ValidationError(
                f"Дата завершення ({end.strftime('%d.%m.%Y')}) "
                f"припадає на вихідний день"
            )
        
        # Правило 3: Не виходить за межі контракту
        if end > staff.term_end:
            raise ValidationError(
                f"Відпустка виходить за межі контракту "
                f"(закінчується {staff.term_end.strftime('%d.%m.%Y')})"
            )
        
        # Правило 4: Достатній баланс днів
        days = (end - start).days + 1
        if days > staff.vacation_balance:
            raise ValidationError(
                f"Недостатньо днів відпустки. "
                f"Запитано: {days}, доступно: {staff.vacation_balance}"
            )
    
    @staticmethod
    def calculate_working_days(start: date, end: date) -> int:
        """
        Обчислює кількість робочих днів між датами (включно).
        Враховує суботи та неділі, НЕ враховує державні свята.
        """
        days = 0
        current = start
        
        while current <= end:
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                days += 1
            current += timedelta(days=1)
        
        return days
```

---

## 🖥️ Desktop Application (PyQt6)

### Main Window Architecture

```python
# desktop/main.py
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt6.QtCore import Qt
from ui.staff_tab import StaffTab
from ui.schedule_tab import ScheduleTab
from ui.builder_tab import BuilderTab
from ui.settings_dialog import SettingsDialog
from utils.sync_manager import SyncManager
from backend.core.database import SessionLocal

class VacationManagerApp(QMainWindow):
    """Головне вікно додатку"""
    
    def __init__(self):
        super().__init__()
        self.db = SessionLocal()
        self.sync_manager = SyncManager()
        
        self.setWindowTitle("VacationManager v5.5")
        self.setMinimumSize(1400, 900)
        
        self._setup_ui()
        self._connect_signals()
        
        # Застосування теми
        from utils.theme import apply_theme
        apply_theme(self)
    
    def _setup_ui(self):
        """Створення інтерфейсу"""
        # Центральний віджет - табки
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Вкладки
        self.staff_tab = StaffTab(self.db)
        self.schedule_tab = ScheduleTab(self.db)
        self.builder_tab = BuilderTab(self.db)
        
        self.tabs.addTab(self.staff_tab, "👥 Персонал")
        self.tabs.addTab(self.schedule_tab, "📅 Графік відпусток")
        self.tabs.addTab(self.builder_tab, "📝 Конструктор заяв")
        
        # Меню
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("Файл")
        file_menu.addAction("Налаштування", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("Вихід", self.close)
        
        sync_menu = menubar.addMenu("Синхронізація")
        sync_menu.addAction("Відкрити Web Portal", self._open_web_portal)
        sync_menu.addAction("Перевірити оновлення", self.sync_manager.sync_now)
    
    def _connect_signals(self):
        """Підключення сигналів між компонентами"""
        # Коли документ створено у конструкторі, оновити список у персоналі
        self.builder_tab.document_created.connect(
            self.staff_tab.refresh_documents
        )
        
        # Коли завантажено скан, оновити статус
        self.sync_manager.scan_uploaded.connect(
            self.staff_tab.update_document_status
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Кросплатформний стиль
    
    window = VacationManagerApp()
    window.show()
    
    sys.exit(app.exec())
```

### Live Builder Widget

```python
# desktop/widgets/live_preview.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import pyqtSignal
from jinja2 import Environment, FileSystemLoader

class LivePreviewWidget(QWidget):
    """
    HTML прев'ю документа з можливістю редагування.
    Використовує QWebEngineView для рендерингу.
    """
    
    content_changed = pyqtSignal(str)  # Емітується при зміні тексту
    
    def __init__(self):
        super().__init__()
        self.web_view = QWebEngineView()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web_view)
        
        # Jinja2 для HTML шаблонів
        self.jinja_env = Environment(
            loader=FileSystemLoader('desktop/templates')
        )
    
    def render_preview(self, context: dict):
        """
        Рендерить прев'ю заяви.
        
        Args:
            context: Дані для шаблону (ПІБ, дати, тощо)
        """
        template = self.jinja_env.get_template('document_preview.html')
        html = template.render(**context)
        
        self.web_view.setHtml(html)
    
    def enable_editing(self):
        """Дозволяє редагувати текст прямо у прев'ю"""
        js_code = """
        document.body.contentEditable = 'true';
        document.body.addEventListener('input', function() {
            // Відправка змін назад у PyQt
            window.qt.content_changed(document.body.innerText);
        });
        """
        self.web_view.page().runJavaScript(js_code)
```

### Status Badge Widget

```python
# desktop/widgets/status_badge.py
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from shared.enums import DocumentStatus

class StatusBadge(QLabel):
    """Кольоровий індикатор статусу документа"""
    
    COLORS = {
        DocumentStatus.DRAFT: "#3B82F6",           # Синій
        DocumentStatus.ON_SIGNATURE: "#F59E0B",    # Помаранчевий
        DocumentStatus.SIGNED: "#10B981",          # Зелений
        DocumentStatus.PROCESSED: "#059669",       # Темно-зелений
    }
    
    ICONS = {
        DocumentStatus.DRAFT: "📝",
        DocumentStatus.ON_SIGNATURE: "✍️",
        DocumentStatus.SIGNED: "✅",
        DocumentStatus.PROCESSED: "📁",
    }
    
    def __init__(self, status: DocumentStatus):
        super().__init__()
        self.set_status(status)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def set_status(self, status: DocumentStatus):
        """Оновлює відображення статусу"""
        color = self.COLORS[status]
        icon = self.ICONS[status]
        text = status.value.replace('_', ' ').title()
        
        self.setText(f"{icon} {text}")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
```

---

## 🌐 Web Portal (FastAPI)

### Main Application

```python
# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from api.routes import documents, upload
from core.config import settings
from core.logging import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events"""
    setup_logging()
    yield
    # Cleanup

app = FastAPI(
    title="VacationManager API",
    version="5.5.0",
    lifespan=lifespan
)

# Static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Templates
templates = Jinja2Templates(directory="backend/templates")

# Routes
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])

# WebSocket для real-time синхронізації
class ConnectionManager:
    """Менеджер WebSocket з'єднань"""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Відправляє повідомлення всім підключеним клієнтам"""
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle ping/pong
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
async def root():
    """Головна сторінка - редірект на Upload Portal"""
    return RedirectResponse("/upload-portal")
```

### Upload Endpoint

```python
# backend/api/routes/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
import structlog
from backend.core.database import get_db
from backend.models.document import Document
from backend.schemas.responses import UploadResponse
from shared.enums import DocumentStatus

router = APIRouter()
logger = structlog.get_logger()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

@router.get("/upload-portal", response_class=HTMLResponse)
async def upload_portal(request: Request, db: Session = Depends(get_db)):
    """Головна сторінка Upload Portal"""
    # Отримати всі документи зі статусом "На підписі"
    documents = db.query(Document).filter(
        Document.status == DocumentStatus.ON_SIGNATURE
    ).order_by(Document.created_at.desc()).all()
    
    return templates.TemplateResponse(
        "upload_portal.html",
        {
            "request": request,
            "documents": documents,
            "total_pending": len(documents)
        }
    )

@router.post("/upload/{document_id}", response_model=UploadResponse)
async def upload_scan(
    document_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Завантаження скану підписаного документа.
    
    - Валідує розмір та формат файлу
    - Зберігає у структуровану папку
    - Оновлює статус документа
    - Відправляє WebSocket notification Desktop app
    """
    logger.info("upload_scan_started", document_id=document_id, filename=file.filename)
    
    # Валідація документа
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Документ не знайдено")
    
    if document.status != DocumentStatus.ON_SIGNATURE:
        raise HTTPException(
            400, 
            f"Документ має статус '{document.status.value}', "
            f"очікується 'on_signature'"
        )
    
    # Валідація файлу
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Недопустимий формат файлу. "
            f"Дозволені: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Читання та перевірка розміру
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            413,
            f"Файл завеликий. Максимум: {MAX_FILE_SIZE / 1024 / 1024:.1f} MB"
        )
    
    # Збереження файлу
    try:
        save_path = _generate_scan_path(document, file_ext)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'wb') as f:
            f.write(contents)
        
        # Оновлення документа
        document.file_scan_path = str(save_path)
        document.status = DocumentStatus.SIGNED
        document.signed_at = datetime.utcnow()
        db.commit()
        
        # WebSocket broadcast
        await manager.broadcast({
            "type": "document_signed",
            "document_id": document_id,
            "status": DocumentStatus.SIGNED.value
        })
        
        logger.info(
            "upload_scan_success",
            document_id=document_id,
            path=str(save_path)
        )
        
        return UploadResponse(
            success=True,
            file_path=str(save_path),
            message="Скан успішно завантажено"
        )
        
    except Exception as e:
        logger.error("upload_scan_failed", error=str(e))
        db.rollback()
        raise HTTPException(500, "Помилка збереження файлу")

def _generate_scan_path(document: Document, extension: str) -> Path:
    """Генерує шлях для збереження скану"""
    year = document.date_start.year
    month = document.date_start.strftime("%m_%B").lower()
    
    filename = (
        f"{document.staff.pib_nom.replace(' ', '_')}_"
        f"{document.id}_signed{extension}"
    )
    
    return Path(f"storage/{year}/{month}/signed/{filename}")
```

### HTML Template для Upload Portal

```html
<!-- backend/templates/upload_portal.html -->
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VacationManager — Завантаження сканів</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="container mx-auto px-4 py-8 max-w-6xl">
        <!-- Header -->
        <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">
                📤 Завантаження підписаних документів
            </h1>
            <p class="text-gray-600 mt-2">
                Знайдіть потрібний документ та завантажте фото/скан підписаного оригіналу
            </p>
            <div class="mt-4 inline-flex items-center px-4 py-2 bg-orange-100 rounded-lg">
                <span class="text-orange-800 font-semibold">
                    На підписі: {{ total_pending }} документів
                </span>
            </div>
        </div>

        <!-- Documents List -->
        <div class="space-y-4">
            {% for doc in documents %}
            <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
                <div class="flex items-center justify-between">
                    <!-- Document Info -->
                    <div class="flex-1">
                        <h3 class="text-xl font-semibold text-gray-900">
                            {{ doc.staff.pib_nom }}
                        </h3>
                        <div class="mt-2 space-y-1 text-sm text-gray-600">
                            <p>
                                <span class="font-medium">Посада:</span>
                                {{ doc.staff.position }}
                            </p>
                            <p>
                                <span class="font-medium">Тип:</span>
                                {% if doc.doc_type.value == 'vacation_paid' %}
                                    Відпустка (оплачувана)
                                {% elif doc.doc_type.value == 'vacation_unpaid' %}
                                    Відпустка (без збереження)
                                {% else %}
                                    Продовження контракту
                                {% endif %}
                            </p>
                            <p>
                                <span class="font-medium">Період:</span>
                                {{ doc.date_start.strftime('%d.%m.%Y') }} — 
                                {{ doc.date_end.strftime('%d.%m.%Y') }}
                                ({{ doc.days_count }} днів)
                            </p>
                            <p class="text-xs text-gray-500">
                                Створено: {{ doc.created_at.strftime('%d.%m.%Y о %H:%M') }}
                            </p>
                        </div>
                    </div>

                    <!-- Upload Button -->
                    <div class="ml-6">
                        <form 
                            hx-post="/api/upload/{{ doc.id }}" 
                            hx-encoding="multipart/form-data"
                            hx-target="#status-{{ doc.id }}"
                            hx-indicator="#spinner-{{ doc.id }}"
                            class="flex flex-col items-center"
                        >
                            <label class="cursor-pointer">
                                <input 
                                    type="file" 
                                    name="file" 
                                    accept="image/*,.pdf"
                                    class="hidden"
                                    onchange="this.form.requestSubmit()"
                                    required
                                />
                                <div class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition-colors">
                                    📸 Завантажити
                                </div>
                            </label>
                            
                            <div id="spinner-{{ doc.id }}" class="htmx-indicator mt-2">
                                <svg class="animate-spin h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                            </div>
                            
                            <div id="status-{{ doc.id }}" class="mt-2 text-sm"></div>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}

            {% if not documents %}
            <div class="bg-white rounded-lg shadow-md p-12 text-center">
                <div class="text-6xl mb-4">✅</div>
                <h3 class="text-2xl font-semibold text-gray-900 mb-2">
                    Немає документів на підписі
                </h3>
                <p class="text-gray-600">
                    Всі документи оброблено або ще не створено
                </p>
            </div>
            {% endif %}
        </div>
    </div>

    <!-- WebSocket для real-time оновлень -->
    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'document_signed') {
                // Оновити сторінку при підписанні
                location.reload();
            }
        };
        
        // Keep-alive ping
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'ping'}));
            }
        }, 30000);
    </script>
</body>
</html>
```

---

## 🧪 Тестування

### Unit Tests

```python
# tests/unit/test_grammar_service.py
import pytest
from backend.services.grammar_service import GrammarService
from shared.enums import DocumentType

@pytest.fixture
def grammar():
    return GrammarService()

def test_to_genitive_male(grammar):
    """Тест родового відмінку для чоловічого ПІБ"""
    assert grammar.to_genitive("Іванов Іван Іванович") == "Іванова Івана Івановича"
    assert grammar.to_genitive("Петренко Петро Петрович") == "Петренка Петра Петровича"

def test_to_genitive_female(grammar):
    """Тест родового відмінку для жіночого ПІБ"""
    assert grammar.to_genitive("Коваленко Анна Іванівна") == "Коваленко Анни Іванівни"

def test_format_for_vacation(grammar):
    """Тест форматування ПІБ для відпустки"""
    result = grammar.format_for_document(
        "Ляшенко Анна Сергіївна",
        DocumentType.VACATION_PAID
    )
    assert result == "Анна ЛЯШЕНКО"

def test_format_for_extension(grammar):
    """Тест форматування ПІБ для продовження"""
    result = grammar.format_for_document(
        "Судаков Андрій Олександрович",
        DocumentType.TERM_EXTENSION
    )
    assert result == "СУДАКОВ Андрій"
```

```python
# tests/unit/test_validation_service.py
import pytest
from datetime import date
from backend.services.validation_service import ValidationService
from shared.exceptions import ValidationError

def test_weekend_validation():
    """Тест валідації вихідних днів"""
    service = ValidationService()
    
    # Субота (5)
    with pytest.raises(ValidationError, match="припадає на вихідний"):
        service.validate_vacation_dates(
            date(2025, 7, 5),  # Субота
            date(2025, 7, 18),
            staff=mock_staff()
        )

def test_working_days_calculation():
    """Тест підрахунку робочих днів"""
    service = ValidationService()
    
    # Повний тиждень (Пн-Пт)
    days = service.calculate_working_days(
        date(2025, 7, 7),   # Понеділок
        date(2025, 7, 11)   # П'ятниця
    )
    assert days == 5
    
    # З вихідними
    days = service.calculate_working_days(
        date(2025, 7, 7),   # Понеділок
        date(2025, 7, 13)   # Неділя
    )
    assert days == 5  # Тільки робочі дні
```

### Integration Tests

```python
# tests/integration/test_document_flow.py
import pytest
from sqlalchemy.orm import Session
from backend.models.staff import Staff
from backend.models.document import Document
from backend.services.document_service import DocumentService
from shared.enums import DocumentType, DocumentStatus

@pytest.mark.asyncio
async def test_full_document_lifecycle(db: Session):
    """Тест повного життєвого циклу документа"""
    
    # 1. Створення співробітника
    staff = Staff(
        pib_nom="Тестовий Тест Тестович",
        position="Доцент",
        rate=1.0,
        term_start=date(2024, 1, 1),
        term_end=date(2025, 12, 31),
        vacation_balance=28
    )
    db.add(staff)
    db.commit()
    
    # 2. Створення документа
    doc = Document(
        staff_id=staff.id,
        doc_type=DocumentType.VACATION_PAID,
        date_start=date(2025, 7, 7),
        date_end=date(2025, 7, 18),
        days_count=10
    )
    db.add(doc)
    db.commit()
    
    assert doc.status == DocumentStatus.DRAFT
    
    # 3. Генерація .docx
    service = DocumentService(db, grammar_service)
    path = service.generate_document(doc)
    
    assert path.exists()
    assert doc.status == DocumentStatus.ON_SIGNATURE
    
    # 4. Завантаження скану (симуляція)
    doc.file_scan_path = "storage/test_scan.pdf"
    doc.status = DocumentStatus.SIGNED
    db.commit()
    
    # 5. Обробка (списання днів)
    doc.status = DocumentStatus.PROCESSED
    staff.vacation_balance -= doc.days_count
    db.commit()
    
    assert staff.vacation_balance == 18
    assert doc.status == DocumentStatus.PROCESSED
```

---

## 📋 Чеклист перед релізом

### Функціональність
- [ ] Всі типи документів генеруються коректно
- [ ] Морфологія працює для 20+ тестових ПІБ
- [ ] Валідація дат блокує вихідні
- [ ] Статуси переключаються згідно з діаграмою
- [ ] Rollback видаляє файли та переміщає скани
- [ ] Web Portal завантажує файли та синхронізується
- [ ] Критичні сповіщення (< 30 днів) працюють

### UI/UX
- [ ] Всі тексти українською
- [ ] Кольорові індикатори відповідають статусам
- [ ] Live Preview оновлюється миттєво
- [ ] Немає "мертвих" кнопок
- [ ] Форми мають placeholder texts

### Технічне
- [ ] Unit tests покривають 80%+ логіки
- [ ] Integration tests проходять
- [ ] Логування налаштовано (structlog)
- [ ] Backup скрипт протестовано
- [ ] Docker Compose запускається з першого разу

### Документація
- [ ] README.md з інструкціями запуску
- [ ] API документація (FastAPI автогенерація)
- [ ] Коментарі до складних функцій
- [ ] .env.example з усіма змінними

---

## 🚀 Пріоритети розробки (MVP → Full)

### Phase 1: MVP (2 тижні)
1. Базова структура проекту
2. ORM моделі + міграції
3. CRUD для персоналу (Desktop UI)
4. Grammar Service
5. Генерація 1 типу документа (відпустка оплачувана)

### Phase 2: Core Features (2 тижні)
6. Решта типів документів
7. Validation Service
8. Візуальний конструктор з Live Preview
9. Система статусів
10. Річний графік

### Phase 3: Web Integration (1 тиждень)
11. FastAPI endpoints
12. Upload Portal
13. WebSocket синхронізація

### Phase 4: Polish (1 тиждень)
14. Тести
15. Темна тема
16. Error handling
17. Логування

---

## 💡 Креативні доповнення

### 1. Автопідказки при введенні ПІБ
Під час введення нового співробітника, система може аналізувати ПІБ та автоматично визначати рід для коректного відмінювання.

### 2. Dashboard зі статистикою
```python
# Аналітика на головній сторінці
- Скільки днів відпустки використано цього року
- Top-3 місяці по навантаженню
- Хто не планував відпустку
- Графік закінчення контрактів (timeline)
```

### 3. Export до Excel
```python
from openpyxl import Workbook

def export_annual_schedule_to_excel(year: int) -> Path:
    """Експортує річний графік у красиву Excel таблицю"""
    wb = Workbook()
    ws = wb.active
    # Форматування, кольори, формули
    return path_to_file
```

### 4. Email нотифікації
```python
from fastapi_mail import FastMail

async def notify_dept_head(document: Document):
    """Відправляє листа завідувачу про нову заяву"""
    await mail.send_message(
        subject=f"Нова заява: {document.staff.pib_nom}",
        recipients=[settings.dept_head_email],
        body=f"На підписі: відпустка з {document.date_start}"
    )
```

### 5. Темна тема з автоперемиканням
```python
# utils/theme.py
import darkdetect

def apply_theme(window: QMainWindow):
    """Застосовує тему згідно з системними налаштуваннями"""
    is_dark = darkdetect.isDark()
    
    if is_dark:
        # Dracula palette
        window.setStyleSheet(load_dark_stylesheet())
    else:
        # Light Material
        window.setStyleSheet(load_light_stylesheet())
```

---

## 📞 Підтримка та зворотній зв'язок

Якщо під час розробки виникнуть питання:
1. Перевір документацію у `/docs`
2. Подивись приклади у `/tests`
3. Створи Issue у репозиторії

**Coding is poetry — пиши код так, щоб його було приємно читати через рік!** 🎨