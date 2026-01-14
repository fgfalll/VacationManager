# Enhanced Vacation System - Quick Start

## Overview
The VacationManager now includes an enhanced vacation dialog that supports complex vacation scheduling.

## Features

### 1. Continuous Period
- Simple date range selection (start and end dates)
- Automatic day calculation
- Example: 29.12.2025 - 21.01.2026 (24 days)

### 2. Split Periods
- Multiple separate vacation periods
- Add/remove periods dynamically
- Each period has its own start and end date
- Automatic total days calculation
- Examples supported:
  - 30.12.2025 - 01.01.2026 (3 days)
  - 02.01.2026 - 16.01.2026 (11 days)
  - 29.12.2025 - 31.12.2025 (3 days)

### 3. Custom Description
- Free text input for complex scenarios
- Manual total days entry
- Examples:
  ```
  з 29.12.2025 по 31.12.2025 (3 дні)
  з 05.01.2026 по 09.01.2026 (5 днів)
  з 12.01.2026 по 16.01.2026 (5 днів)
  ```

## How to Use

1. **Run the Desktop Application**:
   ```bash
   cd VacationManager
   pip install -r requirements.txt
   python run_desktop.py
   ```

2. **Add Staff Members**:
   - Click "Додати співробітника" button
   - Fill in staff details
   - Click OK to save

3. **Create Vacation Request**:
   - Select a staff member from the list
   - Click "Створити заяву"
   - Choose vacation type:
     - **Неперервний період**: For continuous vacations
     - **Розділені періоди**: For split vacations
     - **Користувацький**: For custom descriptions

4. **Fill in Details**:
   - **Continuous**: Select start and end dates
   - **Split**: Click "Додати період" for each vacation segment
   - **Custom**: Enter description and total days

5. **Save the Request**:
   - Click OK to generate the document
   - The document will be saved in the `generated_docs` folder

## Document Generation

The system automatically generates Ukrainian vacation documents with:
- Correct formatting for each vacation type
- Proper date formatting (dd.MM.yyyy)
- Signature lines for required approvals
- Staff and department information

## Examples

### Example 1: Continuous Vacation
```
Type: Неперервний період
Start: 29.12.2025
End: 21.01.2026
Total: 24 days
```

### Example 2: Split Vacation
```
Type: Розділені періоди
Period 1: 29.12.2025 - 31.12.2025 (3 days)
Period 2: 02.01.2026 - 16.01.2026 (15 days)
Total: 18 days
```

### Example 3: Custom Description
```
Type: Користувацький
Description: з 29.12.2025 по 31.12.2025 (3 дні), з 05.01.2026 по 09.01.2026 (5 днів)
Total: 8 days
```

## Notes

- The system automatically calculates total days
- For split vacations, you can add as many periods as needed
- Custom descriptions support any text format
- All generated documents are in Ukrainian
- The system saves staff vacation history in the database

## Troubleshooting

If the enhanced dialog doesn't appear:
1. Ensure PyQt6 is installed: `pip install PyQt6`
2. Check that all files are in the VacationManager directory
3. Run the application from the VacationManager directory

The enhanced vacation system is now fully integrated and ready to use!