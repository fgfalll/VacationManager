"""
Скрипт для оновлення статусу блокування існуючих записів.

Цей скрипт повинен бути запущений один раз після додавання полів is_blocked та blocked_reason
до таблиць attendance та documents. Він проактивно перевіряє стан записів і встановлює
правильний статус блокування.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker

from backend.core.config import get_settings
from backend.models.attendance import Attendance
from backend.models.document import Document
from backend.models.tabel_approval import TabelApproval
from shared.enums import DocumentStatus


def update_attendance_blocked_status(db):
    """
    Оновити статус блокування для існуючих записів відвідуваності.
    Запис блокується, якщо місяць вже погоджений (затверджений).
    """
    print("Оновлення статусу блокування для записів відвідуваності...")

    # Get all attendance records that are not blocked
    query = db.query(Attendance).filter(Attendance.is_blocked == False)
    total = query.count()
    print(f"Знайдено {total} записів для перевірки")

    updated_count = 0

    for attendance in query.all():
        if not attendance.date:
            continue

        month = attendance.date.month
        year = attendance.date.year

        # Check if the month is approved
        approval = db.query(TabelApproval).filter(
            TabelApproval.month == month,
            TabelApproval.year == year,
            TabelApproval.is_correction == False,
            TabelApproval.is_approved == True
        ).first()

        if approval:
            attendance.is_blocked = True
            attendance.blocked_reason = f"Місяць {month:02d}.{year} погоджено з кадрами. Редагування заблоковано."
            updated_count += 1
            print(f"  ✓ Attendance #{attendance.id} ({attendance.date}) - заблоковано (місяць погоджено)")

    db.commit()
    print(f"Оновлено {updated_count} записів відвідуваності.")


def update_documents_blocked_status(db):
    """
    Оновити статус блокування для існуючих документів.
    Документ блокується, якщо:
    - Є завантажений скан (file_scan_path)
    - Статус = 'processed'
    """
    print("\nОновлення статусу блокування для документів...")

    # Get all documents that are not blocked
    query = db.query(Document).filter(Document.is_blocked == False)
    total = query.count()
    print(f"Знайдено {total} документів для перевірки")

    updated_count = 0

    for doc in query.all():
        should_block = False
        blocked_reason = None

        if doc.file_scan_path:
            should_block = True
            blocked_reason = "Документ має завантажений скан. Редагування заблоковано."
            print(f"  ✓ Document #{doc.id} - заблоковано (є скан)")
        elif doc.status == DocumentStatus.PROCESSED:
            should_block = True
            blocked_reason = "Документ оброблено та додано до табелю. Редагування заблоковано."
            print(f"  ✓ Document #{doc.id} - заблоковано (оброблено)")

        if should_block:
            doc.is_blocked = True
            doc.blocked_reason = blocked_reason
            updated_count += 1

    db.commit()
    print(f"Оновлено {updated_count} документів.")


def main():
    """Головна функція скрипту."""
    settings = get_settings()

    # Create database connection
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        print("=" * 60)
        print("Скрипт для оновлення статусу блокування")
        print("=" * 60)
        print(f"База даних: {settings.database_url}")
        print()

        # Update attendance records
        update_attendance_blocked_status(db)

        # Update documents
        update_documents_blocked_status(db)

        print()
        print("=" * 60)
        print("Оновлення завершено успішно!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
