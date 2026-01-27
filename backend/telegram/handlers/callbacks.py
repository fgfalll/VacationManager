"""Callback query handlers for Telegram bot - Full implementation without Mini App."""

from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import date, datetime, timedelta

from backend.telegram.keyboards import (
    get_main_menu_keyboard,
    get_document_list_keyboard,
    get_document_detail_keyboard,
    get_stale_document_keyboard,
    get_confirm_keyboard,
    get_back_keyboard,
)
from backend.telegram.states import StaleExplanationStates
from shared.enums import get_position_label

router = Router()


# ==================== Helper Functions ====================

def get_status_emoji(status: str) -> str:
    """Get emoji for document status."""
    return {
        "draft": "📝",
        "signed_by_applicant": "✍️",
        "approved_by_dispatcher": "👍",
        "signed_dep_head": "👨‍💼",
        "agreed": "🤝",
        "signed_rector": "🎓",
        "scanned": "📸",
        "processed": "✅",
    }.get(status.lower() if status else "", "📄")


def get_status_label(status: str) -> str:
    """Get Ukrainian label for document status."""
    return {
        "draft": "Чернетка",
        "signed_by_applicant": "Підписано заявником",
        "approved_by_dispatcher": "Погоджено диспетчером",
        "signed_dep_head": "Підписано зав. кафедри",
        "agreed": "Узгоджено",
        "signed_rector": "Підписано ректором",
        "scanned": "Скан завантажено",
        "processed": "Оброблено",
    }.get(status.lower() if status else "", status)


def get_doctype_label(doc_type: str) -> str:
    """Get Ukrainian label for document type."""
    return {
        "vacation_paid": "Оплачувана відпустка",
        "vacation_unpaid": "Відпустка без збереження",
        "term_extension": "Продовження контракту",
        "employment_contract": "Прийом на роботу (контракт)",
        "employment_competition": "Прийом на роботу (конкурс)",
    }.get(doc_type.lower() if doc_type else "", doc_type)


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


def get_next_status(current_status: str) -> str:
    """Get next status in workflow."""
    flow = {
        "draft": "signed_by_applicant",
        "signed_by_applicant": "approved_by_dispatcher",
        "approved_by_dispatcher": "signed_dep_head",
        "signed_dep_head": "agreed",
        "agreed": "signed_rector",
        "signed_rector": "scanned",
        "scanned": "processed",
    }
    return flow.get(current_status.lower() if current_status else "", current_status)


