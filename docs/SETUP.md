# VacationManager v5.5 - First Time Setup

## Prerequisites

- Python 3.11 or higher
- pip (Python package installer)
- Git (optional, for version control)

## Installation Steps

### 1. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or with development tools (optional):

```bash
pip install pytest pytest-cov black ruff mypy
```

### 3. Configure Environment

```bash
# Copy example environment file
copy .env.example .env
```

Edit `.env` and update the following values:
- `VM_SECRET_KEY` - Generate a secure random key
- `VM_DATABASE_URL` - SQLite path (default is fine for development)
- `VM_STORAGE_DIR` - Where to store generated documents

### 4. Initialize Database

```bash
# Run database migrations
python -m backend.alembic_migration init
python -m backend.alembic_migration upgrade head
```

### 5. Create Storage Directories

```bash
# Create base storage structure
python -c "import os; os.makedirs('storage/obsolete', exist_ok=True)"
```

## Running the Application

### Desktop App
```bash
python -m desktop.app
```

### Web Server (Backend + Upload Portal)
```bash
python -m backend.main
```

The web interface will be available at: http://127.0.0.1:8000

## Development Tools

### Code Formatting
```bash
black .
ruff check .
```

### Type Checking
```bash
mypy .
```

### Running Tests
```bash
pytest
```

## Project Structure (After Setup)

```
Вак/
├── backend/          # FastAPI backend
├── desktop/          # PyQt6 desktop app
├── shared/           # Shared utilities
├── storage/          # Generated documents
├── templates/        # Word document templates
├── tests/            # Test suite
├── .env              # Environment config (create this)
└── requirements.txt  # Python dependencies
```

## Troubleshooting

**Issue**: `ModuleNotFoundError: No module named 'PyQt6'`
- **Solution**: Make sure virtual environment is activated, then run `pip install -r requirements.txt`

**Issue**: Ukrainian grammar not working
- **Solution**: Verify pymorphy3-dicts-uk is installed: `pip install pymorphy3-dicts-uk>=3.1.0`

**Issue**: Database migration errors
- **Solution**: Delete `vacation_manager.db` and re-run migrations

## Next Steps

1. Review the [DESIGN.md](./DESIGN.md) for architecture details
2. Check [CLAUDE.md](./CLAUDE.md) for development guidelines
3. Start with Phase 1: ORM models and Staff CRUD
