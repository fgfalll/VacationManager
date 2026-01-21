
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.staff import Staff
from backend.models.document import Document
from shared.enums import DocumentType, DocumentStatus

@pytest.fixture
def auth_headers(test_client):
    """Отримати заголовки авторизації."""
    response = test_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def clean_staff_and_docs(db_session):
    """Очистити тестових співробітників та документи."""
    db_session.query(Document).delete()
    db_session.query(Staff).filter(Staff.pib_nom.like("Test%")).delete()
    db_session.commit()
    yield
    db_session.query(Document).delete()
    db_session.query(Staff).filter(Staff.pib_nom.like("Test%")).delete()
    db_session.commit()

@pytest.fixture
def test_staff(db_session):
    """Створити тестового співробітника."""
    staff = Staff(
        pib_nom="Test User One",
        position="Tester",
        vacation_balance=24,
        term_start=date(2025, 1, 1),
        term_end=date(2025, 12, 31),
        employment_type="main",
        work_basis="contract",
        rate=1.0
    )
    db_session.add(staff)
    db_session.commit()
    db_session.refresh(staff)
    return staff

def test_validate_dates_clean(test_client, auth_headers, test_staff):
    """Валідація коректних дат."""
    response = test_client.post(
        "/api/documents/validate-dates",
        headers=auth_headers,
        json={
            "staff_id": test_staff.id,
            "doc_type": "vacation_paid",
            "date_start": "2025-06-02", # Monday
            "date_end": "2025-06-06",   # Friday
        }
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True

def test_validate_dates_weekend_start(test_client, auth_headers, test_staff):
    """Валідація початку у вихідний."""
    response = test_client.post(
        "/api/documents/validate-dates",
        headers=auth_headers,
        json={
            "staff_id": test_staff.id,
            "doc_type": "vacation_paid",
            "date_start": "2025-06-01", # Sunday
            "date_end": "2025-06-06",
        }
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "Неділя" in response.json()["message"]

def test_calculate_days(test_client, auth_headers):
    """Розрахунок днів."""
    response = test_client.post(
        "/api/documents/calculate-days",
        headers=auth_headers,
        json={
            "date_start": "2025-06-01",
            "date_end": "2025-06-10",
            "apply_martial_law": False
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["calendar_days"] == 10
    assert data["working_days"] == 7

def test_bulk_validate(test_client, auth_headers, test_staff):
    """Перевірка масової валідації."""
    response = test_client.post(
        "/api/bulk/validate",
        headers=auth_headers,
        json={
            "staff_ids": [test_staff.id],
            "doc_type": "vacation_paid",
            "date_start": "2025-06-02",
            "date_end": "2025-06-06"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["valid"]) == 1
    assert data["valid"][0]["id"] == test_staff.id

def test_bulk_generate(test_client, auth_headers, test_staff, db_session):
    """Перевірка масової генерації."""
    # Ensure no docs initially
    assert db_session.query(Document).filter(Document.staff_id == test_staff.id).count() == 0

    response = test_client.post(
        "/api/bulk/generate",
        headers=auth_headers,
        json={
            "staff_ids": [test_staff.id],
            "doc_type": "vacation_paid",
            "date_start": "2025-07-07",
            "date_end": "2025-07-11"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["generated_count"] == 1
    
    # Check doc created
    db_session.expire_all()
    count = db_session.query(Document).filter(Document.staff_id == test_staff.id).count()
    assert count == 1
