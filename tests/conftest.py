"""Конфігурація pytest для тестів."""

import pytest
from pathlib import Path
import tempfile
import shutil

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.models import Base
from backend.core.database import get_db


@pytest.fixture
def temp_db():
    """
    Створює тимчасову базу даних для тестів.

    Yields:
        Шлях до тимчасової бази даних
    """
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    yield db_url

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def db_session(temp_db):
    """
    Створює сесію бази даних для тестів.

    Args:
        temp_db: URL тимчасової бази даних

    Yields:
        Сесія SQLAlchemy
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(temp_db, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_staff(db_session):
    """
    Створює тестового співробітника.

    Args:
        db_session: Сесія бази даних

    Returns:
        Об'єкт Staff
    """
    from backend.models.staff import Staff
    from datetime import date
    from decimal import Decimal
    from shared.enums import EmploymentType, WorkBasis

    staff = Staff(
        pib_nom="Тестовий Тест Тестович",
        degree="к.т.н.",
        rate=Decimal("1.0"),
        position="Доцент",
        employment_type=EmploymentType.MAIN,
        work_basis=WorkBasis.CONTRACT,
        term_start=date(2024, 1, 1),
        term_end=date(2025, 12, 31),
        vacation_balance=28,
    )
    db_session.add(staff)
    db_session.commit()
    db_session.refresh(staff)

    return staff