async def get_staff_from_telegram(telegram_user_id: str):
    """Get staff member by Telegram user ID."""
    from backend.core.database import get_db_session
    from backend.models.staff import Staff
    from sqlalchemy import select

    async for db in get_db_session():
        result = db.execute(
            select(Staff).where(Staff.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()


# ==================== Main Menu ====================

async def callback_main_menu(callback: CallbackQuery) -> None:
    """Show main menu with status overview."""
    from backend.core.database import get_db_session
    from backend.models.document import Document, DocumentStatus
    from sqlalchemy import select, func
    from datetime import datetime, timedelta

    stale_threshold = datetime.now() - timedelta(days=1)
    
    active_statuses = [
        DocumentStatus.DRAFT,
        DocumentStatus.SIGNED_BY_APPLICANT,
        DocumentStatus.APPROVED_BY_DISPATCHER,
        DocumentStatus.SIGNED_DEP_HEAD,
        DocumentStatus.AGREED,
    ]

    active_count = 0
    stale_count = 0

    async for db in get_db_session():
        # Active count
        active_count = db.execute(
            select(func.count(Document.id)).where(Document.status.in_(active_statuses))
        ).scalar() or 0
        
        # Stale count
        stale_count = db.execute(
            select(func.count(Document.id)).where(
                Document.status.in_(active_statuses),
                Document.status_changed_at < stale_threshold
            )
        ).scalar() or 0

    # Delete current inline message (list or old menu)
    try:
        await callback.message.delete()
    except:
        pass

    # Send new message with Reply Keyboard
    await callback.message.answer(
        f"📋 <b>Головне меню</b>\n\n"
        f"📊 <b>Статус системи:</b>\n"
        f"• На підписі: {active_count}\n"
        f"• Проблемні: {stale_count}\n\n"
        "Оберіть дію:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


async def callback_help_show(callback: CallbackQuery) -> None:
    """Show help information."""
    help_text = (
        "<b>❓ Довідка</b>\n\n"
        "<b>Доступні функції:</b>\n"
        "• 📄 <b>Мої документи</b> - документи, де ви заявник\n"
        "• 📋 <b>Сьогоднішні</b> - документи на підписі/в роботі\n"
        "• ⚠️ <b>Проблемні</b> - документи, що потребують уваги (застарілі)\n"
        "• 👤 <b>Профіль</b> - ваша інформація\n\n"
        "<b>Дії з документами:</b>\n"
        "• Натисніть на документ для перегляду\n"
        "• Підписуйте/погоджуйте прямо в боті\n\n"
        "<i>📸 Сканування доступне тільки в Mini App</i>"
    )
    await callback.message.edit_text(
        help_text,
        reply_markup=get_back_keyboard("main_menu"),
        parse_mode="HTML",
    )
    await callback.answer()


# ==================== Document Lists ====================

async def callback_documents_my(callback: CallbackQuery) -> None:
    """Show user's own documents."""
    from backend.core.database import get_db_session
    from backend.models.document import Document
    from sqlalchemy import select, desc
    from sqlalchemy.orm import joinedload

    telegram_user_id = str(callback.from_user.id)
    staff = await get_staff_from_telegram(telegram_user_id)

    if not staff:
        await callback.message.edit_text(
            "❌ Ваш акаунт не прив'язаний до системи.",
            reply_markup=get_back_keyboard("main_menu"),
        )
        await callback.answer()
        return

    async for db in get_db_session():
        result = db.execute(
            select(Document)
            .options(joinedload(Document.staff))
            .where(Document.staff_id == staff.id)
            .order_by(desc(Document.created_at))
            .limit(20)
        )
        documents = result.scalars().all()

    if not documents:
        await callback.message.edit_text(
            "📄 <b>Мої документи</b>\n\n"
            "У вас ще немає документів.",
            reply_markup=get_back_keyboard("main_menu"),
            parse_mode="HTML",
        )
    else:
        docs_list = [
            {
                "id": doc.id,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "staff_name": doc.staff.pib_nom if doc.staff else "",
                "type_label": get_doctype_short(doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type)),
                "dates": f"{doc.date_start.strftime('%d.%m')}-{doc.date_end.strftime('%d.%m')}" if doc.date_start and doc.date_end else "",
            }
            for doc in documents
        ]
        await callback.message.edit_text(
            f"📄 <b>Мої документи</b> ({len(docs_list)})\n\n"
            "Натисніть для перегляду:",
            reply_markup=get_document_list_keyboard(docs_list, 0, 5, "my"),
            parse_mode="HTML",
        )

    await callback.answer()


async def callback_documents_today(callback: CallbackQuery) -> None:
    """Show today's documents."""
    from backend.core.database import get_db_session
    from backend.core.database import get_db_session
    from backend.models.document import Document, DocumentStatus
    from sqlalchemy import select, desc
    from sqlalchemy.orm import joinedload

    today = date.today()
    
    # "Today's" actually means "Active/To Action" documents
    # User feedback: "all documents that avaliable to sign"
    
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
        await callback.message.edit_text(
            "📋 <b>Сьогоднішні документи</b>\n\n"
            "Документів ще не створено сьогодні.",
            reply_markup=get_back_keyboard("main_menu"),
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
        await callback.message.edit_text(
            f"📋 <b>Сьогоднішні документи</b> ({len(docs_list)})\n\n"
            "Натисніть для перегляду:",
            reply_markup=get_document_list_keyboard(docs_list, 0, 5, "today"),
            parse_mode="HTML",
        )

    await callback.answer()


async def callback_documents_stale(callback: CallbackQuery) -> None:
    """Show stale documents."""
    from backend.core.database import get_db_session
    from backend.models.document import Document, DocumentStatus
    from sqlalchemy import select, desc
    from sqlalchemy.orm import joinedload

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
        await callback.message.edit_text(
            "⚠️ <b>Застарілі документи</b>\n\n"
            "Застарілих документів немає. Гарна робота! 👍",
            reply_markup=get_back_keyboard("main_menu"),
            parse_mode="HTML",
        )
    else:
        docs_list = [
            {
                "id": doc.id,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "staff_name": doc.staff.pib_nom[:15] if doc.staff else "",
            }
            for doc in documents
        ]
        await callback.message.edit_text(
            f"⚠️ <b>Застарілі документи</b> ({len(docs_list)})\n\n"
            "Документи, що потребують уваги:",
            reply_markup=get_document_list_keyboard(docs_list, 0, 5, "stale"),
            parse_mode="HTML",
        )

    await callback.answer()


async def callback_docs_page(callback: CallbackQuery) -> None:
    """Handle document list pagination."""
    from backend.core.database import get_db_session
    from backend.models.staff import Staff
    from backend.models.document import Document, DocumentStatus
    from backend.telegram.keyboards import get_document_list_keyboard
    from sqlalchemy import select, desc
    from sqlalchemy.orm import joinedload

    # Parse callback: docs_{list_type}_page_{page}
    parts = callback.data.split("_")
    list_type = parts[1]  # today, stale, my
    page = int(parts[3])
    per_page = 5

    telegram_user_id = str(callback.from_user.id)

    if list_type == "my":
        # Fetch user's documents
        async for db in get_db_session():
            result = db.execute(
                select(Staff).where(Staff.telegram_user_id == telegram_user_id)
            )
            staff = result.scalar_one_or_none()

            if not staff:
                await callback.answer("❌ Користувача не знайдено", show_alert=True)
                return

            result = db.execute(
                select(Document)
                .options(joinedload(Document.staff))
                .where(Document.staff_id == staff.id)
                .order_by(desc(Document.date_start))
            )
            documents = result.scalars().all()

        # Build docs list
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
        total_pages = (total_docs + per_page - 1) // per_page

        # Ensure page is valid
        if page >= total_pages:
            page = max(0, total_pages - 1)

        await callback.message.edit_text(
            f"📄 <b>Мої документи</b> ({total_docs}) - Сторінка {page + 1}/{total_pages}\n\n"
            "Натисніть на документ для перегляду:",
            reply_markup=get_document_list_keyboard(docs_list, page=page, per_page=per_page, list_type="my"),
            parse_mode="HTML",
        )
        await callback.answer()

    elif list_type == "today":
        # For "today" list, refresh the list
        callback.data = "documents_today"
        # Will be handled by the documents_today handler
        await callback.answer()
    elif list_type == "stale":
        # For "stale" list, refresh the list
        callback.data = "documents_stale"
        await callback.answer()


# ==================== Document Detail & Actions ====================

async def callback_doc_view(callback: CallbackQuery) -> None:
    """Show document detail view."""
    from backend.core.database import get_db_session
    from backend.models.document import Document
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    doc_id = int(callback.data.split("_")[-1])

    async for db in get_db_session():
        result = db.execute(
            select(Document)
            .options(joinedload(Document.staff))
            .where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()

    if not doc:
        await callback.answer("Документ не знайдено", show_alert=True)
        return

    status = doc.status.value if hasattr(doc.status, 'value') else str(doc.status)
    status_lower = status.lower()

    # Build detail text
    detail_text = (
        f"{get_status_emoji(status_lower)} <b>Документ #{doc.id}</b>\n\n"
        f"<b>Тип:</b> {get_doctype_label(doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type))}\n"
        f"<b>Статус:</b> {get_status_label(status_lower)}\n"
        f"<b>Співробітник:</b> {doc.staff.pib_nom if doc.staff else 'N/A'}\n"
    )

    if doc.date_start and doc.date_end:
        detail_text += f"<b>Період:</b> {doc.date_start.strftime('%d.%m.%Y')} - {doc.date_end.strftime('%d.%m.%Y')}\n"
        detail_text += f"<b>Днів:</b> {doc.days_count}\n"

    detail_text += f"<b>Створено:</b> {doc.created_at.strftime('%d.%m.%Y %H:%M')}\n"

    await callback.message.edit_text(
        detail_text,
        reply_markup=get_document_detail_keyboard(doc.id, status_lower),
        parse_mode="HTML",
    )
    await callback.answer()


async def callback_doc_sign(callback: CallbackQuery) -> None:
    """Show sign confirmation."""
    doc_id = int(callback.data.split("_")[-1])
    
    await callback.message.edit_text(
        f"✅ <b>Підписання документа #{doc_id}</b>\n\n"
        "Ви впевнені, що хочете підписати цей документ?",
        reply_markup=get_confirm_keyboard("sign", doc_id),
        parse_mode="HTML",
    )
    await callback.answer()


async def callback_doc_forward(callback: CallbackQuery) -> None:
    """Show forward confirmation."""
    doc_id = int(callback.data.split("_")[-1])
    
    await callback.message.edit_text(
        f"👉 <b>Погодження документа #{doc_id}</b>\n\n"
        "Ви впевнені, що хочете погодити/переслати цей документ далі?",
        reply_markup=get_confirm_keyboard("forward", doc_id),
        parse_mode="HTML",
    )
    await callback.answer()


async def callback_doc_scan_info(callback: CallbackQuery) -> None:
    """Show info that scan is only available in Mini App."""
    await callback.answer(
        "📸 Завантаження скану доступне тільки в Mini App.\n"
        "Відкрийте Mini App для сканування.",
        show_alert=True,
    )


async def callback_confirm_action(callback: CallbackQuery) -> None:
    """Handle confirmed action (sign/forward)."""
    from backend.core.database import get_db_session
    from backend.models.document import Document, DocumentStatus
    from backend.services.document_service import DocumentService
    from backend.services.grammar_service import GrammarService
    from sqlalchemy import select

    # Parse: confirm_{action}_{doc_id}
    parts = callback.data.split("_")
    action = parts[1]
    doc_id = int(parts[2])

    async for db in get_db_session():
        result = db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()

        if not doc:
            await callback.answer("Документ не знайдено", show_alert=True)
            return

        try:
            service = DocumentService(db, GrammarService())
            current_status = doc.status.value if hasattr(doc.status, 'value') else str(doc.status)
            
            # Perform action based on current status
            if action in ("sign", "forward"):
                if current_status == "draft":
                    service.set_applicant_signed(doc)
                elif current_status == "signed_by_applicant":
                    service.set_approval(doc)
                elif current_status == "approved_by_dispatcher":
                    service.set_department_head_signed(doc)
                elif current_status == "signed_dep_head":
                    service.set_approval_order(doc)
                elif current_status == "agreed":
                    service.set_rector_signed(doc)

            db.commit()
            db.refresh(doc)

            new_status = doc.status.value if hasattr(doc.status, 'value') else str(doc.status)
            
            await callback.message.edit_text(
                f"✅ <b>Успішно!</b>\n\n"
                f"Документ #{doc_id} оновлено.\n"
                f"Новий статус: {get_status_label(new_status.lower())}",
                reply_markup=get_back_keyboard("documents_today"),
                parse_mode="HTML",
            )
            await callback.answer("Готово!")

        except Exception as e:
            await callback.answer(f"Помилка: {str(e)[:50]}", show_alert=True)


# ==================== Admin: View Employee Documents ====================

async def callback_employee_documents(callback: CallbackQuery) -> None:
    """Show documents for selected employee (admin search result)."""
    from backend.core.database import get_db_session
    from backend.models.document import Document
    from backend.models.staff import Staff
    from sqlalchemy import select, desc
    from sqlalchemy.orm import joinedload
    from shared.enums import get_position_label

    staff_id = int(callback.data.split("_")[-1])

    async for db in get_db_session():
        result = db.execute(
            select(Staff)
            .options(joinedload(Staff.documents))
            .where(Staff.id == staff_id)
        )
        staff = result.scalar_one_or_none()

    if not staff:
        await callback.answer("Співробітника не знайдено", show_alert=True)
        return

    # Build documents list
    docs_list = []
    for doc in staff.documents:
        doc_type = doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type)
        docs_list.append({
            "id": doc.id,
            "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
            "staff_name": staff.pib_nom[:15] if staff else "",
            "type_label": get_doctype_short(doc_type),
            "dates": f"{doc.date_start.strftime('%d.%m')}" if doc.date_start else "",
        })

    # Sort by date descending
    docs_list.sort(key=lambda x: x["dates"], reverse=True)

    pos_label = get_position_label(staff.position)

    await callback.message.edit_text(
        f"📄 <b>Документи співробітника</b>\n\n"
        f"<b>ПІБ:</b> {staff.pib_nom}\n"
        f"<b>Посада:</b> {pos_label}\n"
        f"<b>Кількість документів:</b> {len(docs_list)}\n\n"
        f"Натисніть для перегляду:",
        reply_markup=get_document_list_keyboard(docs_list, page=0, per_page=5, list_type="my"),
        parse_mode="HTML",
    )
    await callback.answer()


# ==================== Stale Document Actions ====================

async def callback_stale_view(callback: CallbackQuery) -> None:
    """Show stale document with actions."""
    from backend.core.database import get_db_session
    from backend.models.document import Document
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    doc_id = int(callback.data.split("_")[-1])

    async for db in get_db_session():
        result = db.execute(
            select(Document)
            .options(joinedload(Document.staff))
            .where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()

    if not doc:
        await callback.answer("Документ не знайдено", show_alert=True)
        return

    days_stale = 0
    if doc.status_changed_at:
        days_stale = (datetime.now() - doc.status_changed_at).days

    detail_text = (
        f"⚠️ <b>Застарілий документ #{doc.id}</b>\n\n"
        f"<b>Статус:</b> {get_status_label(doc.status.value.lower() if hasattr(doc.status, 'value') else str(doc.status).lower())}\n"
        f"<b>Не змінювався:</b> {days_stale} днів\n"
        f"<b>Співробітник:</b> {doc.staff.pib_nom if doc.staff else 'N/A'}\n"
    )

    if doc.stale_explanation:
        detail_text += f"\n💬 <b>Пояснення:</b> {doc.stale_explanation}\n"

    await callback.message.edit_text(
        detail_text,
        reply_markup=get_stale_document_keyboard(doc.id),
        parse_mode="HTML",
    )
    await callback.answer()


async def callback_stale_explain(callback: CallbackQuery, state: FSMContext) -> None:
    """Start explanation input flow."""
    doc_id = int(callback.data.split("_")[-1])
    
    await state.update_data(document_id=doc_id)
    await state.set_state(StaleExplanationStates.waiting_for_explanation)
    
    await callback.message.edit_text(
        f"💬 <b>Пояснення для документа #{doc_id}</b>\n\n"
        "Введіть причину затримки:",
        parse_mode="HTML",
    )
    await callback.answer()


async def callback_stale_resolve(callback: CallbackQuery) -> None:
    """Mark stale document as resolved."""
    from backend.core.database import get_db_session
    from backend.models.document import Document
    from sqlalchemy import select

    doc_id = int(callback.data.split("_")[-1])

    async for db in get_db_session():
        result = db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()

        if doc:
            doc.stale_notification_count = 0
            doc.stale_explanation = None
            doc.status_changed_at = datetime.now()
            db.commit()

            await callback.message.edit_text(
                f"✅ Документ #{doc_id} позначено як актуальний.",
                reply_markup=get_back_keyboard("documents_stale"),
            )
            await callback.answer("Готово!")
        else:
            await callback.answer("Документ не знайдено", show_alert=True)


# ==================== Settings ====================

async def callback_settings_profile(callback: CallbackQuery) -> None:
    """Show user profile."""
    telegram_user_id = str(callback.from_user.id)
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
            f"<b>Telegram:</b> @{staff.telegram_username or callback.from_user.username or 'N/A'}\n"
        )
    else:
        profile_text = "👤 Профіль не знайдено.\n\nВаш акаунт не прив'язаний до системи."

    await callback.message.edit_text(
        profile_text,
        reply_markup=get_back_keyboard("main_menu"),
        parse_mode="HTML",
    )
    await callback.answer()


async def callback_noop(callback: CallbackQuery) -> None:
    """No-op callback for pagination info buttons."""
    await callback.answer()


# ==================== Registration ====================

async def callback_link_approve(callback: CallbackQuery, state: FSMContext) -> None:
    """Start link approval flow."""
    from backend.telegram.states import LinkRequestStates
    
    req_id = int(callback.data.split("_")[-1])
    
    await state.update_data(request_id=req_id)
    await state.set_state(LinkRequestStates.waiting_for_staff_id)
    
    await callback.message.answer(
        f"✍️ <b>Введіть ID співробітника</b> для прив'язки до запиту #{req_id}.\n\n"
        "ID можна знайти у списку співробітників або у базі даних.",
        parse_mode="HTML"
    )
    await callback.answer()


async def callback_link_reject(callback: CallbackQuery) -> None:
    """Reject link request."""
    from backend.core.database import get_db_session
    from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
    from sqlalchemy import select
    from backend.api.routes.telegram import _send_rejection_notification
    from datetime import datetime
    
    req_id = int(callback.data.split("_")[-1])
    
    async for db in get_db_session():
        result = db.execute(select(TelegramLinkRequest).where(TelegramLinkRequest.id == req_id))
        req = result.scalar_one_or_none()
        
        if not req or req.status != LinkRequestStatus.PENDING:
            await callback.answer("Запит не знайдено або оброблено", show_alert=True)
            return
            
        req.status = LinkRequestStatus.REJECTED
        req.approved_by = f"Telegram Admin {callback.from_user.id}"
        req.processed_at = datetime.now()
        
        db.commit()
        
        await _send_rejection_notification(req.telegram_user_id, "Відхилено адміністратором через бот")
        
        await callback.message.edit_text(
            f"❌ Запит #{req_id} відхилено.\n"
            f"Користувач: {req.first_name}"
        )


def register_callback_handlers(dp) -> None:
    """Register all callback query handlers."""
    # Main menu
    dp.callback_query.register(callback_main_menu, lambda c: c.data == "main_menu")
    dp.callback_query.register(callback_help_show, lambda c: c.data == "help_show")

    # Document lists
    dp.callback_query.register(callback_documents_my, lambda c: c.data == "documents_my")
    dp.callback_query.register(callback_documents_today, lambda c: c.data == "documents_today")
    dp.callback_query.register(callback_documents_stale, lambda c: c.data == "documents_stale")
    dp.callback_query.register(callback_docs_page, lambda c: c.data and c.data.startswith("docs_") and "_page_" in c.data)

    # Document detail & actions
    dp.callback_query.register(callback_doc_view, lambda c: c.data and c.data.startswith("doc_view_"))
    dp.callback_query.register(callback_doc_sign, lambda c: c.data and c.data.startswith("doc_sign_") and not c.data.startswith("doc_sign_info"))
    dp.callback_query.register(callback_doc_forward, lambda c: c.data and c.data.startswith("doc_forward_"))
    dp.callback_query.register(callback_doc_scan_info, lambda c: c.data and c.data.startswith("doc_scan_info_"))
    dp.callback_query.register(callback_confirm_action, lambda c: c.data and c.data.startswith("confirm_"))

    # Stale documents
    dp.callback_query.register(callback_stale_view, lambda c: c.data and c.data.startswith("stale_view_"))
    dp.callback_query.register(callback_stale_explain, lambda c: c.data and c.data.startswith("stale_explain_"))
    dp.callback_query.register(callback_stale_resolve, lambda c: c.data and c.data.startswith("stale_resolve_"))

    # Admin: Employee documents
    dp.callback_query.register(callback_employee_documents, lambda c: c.data and c.data.startswith("emp_docs_"))

    # Link requests
    dp.callback_query.register(callback_link_approve, lambda c: c.data and c.data.startswith("link_approve_"))
    dp.callback_query.register(callback_link_reject, lambda c: c.data and c.data.startswith("link_reject_"))

    # Profile
    dp.callback_query.register(callback_settings_profile, lambda c: c.data == "settings_profile")

    # Utility
    dp.callback_query.register(callback_noop, lambda c: c.data == "noop")
