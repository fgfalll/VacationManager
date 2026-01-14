# Configuration settings for VacationManager

# Signatories (can be updated without code changes)
SIGNATORIES = {
    'recipient': 'Ректору... Олені ФІЛОНИЧ',
    'dept_head': {'title': 'Завідувач кафедри НГІТ', 'name': 'Вікторія ДМИТРЕНКО'},
    'director': {'title': 'В.о. директора ННІНГ', 'name': 'Богдан КОРОБКО'},
    'quality_dept': {'title': 'Директор Департаменту організації навчального процесу', 'name': 'Олег МАКСИМЕНКО'}
}

# Database settings
DATABASE_URL = 'sqlite:///vacation_manager.db'
# For production, use PostgreSQL:
# DATABASE_URL = 'postgresql://user:password@localhost/vacation_manager'

# File paths
SCANS_DIRECTORY = 'scans'
TEMPLATES_DIRECTORY = 'templates'

# Leave types
LEAVE_TYPES = {
    'PAID': 'Оплачувана відпустка',
    'UNPAID': 'Відпустка без збереження заробітної плати'
}

# Employment types
EMPLOYMENT_TYPES = {
    'MAIN': 'Основне місце',
    'EXTERNAL': 'Зовнішній сумісник',
    'INTERNAL': 'Внутрішній сумісник'
}

# Positions list
POSITIONS = [
    'Завідувач кафедри',
    'В.О. завідувача кафедри',
    'Професор',
    'Доцент',
    'Старший викладач',
    'Асистент',
    'Фахівець'
]

# Document statuses
STATUSES = {
    'DRAFT': 'Створено',
    'ON_SIGNATURE': 'На підписі',
    'SIGNED': 'Підписано',
    'TIMESHEET_PROCESSED': 'Додано до табелю'
}

# Academic degrees
ACADEMIC_DEGREES = [
    'К.т.н',
    'Д.т.н',
    'PhD',
    'без ступеня'
]

# Department/Faculty configuration
# Update these values to match your institution's structure
DEPARTMENT_NAME = "кафедри нафтогазової інженерії та технологій"
FACULTY_NAME = "факультету інформатики та комп'ютерної науки"
UNIVERSITY_NAME = "НТУУ «КПІ»"

# Note: In the document, the position genitive case is followed by DEPARTMENT_NAME
# Example: "асистента кафедри нафтогазової інженерії та технологій"

# Ukrainian months
MONTHS_UK = {
    1: 'січня',
    2: 'лютого',
    3: 'березня',
    4: 'квітня',
    5: 'травня',
    6: 'червня',
    7: 'липня',
    8: 'серпня',
    9: 'вересня',
    10: 'жовтня',
    11: 'листопада',
    12: 'грудня'
}