"""Document rendering service using Jinja2 templates from backend/templates/documents."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader

from shared.enums import DocumentType

from backend.models.staff import Staff as StaffModel
from backend.models.settings import Approvers, SystemSettings
from backend.services.grammar_service import GrammarService

if TYPE_CHECKING:
    from backend.models.document import Document
    from backend.models.staff import Staff

# Template file mapping
TEMPLATE_MAP = {
    DocumentType.VACATION_PAID: "vacation_paid.html",
    DocumentType.VACATION_UNPAID: "vacation_unpaid.html",
    DocumentType.VACATION_CHILDREN: "vacation_children.html",
    DocumentType.VACATION_CHILDCARE: "vacation_childcare.html",
    DocumentType.VACATION_MATERNITY: "vacation_maternity.html",
    DocumentType.VACATION_STUDY: "vacation_study.html",
    DocumentType.VACATION_CREATIVE: "vacation_creative.html",
    DocumentType.VACATION_CHORNOBYL: "vacation_chornobyl.html",
    DocumentType.VACATION_ADDITIONAL: "vacation_additional.html",
    DocumentType.VACATION_MAIN: "vacation_main.html",
    DocumentType.VACATION_UNPAID_AGREEMENT: "vacation_unpaid_agreement.html",
    DocumentType.VACATION_UNPAID_MANDATORY: "vacation_unpaid_mandatory.html",
    DocumentType.VACATION_UNPAID_OTHER: "vacation_unpaid_other.html",
    DocumentType.VACATION_UNPAID_STUDY: "vacation_unpaid_study.html",
    DocumentType.TERM_EXTENSION: "term_extension.html",
    DocumentType.TERM_EXTENSION_CONTRACT: "term_extension_contract.html",
    DocumentType.TERM_EXTENSION_COMPETITION: "term_extension_competition.html",
    DocumentType.TERM_EXTENSION_PDF: "term_extension_pdf.html",
}

# Default template for unknown types
DEFAULT_TEMPLATE = "vacation_paid.html"


def format_date_ukrainian(d, include_year=True):
    """Format date in Ukrainian: '10 січня 2026 року' or '10 січня'."""
    month_names_genitive = {
        1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
        5: "травня", 6: "червня", 7: "листя", 8: "серпеня",
        9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
    }
    month = month_names_genitive.get(d.month, "")
    if include_year:
        return f"{d.day} {month} {d.year} року"
    return f"{d.day} {month}"


def format_date_range_ukrainian(start, end):
    """Format date range in Ukrainian."""
    month_names_genitive = {
        1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
        5: "травня", 6: "червня", 7: "липня", 8: "серпня",
        9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
    }

    if start == end:
        return format_date_ukrainian(start)

    if start.month == end.month and start.year == end.year:
        # Same month: "з 13 по 26 березня 2026 року"
        month = month_names_genitive.get(start.month, "")
        return f"з {start.day} по {end.day} {month} {start.year} року"

    if start.year == end.year:
        # Same year, diff month: "з 13 березня по 26 квітня 2026 року"
        return f"з {start.day} {format_date_ukrainian(start, include_year=False)} по {end.day} {format_date_ukrainian(end)}"

    return f"з {start.day} {format_date_ukrainian(start)} по {end.day} {format_date_ukrainian(end)}"


def get_templates_dir() -> Path:
    """Get the templates directory."""
    possible_paths = [
        Path(__file__).parent / "templates" / "documents",
        Path(__file__).parent.parent / "templates" / "documents",
    ]
    for path in possible_paths:
        if path.exists():
            return path
    raise FileNotFoundError(f"Templates directory not found. Searched: {[str(p) for p in possible_paths]}")


def get_settings_from_db(db_session) -> dict:
    """Get university and rector settings from database."""
    from backend.models.settings import SystemSettings

    settings = {}

    # University settings
    settings["university_name"] = SystemSettings.get_value(db_session, "university_name", "")
    settings["university_name_dative"] = SystemSettings.get_value(db_session, "university_name_dative", "")

    # Rector settings
    settings["rector_name_dative"] = SystemSettings.get_value(db_session, "rector_name_dative", "")
    settings["rector_name_nominative"] = SystemSettings.get_value(db_session, "rector_name_nominative", "")

    # Department settings
    settings["dept_name"] = SystemSettings.get_value(db_session, "dept_name", "")
    settings["dept_abbr"] = SystemSettings.get_value(db_session, "dept_abbr", "")

    # Department head
    settings["dept_head_id"] = SystemSettings.get_value(db_session, "dept_head_id", None)

    return settings


def get_signatories_from_db(db_session, staff, dept_head_id=None) -> list:
    """Get signatories from database (department head, dean, etc.)."""
    from backend.models.staff import Staff as StaffModel
    from backend.models.settings import Approvers, SystemSettings
    
    signatories = []
    
    # 1. Get Approvers from database (like in builder_tab.py)
    approvers = (
        db_session.query(Approvers)
        .order_by(Approvers.order_index)
        .all()
    )
    
    for approver in approvers:
        # Format the signatory name
        display_name = _format_signatory_name(approver.full_name_nom or approver.full_name_dav)
        
        signatories.append({
            "position": approver.position_name,
            "position_multiline": "", # Can be enhanced if we store multiline position
            "name": display_name
        })

    # 2. Filter out current staff if they are in the list
    if staff:
        staff_name_formatted = _format_signatory_name(staff.pib_nom)
        signatories = [s for s in signatories if s.get("name") != staff_name_formatted]

    # 3. Add Department Head (if not already in list)
    if not dept_head_id:
        dept_head_id = SystemSettings.get_value(db_session, "dept_head_id", None)
    
    if dept_head_id and staff:
        dept_head = db_session.query(StaffModel).filter(StaffModel.id == dept_head_id).first()
        if dept_head:
            # Check if current staff IS the department head
            is_dept_head = (staff.pib_nom == dept_head.pib_nom)

            if not is_dept_head:
                head_name_formatted = _format_signatory_name(dept_head.pib_nom)
                
                # Check if already exists in signatories
                already_exists = any(s.get("name") == head_name_formatted for s in signatories)
                
                if not already_exists:
                    # Format position
                    position = dept_head.position
                    position_multiline = ""
                    
                    # Add department abbreviation logic
                    dept_abbr = SystemSettings.get_value(db_session, "dept_abbr", "")
                    dept_name = SystemSettings.get_value(db_session, "dept_name", "") 
                    
                    # Logic from builder_tab.py
                    if dept_abbr:
                        if dept_abbr.lower() not in position.lower():
                            if "кафедр" not in position.lower():
                                position_multiline = f"кафедри {dept_abbr}"
                            else:
                                position_multiline = dept_abbr
                    elif dept_name:
                         if dept_name.lower() not in position.lower():
                            if "кафедр" not in position.lower():
                                position_multiline = f"кафедри {dept_name}"
                            else:
                                position_multiline = dept_name

                    # Insert as first signatory
                    signatories.insert(0, {
                        "position": position,
                        "position_multiline": position_multiline,
                        "name": head_name_formatted
                    })

    return signatories

def _format_signatory_name(full_name: str) -> str:
    """
    Formats name like 'Іванов Іван Іванович' to 'Іван ІВАНОВ'.
    Matches builder_tab.py `_format_signatory_name`.
    """
    if not full_name:
        return ""
        
    parts = full_name.split()
    if len(parts) >= 3:
        # "Іванов Іван Іванович" -> "Іван ІВАНОВ"
        # Surname is first, Name is second
        surname = parts[0].upper()
        name = parts[1]
        return f"{name} {surname}"
    elif len(parts) == 2:
        # "Іванов Іван" -> "Іван ІВАНОВ"
        surname = parts[0].upper()
        name = parts[1]
        return f"{name} {surname}"
    return full_name



def render_document_html(
    doc_type: DocumentType,
    staff_name: str,
    staff_position: str,
    date_start,
    date_end,
    days_count: int | None = None,
    payment_period: str | None = None,
    custom_text: str | None = None,
    signatories: list | None = None,
    db_session: Any = None,
    staff_id: int | None = None,
    employment_type: str | None = None,
) -> str:
    """
    Render document HTML using template from backend/templates/documents.

    Args:
        doc_type: Type of document
        staff_name: Staff full name (ПІБ)
        staff_position: Staff position
        date_start: Start date
        date_end: End date
        days_count: Number of days (optional)
        payment_period: Payment period (optional)
        custom_text: Custom text to add (optional)
        signatories: List of signatories for approvals (optional)
        db_session: Database session to fetch settings (optional)
        staff_id: Staff ID for fetching additional data
        employment_type: Employment type for notes

    Returns:
        Rendered HTML string
    """
    from backend.models.staff import Staff as StaffModel

    # Instantiate GrammarService
    from backend.services.grammar_service import GrammarService
    grammar = GrammarService()

    templates_dir = get_templates_dir()

    jinja_env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )

    # Get template filename from mapping
    template_filename = TEMPLATE_MAP.get(doc_type, DEFAULT_TEMPLATE)

    try:
        template = jinja_env.get_template(template_filename)
    except Exception:
        # Fallback to default template
        template = jinja_env.get_template(DEFAULT_TEMPLATE)

    # Format dates for display
    if hasattr(date_start, 'strftime'):
        date_start_str = format_date_ukrainian(date_start)
    else:
        date_start_str = str(date_start)

    if hasattr(date_end, 'strftime'):
        date_end_str = format_date_ukrainian(date_end)
    else:
        date_end_str = str(date_end)

    formatted_dates = format_date_range_ukrainian(
        date_start if hasattr(date_start, 'strftime') else date_start,
        date_end if hasattr(date_end, 'strftime') else date_end
    )

    # Get settings from database if session provided
    db_settings = {}
    db_signatories = []
    if db_session:
        db_settings = get_settings_from_db(db_session)

        # Get staff from db if we have staff_id
        db_staff = None
        if staff_id:
            db_staff = db_session.query(StaffModel).filter(StaffModel.id == staff_id).first()

        # Get signatories from database
        db_signatories = get_signatories_from_db(db_session, db_staff, db_settings.get("dept_head_id"))

    # Merge signatories: passed in > from database
    final_signatories = signatories if signatories else db_signatories

    # Get employment type note
    employment_type_note = ""
    if employment_type:
        if employment_type == "internal":
            employment_type_note = "(внутрішнє сумісництво)"
        elif employment_type == "external":
            employment_type_note = "(зовнішнє сумісництво)"

    # Format days count with correct Ukrainian grammar
    days_formatted = ""
    if days_count:
        if days_count == 1:
            days_formatted = "1 календарний день"
        elif days_count in (2, 3, 4):
            days_formatted = f"{days_count} календарні дні"
        else:
            days_formatted = f"{days_count} календарних днів"

    # Improve staff position formatting (match desktop builder logic)
    staff_position_nom = staff_position
    if staff_position:
        # Capitalize first letter
        staff_position_capitalized = staff_position[0].upper() + staff_position[1:]
        staff_position_nom = staff_position_capitalized
        
        # Add department info if needed
        dept_name = db_settings.get("dept_name", "")
        dept_abbr = db_settings.get("dept_abbr", "")
        dept_for_position = dept_abbr if dept_abbr else dept_name
        
        if dept_for_position:
            position_lower = staff_position.lower()
            
            # Logic to append department if missing
            append_dept = False
            
            # Case 1: Academic position without "department" word
            if "кафедри" not in position_lower and "кафедру" not in position_lower and "кафедр" not in position_lower:
                if any(x in position_lower for x in ["професор", "доцент", "асистент", "викладач", "старший викладач", "фахівець"]):
                     staff_position_nom = f"{staff_position_capitalized} кафедри {dept_for_position}"
            
            # Case 2: Position contains "department" but specific name/abbr is missing
            # e.g. "В.о завідувача кафедри" -> "В.о завідувача кафедри НГіТ"
            else:
                 dept_mentioned = False
                 if dept_abbr and dept_abbr.lower() in position_lower:
                     dept_mentioned = True
                 if dept_name and dept_name.lower() in position_lower:
                     dept_mentioned = True
                 
                 if not dept_mentioned and "кафедри" in position_lower:
                     staff_position_nom = f"{staff_position_capitalized} {dept_for_position}"

    context = {
        # University and rector from database
        "university_name": db_settings.get("university_name", ""),
        "university_name_dative": db_settings.get("university_name_dative", ""),
        "rector_name": db_settings.get("rector_name_dative", ""),  # Uses dative for header
        "rector_name_nominative": db_settings.get("rector_name_nominative", ""),

        # Department info
        "dept_name": db_settings.get("dept_name", ""),
        "dept_abbr": db_settings.get("dept_abbr", ""),

        # Staff info
        "staff_position_nom": staff_position_nom,  # Nominative for header (enhanced)
        "staff_position": staff_position,       # For signature block (keep original usually)
        "staff_name_nom": staff_name,           # Nominative for signature
        "staff_name_gen": staff_name,           # Genitive for header

        # Employment type note
        "employment_type_note": employment_type_note,

        # Date and duration info
        "days_count": days_formatted if days_formatted else (days_count or 0),
        "formatted_dates": formatted_dates,
        "date_start": date_start_str,
        "date_end": date_end_str,

        # Payment info
        "payment_period": payment_period or "",

        # Custom text
        "custom_text": custom_text,

        # Signatories for approvals
        "signatories": final_signatories,
    }

    rendered_content = template.render(**context)

    # Wrap with exact CSS from desktop WYSIWYG editor
    html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Документ</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Times New Roman', serif;
            font-size: 14pt;
            line-height: 1.5;
            background-color: white;
            /* Remove padding to avoid double scrollbars */
            padding: 0; 
        }}
        .document {{
            max-width: 21cm;
            /* Center the document */
            margin: 0 auto; 
            background-color: white;
            padding: 2.54cm;
            min-height: 29.7cm;
        }}
        .header {{
            text-align: right;
            margin-bottom: 24pt;
        }}
        .title {{
            text-align: center;
            font-weight: bold;
            margin-bottom: 24pt;
            text-transform: uppercase;
            font-size: 16pt;
        }}
        .content {{
            text-align: justify;
            text-indent: 1.27cm;
            margin-bottom: 0;
            line-height: 1.5;
        }}
        .auto-field {{
            font-weight: bold;
        }}
        .signature-block {{
            margin-top: 48pt;
        }}
        .signature-row {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-top: 24pt;
            position: relative;
        }}
        .signature-left,
        .signature-right {{
            flex: 1;
            min-width: 0;
        }}
        .signature-center {{
            flex: 1;
            text-align: center;
            padding: 0 10px;
        }}
        .signature-line {{
            display: inline-block;
            border-bottom: 1px solid #000;
            width: 100%;
        }}
        .approvals-section {{
            margin-top: 50pt;
        }}
        .approvals-title {{
            font-weight: bold;
            margin-bottom: 20px;
        }}
        .signatory-row {{
            display: flex !important;
            justify-content: space-between !important;
            align-items: flex-start !important;
            margin-top: 20px !important;
            padding: 0 !important;
            width: 100% !important;
        }}
        .signatory-row > div {{
            flex: 1 !important;
            min-width: 0 !important;
        }}
        .signatory-row > div:nth-child(1) {{
            text-align: left !important;
        }}
        .signatory-row > div:nth-child(2) {{
            text-align: center !important;
            padding: 0 10px !important;
        }}
        .signatory-row > div:nth-child(3) {{
            text-align: right !important;
            white-space: nowrap !important;
        }}
        .signatory-left {{
            text-align: left !important;
        }}
        .signatory-center {{
            text-align: center !important;
            padding: 0 10px !important;
        }}
        .signatory-right {{
            text-align: right !important;
            white-space: nowrap !important;
        }}
    </style>
</head>
<body>
    <div class="document">
        {rendered_content}
    </div>
</body>
</html>"""

    return html


def render_document(document: "Document", db_session: Any = None) -> str:
    """
    Render a Document model to HTML.

    Args:
        document: Document model instance
        db_session: Database session to fetch settings

    Returns:
        Rendered HTML string
    """
    staff = document.staff

    # Get employment type from staff
    employment_type = None
    if staff and hasattr(staff, 'employment_type'):
        employment_type = staff.employment_type.value if hasattr(staff.employment_type, 'value') else staff.employment_type

    return render_document_html(
        doc_type=document.doc_type,
        staff_name=staff.pib_nom if staff else "",
        staff_position=staff.position if staff else "",
        date_start=document.date_start,
        date_end=document.date_end,
        days_count=document.days_count,
        payment_period=document.payment_period,
        custom_text=document.custom_text,
        db_session=db_session,
        staff_id=document.staff_id if document else None,
        employment_type=employment_type,
    )
