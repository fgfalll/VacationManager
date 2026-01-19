
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Force database path to be the one in root
root_db_path = Path(__file__).parent.parent / "vacation_manager.db"
os.environ["DATABASE_URL"] = f"sqlite:///{root_db_path}"

from backend.core.database import SessionLocal
from backend.models.settings import SystemSettings, Approvers
from backend.models.staff import Staff

from sqlalchemy import inspect

def check_settings():
    db = SessionLocal()
    try:
        inspector = inspect(db.get_bind())
        print("Tables found:", inspector.get_table_names())
        
        # Check if settings exists under a different name
        if "system_settings" in inspector.get_table_names():
             print("Found system_settings table!")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_settings()
