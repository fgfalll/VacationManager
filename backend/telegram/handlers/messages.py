"""Message handlers for Main Menu (Reply Keyboard)."""

from datetime import date, datetime, timedelta
from collections import defaultdict
from itertools import islice

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select, desc, func
from sqlalchemy.orm import joinedload

from backend.core.database import get_db_session
from backend.models.document import Document, DocumentStatus
from backend.models.staff import Staff
from shared.enums import get_position_label
from backend.telegram.keyboards import (
    get_document_list_keyboard,
    get_back_keyboard,
    get_main_menu_keyboard,
)

router = Router()

# Ukrainian month names (nominative case)
MONTH_NAMES_UK = {
    1: "Січень",
    2: "Лютий",
    3: "Березень",
    4: "Квітень",
    5: "Травень",
    6: "Червень",
    7: "Липень",
    8: "Серпень",
    9: "Вересень",
    10: "Жовтень",
    11: "Листопад",
    12: "Грудень",
}


def get_doctype_short(doc_type: str) -> str:
    """Get short Ukrainian label for document type."""
    return {
        "vacation_paid": "Відп. опл.",
        "vacation_unpaid": "Відп. без зб.",
        "term_extension": "Прод. контр.",
        "employment_contract": "Прийом (контр)",
        "employment_competition": "Прийом (конк)",
        # Detailed
        "vacation_main": "Відп. (осн)",
        "vacation_additional": "Відп. (дод)",
        "vacation_chornobyl": "Відп. (Чор)",
        "vacation_creative": "Відп. (твор)",
        "vacation_study": "Відп. (навч)",
        "vacation_children": "Відп. (діти)",
        "vacation_maternity": "Відп. (ваг)",
        "vacation_childcare": "Відп. (догл)",
        "vacation_unpaid_study": "Б/з (навч)",
        "vacation_unpaid_mandatory": "Б/з (обов)",
        "vacation_unpaid_agreement": "Б/з (згод)",
        "vacation_unpaid_other": "Б/з (інше)",
        "term_extension_contract": "Прод. (контр)",
        "term_extension_competition": "Прод. (конк)",
        "term_extension_pdf": "Прод. (PDF)",
        "employment_pdf": "Прийом (PDF)",
    }.get(doc_type.lower() if doc_type else "", "Док")


async def get_staff_from_telegram(telegram_user_id: str):
    """Get staff member by Telegram user ID."""
    async for db in get_db_session():
        result = db.execute(
            select(Staff).where(Staff.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()



@router.message(F.text == "📄 Мої документи")
async def show_documents_my(message: Message) -> None:
    """Show user's documents with pagination (5 per page)."""
    telegram_user_id = str(message.from_user.id)
    staff = await get_staff_from_telegram(telegram_user_id)

    if not staff:
        await message.answer(
            "❌ Ваш акаунт не прив'язаний до системи.",
            reply_markup=get_back_keyboard("main_menu"),
        )
        return

    async for db in get_db_session():
        result = db.execute(
            select(Document)
            .options(joinedload(Document.staff))
            .where(Document.staff_id == staff.id)
            .order_by(desc(Document.date_start))
        )
        documents = result.scalars().all()

    if not documents:
        await message.answer(
            "📄 <b>Мої документи</b>\n\n"
            "У вас ще немає документів.",
            parse_mode="HTML",
        )
        return

    # Build docs list for keyboard (all documents, keyboard handles pagination)
    docs_list = []
    for doc in documents:
        doc_type = doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type)
        docs_list.append({
            "id": doc.id,
            "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
            "staff_name": doc.staff.pib_nom if doc.staff else "",
            "type_label": get_doctype_short(doc_type),
            "dates": f"{doc.date_start.strftime('%d.%m')}" if doc.date_start else "",
        })

    total_docs = len(documents)
    await message.answer(
        f"📄 <b>Мої документи</b> ({total_docs})\n\n"
        "Натисніть на документ для перегляду:",
        reply_markup=get_document_list_keyboard(docs_list, page=0, per_page=5, list_type="my"),
        parse_mode="HTML",
    )


def _get_status_emoji(status: DocumentStatus) -> str:
    """Get emoji for document status."""
    status_map = {
        DocumentStatus.DRAFT: "📝",
        DocumentStatus.SIGNED_BY_APPLICANT: "✍️",
        DocumentStatus.APPROVED_BY_DISPATCHER: "👀",
        DocumentStatus.SIGNED_DEP_HEAD: "📋",
        DocumentStatus.AGREED: "🤝",
        DocumentStatus.SIGNED: "✅",
        DocumentStatus.SCANNED: "📄",
        DocumentStatus.PROCESSED: "🗂️",
    }
    return status_map.get(status, "📄")


@router.message(F.text == "📋 Сьогоднішні")
async def show_documents_today(message: Message) -> None:
    """Show active/today documents."""
    # "Today's" actually means "Active/To Action" documents
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    async for db in get_db_session():
        result = db.execute(
            select(Document)
            .options(joinedload(Document.staff))
            .where(
                Document.status.in_([
                    DocumentStatus.DRAFT,
                    DocumentStatus.SIGNED_BY_APPLICANT,
                    DocumentStatus.APPROVED_BY_DISPATCHER,
                    DocumentStatus.SIGNED_DEP_HEAD,
                    DocumentStatus.AGREED,
                ])
            )
            .order_by(desc(Document.created_at))
            .limit(20)
        )
        documents = result.scalars().all()

    if not documents:
        await message.answer(
            "📋 <b>Актуальні документи</b>\n\n"
            "Немає документів, що потребують дії.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
            ]),
            parse_mode="HTML",
        )
    else:
        docs_list = [
            {
                "id": doc.id,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "staff_name": doc.staff.pib_nom[:15] if doc.staff else "",
                "type_label": get_doctype_short(doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type)),
                "dates": f"{doc.date_start.strftime('%d.%m')}-{doc.date_end.strftime('%d.%m')}" if doc.date_start and doc.date_end else "",
            }
            for doc in documents
        ]
        await message.answer(
            f"📋 <b>Актуальні документи</b> ({len(docs_list)})\n\n"
            "Натисніть для перегляду:",
            reply_markup=get_document_list_keyboard(docs_list, list_type="today"),
            parse_mode="HTML",
        )


