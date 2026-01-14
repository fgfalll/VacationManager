from datetime import date, datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from config import DATABASE_URL

Base = declarative_base()

class EmploymentType(Enum):
    MAIN = "Основне місце"
    EXTERNAL = "Зовнішній сумісник"
    INTERNAL = "Внутрішній сумісник"

class LeaveType(Enum):
    PAID = "Оплачувана відпустка"
    UNPAID = "Відпустка без збереження заробітної плати"

class Status(Enum):
    DRAFT = "Створено"
    ON_SIGNATURE = "На підписі"
    SIGNED = "Підписано"
    TIMESHEET_PROCESSED = "Додано до табелю"

class Staff(Base):
    __tablename__ = 'staff'

    id = Column(Integer, primary_key=True)
    full_name = Column(String(255), nullable=False)
    academic_degree = Column(String(50))
    rate = Column(Float, default=1.0)
    position = Column(String(100))
    employment_type = Column(String(50))
    employment_start = Column(Date)
    employment_end = Column(Date)

    # Relationships
    requests = relationship("VacationRequest", back_populates="staff")

    def __repr__(self):
        return f"<Staff(id={self.id}, name='{self.full_name}', position='{self.position}')>"

class LeaveReason(Base):
    __tablename__ = 'leave_reasons'

    id = Column(Integer, primary_key=True)
    reason_text = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LeaveReason(id={self.id}, text='{self.reason_text}')>"

class VacationRequest(Base):
    __tablename__ = 'vacation_requests'

    id = Column(Integer, primary_key=True)
    staff_id = Column(Integer, ForeignKey('staff.id'), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_days = Column(Integer, nullable=False)
    leave_type = Column(String(50), nullable=False)
    reason_text = Column(Text)
    status = Column(String(50), default=Status.DRAFT.value)
    scan_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    timesheet_processed = Column(Boolean, default=False)

    # Relationships
    staff = relationship("Staff", back_populates="requests")

    def __repr__(self):
        return f"<VacationRequest(id={self.id}, staff_id={self.staff_id}, status='{self.status}')>"

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_default_data():
    """Initialize default data for leave reasons"""
    db = SessionLocal()
    try:
        # Check if default reason exists
        default_reason = "відпусткою за основним місцем роботи"
        existing = db.query(LeaveReason).filter_by(reason_text=default_reason).first()
        if not existing:
            db.add(LeaveReason(reason_text=default_reason))
            db.commit()
    finally:
        db.close()