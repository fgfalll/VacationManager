# VacationManager - Placeholders Reference

This document describes all placeholders used in the VacationManager system for document generation.

## Document Placeholders

### Basic Information Placeholders

| Placeholder | Description | Example Value |
|-------------|-------------|---------------|
| `{{recipient}}` | The recipient of the vacation request | "Ректору... Олені ФІЛОНИЧ" |
| `{{staff_genitive}}` | Staff name in genitive case | "Ларцевої Ірини Ігорівни" |
| `{{position_genitive}}` | Staff position in genitive case | "асистента" |
| `{{start_date}}` | Vacation start date | "01.01.2024" |
| `{{end_date}}` | Vacation end date | "14.01.2024" |
| `{{total_days}}` | Total number of vacation days | "14" |

### Conditional Placeholders

#### Paid Leave Only
| Placeholder | Description | Example Value |
|-------------|-------------|---------------|
| `{{payment_phrase}}` | Payment timing phrase based on start date | "у першій половині січня" |

#### Unpaid Leave Only
| Placeholder | Description | Example Value |
|-------------|-------------|---------------|
| `{{reason_text}}` | Reason for unpaid leave | "відпусткою за основним місцем роботи" |

### Signature Placeholders

| Placeholder | Description | Example Value | Conditional |
|-------------|-------------|---------------|-------------|
| `{{dept_head}}` | Department head name for signature | "Вікторія ДМИТРЕНКО" | Hidden if staff is department head |
| `{{director}}` | Director name for signature | "Богдан КОРОБКО" | Always shown |
| `{{quality_dept}}` | Quality department name for signature | "Олег МАКСИМЕНКО" | Always shown |

## Template Structure

### Paid Leave Document Structure
```
{{recipient}}

{{staff_genitive}}
{{position_genitive}} {DEPARTMENT_NAME}
{FACULTY_NAME}
{UNIVERSITY_NAME}


ЗАЯВА

Прошу надати мені щорічну відпустку з {{start_date}} по {{end_date}}
терміном на {{total_days}} календарних днів.

Заробітну плату за час відпустки прошу виплатити {{payment_phrase}}.


[Signature Section]
ЗАВ. КАФЕДРОЙ                                     {{director}}
Директор ДІЦТ                                     {{quality_dept}}
Зав. кафедрою                                      {{dept_head}}

                                        {{staff_genitive}}
                                        «____» ____________ 202__ р.
```

### Unpaid Leave Document Structure
```
{{recipient}}

{{staff_genitive}}
{{position_genitive}} {DEPARTMENT_NAME}
{FACULTY_NAME}
{UNIVERSITY_NAME}


ЗАЯВА

Прошу надати мені відпустку без збереження заробітної плати
з {{start_date}} по {{end_date}} терміном на {{total_days}} календарних днів
у зв'язку з {{reason_text}}.


[Signature Section]
ЗАВ. КАФЕДРОЙ                                     {{director}}
Директор ДІЦТ                                     {{quality_dept}}
Зав. кафедрою                                      {{dept_head}}

                                        {{staff_genitive}}
                                        «____» ____________ 202__ р.
```

## Special Logic

### Department Head Handling
When the staff member is a department head ("завідувач кафедри" or "в.о. завідувача кафедри"):
- The `{{dept_head}}` placeholder is replaced with an empty string
- The entire "Зав. кафедрою" signature line is removed
- The position remains in nominative case (not converted to genitive)

### Payment Phrase Logic
The `{{payment_phrase}}` is generated based on the vacation start date:
- Days 1-15: "у першій половині {month_name}"
- Days 16-31: "у другій половині {month_name}"

### Position Genitive Case Rules
| Position | Genitive Form |
|----------|---------------|
| завідувач кафедри | завідувач кафедри (no change for dept head) |
| В.О. завідувача кафедри | В.О. завідувача кафедри (no change for dept head) |
| Професор | професора |
| Доцент | доцента |
| Старший викладач | старшого викладача |
| Асистент | асистента |
| Фахівець | фахівця |

## Configuration Values
These values are defined in `config.py` and can be customized:

| Variable | Description | Current Value |
|----------|-------------|---------------|
| `DEPARTMENT_NAME` | Department name in genitive case | "кафедри нафтогазової інженерії та технологій" |
| `FACULTY_NAME` | Faculty name in genitive case | "факультету інформатики та комп'ютерної науки" |
| `UNIVERSITY_NAME` | University name | "НТУУ «КПІ»" |
| `SIGNATORIES['recipient']` | Document recipient | "Ректору... Олені ФІЛОНИЧ" |
| `SIGNATORIES['dept_head']` | Department head | "Вікторія ДМИТРЕНКО" |
| `SIGNATORIES['director']` | Director | "Богдан КОРОБКО" |
| `SIGNATORIES['quality_dept']` | Quality department | "Олег МАКСИМЕНКО" |

## Template Files
The system uses two template files:
- `templates/template_paid.docx` - For paid vacation requests
- `templates/template_unpaid.docx` - For unpaid vacation requests

If these files don't exist, they are automatically created using the placeholders above.