@router.message(F.text == "⚠️ Проблемні")
async def show_documents_stale(message: Message) -> None:
    """Show stale documents."""
    stale_threshold = datetime.now() - timedelta(days=1)

    async for db in get_db_session():
        result = db.execute(
            select(Document)
            .options(joinedload(Document.staff))
            .where(
                Document.status_changed_at < stale_threshold,
                Document.status.in_([
                    DocumentStatus.DRAFT,
                    DocumentStatus.SIGNED_BY_APPLICANT,
                    DocumentStatus.APPROVED_BY_DISPATCHER,
                    DocumentStatus.SIGNED_DEP_HEAD,
                    DocumentStatus.AGREED,
                ]),
            )
            .order_by(desc(Document.status_changed_at))
            .limit(20)
        )
        documents = result.scalars().all()

    if not documents:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await message.answer(
            "⚠️ <b>Проблемні документи</b>\n\n"
            "Проблемних документів не знайдено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
            ]),
            parse_mode="HTML",
        )
    else:
        docs_list = [
            {
                "id": doc.id,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "staff_name": doc.staff.pib_nom[:15] if doc.staff else "",
                "type_label": get_doctype_short(doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type)),
                "dates": f"{doc.date_start.strftime('%d.%m')}-{doc.date_end.strftime('%d.%m')}" if doc.date_start and doc.date_end else "",
            }
            for doc in documents
        ]
        await message.answer(
            f"⚠️ <b>Проблемні документи</b> ({len(docs_list)})\n\n"
            "Натисніть для перегляду:",
            reply_markup=get_document_list_keyboard(docs_list, list_type="stale"),
            parse_mode="HTML",
        )


@router.message(F.text == "👤 Профіль")
async def show_profile(message: Message) -> None:
    """Show user profile."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    telegram_user_id = str(message.from_user.id)
    staff = await get_staff_from_telegram(telegram_user_id)

    if staff:
        # Format rate safely
        rate_str = str(staff.rate) if staff.rate else "N/A"

        # Warnings
        warnings = []
        if staff.is_term_expired:
            warnings.append("❌ <b>КОНТРАКТ ЗАКІНЧИВСЯ!</b>")
        elif staff.is_term_expiring_soon:
            warnings.append(f"⚠️ <b>Увага!</b> Контракт закінчується через {staff.days_until_term_end} днів.")

        w_text = "\n\n".join(warnings)
        if w_text:
            w_text = "\n\n" + w_text

        profile_text = (
            f"👤 <b>Ваш профіль</b>\n\n"
            f"<b>ПІБ:</b> {staff.pib_nom}\n"
            f"<b>Посада:</b> {get_position_label(staff.position)}\n"
            f"<b>Ставка:</b> {rate_str}\n\n"
            f"<b>Днів відпустки:</b> {staff.vacation_balance}\n"
            f"<b>Контракт:</b> {staff.term_start.strftime('%d.%m.%Y')} — {staff.term_end.strftime('%d.%m.%Y')}"
            f"{w_text}\n\n"
            f"<b>Email:</b> {staff.email or 'Не вказано'}\n"
            f"<b>Телефон:</b> {staff.phone or 'Не вказано'}\n"
            f"<b>Telegram:</b> @{staff.telegram_username or message.from_user.username or 'N/A'}\n"
        )
    else:
        profile_text = "👤 Профіль не знайдено.\n\nВаш акаунт не прив'язаний до системи."

    await message.answer(
        profile_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
        ]),
        parse_mode="HTML",
    )


@router.message(F.text == "❓ Допомога")
async def show_help(message: Message) -> None:
    """Show help information."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    help_text = (
        "<b>❓ Довідка</b>\n\n"
        "<b>Доступні функції:</b>\n"
        "• 📄 <b>Мої документи</b> - документи, де ви заявник\n"
        "• 📋 <b>Сьогоднішні</b> - документи на підписі/в роботі\n"
        "• ⚠️ <b>Проблемні</b> - документи, що потребують уваги (застарілі)\n"
        "• 👤 <b>Профіль</b> - ваша інформація\n\n"
        "<b>Дії з документами:</b>\n"
        "• Натисніть на документ для перегляду\n"
        "• Статус та доступні дії відображаються під документом\n"
        "• Ви можете підписати або погодити документ прямо тут\n"
    )
    await message.answer(
        help_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
        ]),
        parse_mode="HTML",
    )


def register_message_handlers(dp) -> None:
    """Register message handlers."""
    dp.include_router(router)
