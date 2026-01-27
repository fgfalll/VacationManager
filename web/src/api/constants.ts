/** System enums mapped to backend shared/enums.py */

// Staff position enum (from shared.enums.StaffPosition)
export enum StaffPosition {
  HEAD_OF_DEPARTMENT = 'head_of_department',
  ACTING_HEAD_OF_DEPARTMENT = 'acting_head',
  PROFESSOR = 'professor',
  ASSOCIATE_PROFESSOR = 'associate_professor',
  SENIOR_LECTURER = 'senior_lecturer',
  LECTURER = 'lecturer',
  SPECIALIST = 'specialist',
}

// Position labels for UI display
export const STAFF_POSITION_LABELS: Record<StaffPosition, string> = {
  [StaffPosition.HEAD_OF_DEPARTMENT]: 'Завідувач кафедри',
  [StaffPosition.ACTING_HEAD_OF_DEPARTMENT]: 'В.о завідувача кафедри',
  [StaffPosition.PROFESSOR]: 'Професор',
  [StaffPosition.ASSOCIATE_PROFESSOR]: 'Доцент',
  [StaffPosition.SENIOR_LECTURER]: 'Старший викладач',
  [StaffPosition.LECTURER]: 'Асистент',
  [StaffPosition.SPECIALIST]: 'Фахівець',
};

// Employment type enum (from shared.enums.EmploymentType)
export enum EmploymentType {
  MAIN = 'main',
  EXTERNAL = 'external',
  INTERNAL = 'internal',
}

// Employment type labels for UI display
export const EMPLOYMENT_TYPE_LABELS: Record<EmploymentType, string> = {
  [EmploymentType.MAIN]: 'Основне місце роботи',
  [EmploymentType.EXTERNAL]: 'Зовнішній сумісник',
  [EmploymentType.INTERNAL]: 'Внутрішній сумісник',
};

// Work basis enum (from shared.enums.WorkBasis)
export enum WorkBasis {
  CONTRACT = 'contract',
  COMPETITIVE = 'competitive',
  STATEMENT = 'statement',
}

// Work basis labels for UI display
export const WORK_BASIS_LABELS: Record<WorkBasis, string> = {
  [WorkBasis.CONTRACT]: 'Контракт',
  [WorkBasis.COMPETITIVE]: 'Конкурсна основа',
  [WorkBasis.STATEMENT]: 'Заява',
};

// Staff action type enum (from shared.enums.StaffActionType)
export enum StaffActionType {
  CREATE = 'create',
  UPDATE = 'update',
  DEACTIVATE = 'deactivate',
  RESTORE = 'restore',
}

// Staff action type labels for UI display
export const STAFF_ACTION_LABELS: Record<StaffActionType, string> = {
  [StaffActionType.CREATE]: 'Створення',
  [StaffActionType.UPDATE]: 'Оновлення',
  [StaffActionType.DEACTIVATE]: 'Деактивація',
  [StaffActionType.RESTORE]: 'Відновлення',
};

// Attendance codes (from backend/models/attendance.py ATTENDANCE_CODES)
export const ATTENDANCE_CODES: Record<string, string> = {
  'Р': 'Години роботи',
  'РС': 'Неповний робочий день',
  'ВЧ': 'Вечірні години',
  'РН': 'Нічні години',
  'НУ': 'Надурочні',
  'РВ': 'Робота у вихідні',
  'ВД': 'Відрядження',
  'В': 'Відпустка основна',
  'Д': 'Відпустка додаткова',
  'Ч': 'Відпустка чорнобильцям',
  'ТВ': 'Творча відпустка',
  'Н': 'Навчальна відпустка',
  'ДО': 'Відпустка з дітьми',
  'ВП': 'Вагітність та пологи',
  'ДД': 'Догляд за дитиною',
  'НБ': 'Відпустка без збереження (навчання)',
  'ДБ': 'Відпустка без збереження (обов\'язкова)',
  'НА': 'Відпустка без збереження (за згодою)',
  'БЗ': 'Інша відпустка без збереження',
  'НД': 'Неявка (неповний день)',
  'НП': 'Неявка (переведення)',
  'ІН': 'Інший невідпрацьований час',
  'П': 'Простої',
  'ПР': 'Прогули',
  'С': 'Страйки',
  'ТН': 'Лікарняний оплачуваний',
  'НН': 'Лікарняний неоплачуваний',
  'НЗ': 'Неявка нез\'ясована',
  'ІВ': 'Інші неявки',
  'І': 'Інші причини',
};

// Helper functions to get label from value
export function getPositionLabel(value: string): string {
  return STAFF_POSITION_LABELS[value as StaffPosition] || value;
}

export function getEmploymentTypeLabel(value: string): string {
  return EMPLOYMENT_TYPE_LABELS[value as EmploymentType] || value;
}

export function getWorkBasisLabel(value: string): string {
  return WORK_BASIS_LABELS[value as WorkBasis] || value;
}

export function getActionTypeLabel(value: string): string {
  return STAFF_ACTION_LABELS[value as StaffActionType] || value;
}

export function getAttendanceCodeLabel(code: string): string {
  return ATTENDANCE_CODES[code] || code;
}

// Ukrainian document type labels
export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  vacation_paid: 'Відпустка оплачувана',
  vacation_main: 'Основна щорічна відпустка',
  vacation_additional: 'Додаткова щорічна відпустка',
  vacation_chornobyl: 'Додаткова відпустка чорнобильцям',
  vacation_creative: 'Творча відпустка',
  vacation_study: 'Навчальна відпустка',
  vacation_children: "Відпустка працівникам з дітьми",
  vacation_maternity: "Відпустка у зв'язку з вагітністю та пологами",
  vacation_childcare: 'Відпустка для догляду за дитиною',
  vacation_unpaid: 'Відпустка без збереження зарплати',
  vacation_unpaid_study: 'Навчальна відпустка без збереження зарплати',
  vacation_unpaid_mandatory: "Відпустка без збереження (обов'язкова)",
  vacation_unpaid_agreement: 'Відпустка без збереження (за згодою)',
  vacation_unpaid_other: 'Інша відпустка без збереження зарплати',
  term_extension: 'Продовження терміну контракту',
  term_extension_contract: 'Продовження контракту (контракт)',
  term_extension_competition: 'Продовження контракту (конкурс)',
  term_extension_pdf: 'Продовження контракту (PDF)',
  employment_contract: 'Прийом на роботу (контракт)',
  employment_competition: 'Прийом на роботу (конкурс)',
  employment_pdf: 'Прийом на роботу (PDF)',
};
