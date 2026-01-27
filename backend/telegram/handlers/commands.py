"""Command handlers for Telegram bot."""

import json
from collections import defaultdict
from itertools import islice

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, or_

from backend.models.document import DocumentStatus
from backend.models.staff import Staff
from backend.telegram.keyboards import get_main_menu_keyboard, get_contact_keyboard, get_back_keyboard, get_document_list_keyboard
from backend.telegram.states import StaleExplanationStates, EmployeeSearchStates
from shared.enums import get_position_label

# Ukrainian month names
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

router = Router()


async def cmd_start(message: Message) -> None:
    """
    Обробник команди /start.

    Перевіряє, чи прив'язаний Telegram акаунт до співробітника,
    і показує відповідне повідомлення.
    """
    from backend.core.database import get_db_session
    from backend.models.staff import Staff
    from sqlalchemy import select

    telegram_user_id = str(message.from_user.id)

    async for db in get_db_session():
        result = db.execute(
            select(Staff).where(Staff.telegram_user_id == telegram_user_id)
        )
        staff = result.scalar_one_or_none()

        if staff:
            # Stats calculation
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
            
            active_count = db.execute(
                select(func.count(Document.id)).where(Document.status.in_(active_statuses))
            ).scalar() or 0
            
            stale_count = db.execute(
                select(func.count(Document.id)).where(
                    Document.status.in_(active_statuses),
                    Document.status_changed_at < stale_threshold
                )
            ).scalar() or 0

            await message.answer(
                f"Вітаю, <b>{staff.pib_nom}</b>! 👋\n\n"
                f"📋 <b>Посада:</b> {get_position_label(staff.position)}\n\n"
                f"📊 <b>Статус системи:</b>\n"
                f"• На підписі: {active_count}\n"
                f"• Проблемні: {stale_count}\n\n"
                f"Оберіть дію з меню нижче:",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
        else:
            await message.answer(
                "Вітаю! 👋\n\n"
                "Ваш Telegram акаунт ще не прив'язаний до системи.\n"
                "Зверніться до адміністратора для прив'язки.",
                reply_markup=get_contact_keyboard(),
            )


async def cmd_help(message: Message) -> None:
    """Обробник команди /help."""
    help_text = (
        "<b>❓ Довідка VacationManager Bot</b>\n\n"
        "<b>Команди:</b>\n"
        "/start - Почати роботу\n"
        "/menu - Головне меню\n"
        "/help - Ця довідка\n"
        "/docs - Мої документи\n"
        "/stale - Застарілі документи\n\n"
        "<b>Функції:</b>\n"
        "• 📄 Перегляд документів\n"
        "• ✅ Підписання/погодження\n"
        "• ⚠️ Управління застарілими\n"
        "• 👤 Профіль\n\n"
        "<i>📸 Сканування - тільки в Mini App</i>"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_back_keyboard("main_menu"))


async def cmd_menu(message: Message) -> None:
    """Обробник команди /menu - показує головне меню."""
    await message.answer(
        "📋 <b>Головне меню</b>\n\nОберіть дію:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )


async def cmd_docs(message: Message) -> None:
    """Обробник команди /docs - показує документи користувача згруповані за місяцем."""
    from backend.core.database import get_db_session
    from backend.models.staff import Staff
    from backend.models.document import Document, DocumentStatus
    from sqlalchemy import select, desc
    from sqlalchemy.orm import joinedload

    telegram_user_id = str(message.from_user.id)

    async for db in get_db_session():
        result = db.execute(
            select(Staff).where(Staff.telegram_user_id == telegram_user_id)
        )
        staff = result.scalar_one_or_none()

        if not staff:
            await message.answer(
                "❌ Ваш акаунт не прив'язаний до системи.",
                reply_markup=get_back_keyboard("main_menu"),
            )
            return

        result = db.execute(
            select(Document)
            .options(joinedload(Document.staff))
            .where(Document.staff_id == staff.id)
            .order_by(desc(Document.date_start))
        )
        documents = result.scalars().all()

    if not documents:
        await message.answer(
            "📄 <b>Мої документи</b>\n\nУ вас ще немає документів.",
            reply_markup=get_back_keyboard("main_menu"),
            parse_mode="HTML",
        )
        return

    # Group documents by year and month
    grouped = defaultdict(list)
    for doc in documents:
        group_date = doc.date_start if doc.date_start else doc.created_at
        key = (group_date.year, group_date.month)
        grouped[key].append(doc)

    # Sort groups: most recent first
    sorted_groups = sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1]), reverse=True)

    # Build message text with grouped documents
    total_docs = len(documents)
    msg_text = f"📄 <b>Мої документи</b> ({total_docs})\n\n"

    # Show documents grouped by month (limit to recent months)
    max_months = 6
    docs_list = []

    for (year, month), docs in islice(sorted_groups, max_months):
        month_name = MONTH_NAMES_UK.get(month, str(month))
        msg_text += f"📅 <b>{month_name} {year}</b>\n"

        for doc in docs:
            doc_type = doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type)
            type_label = _get_doctype_short(doc_type)
            dates = f"{doc.date_start.strftime('%d.%m')}" if doc.date_start else ""
            status_emoji = _get_status_emoji(doc.status)
            msg_text += f"  {status_emoji} {type_label} ({dates})\n"

            docs_list.append({
                "id": doc.id,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "staff_name": doc.staff.pib_nom if doc.staff else "",
                "type_label": type_label,
                "dates": dates,
            })

        msg_text += "\n"

    # If there are more months, add a note
    if len(sorted_groups) > max_months:
        remaining = len(sorted_groups) - max_months
        msg_text += f"... і ще {remaining} міс. раніше\n\n"

    msg_text += "Натисніть кнопку нижче для перегляду деталей:"

    await message.answer(
        msg_text,
        reply_markup=get_document_list_keyboard(docs_list[:10], list_type="my"),
        parse_mode="HTML",
    )


def _get_doctype_short(doc_type: str) -> str:
    """Get short Ukrainian label for document type."""
    return {
        "vacation_paid": "Відп. опл.",
        "vacation_unpaid": "Відп. без зб.",
        "vacation_main": "Осн. відп.",
        "vacation_additional": "Дод. відп.",
        "term_extension": "Продовж.",
        "employment_contract": "Прийом",
    }.get(doc_type, doc_type[:15])


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


async def cmd_stale(message: Message) -> None:
    """Обробник команди /stale - показує застарілі документи."""
    from backend.core.database import get_db_session
    from backend.models.document import Document, DocumentStatus
    from backend.telegram.keyboards import get_document_list_keyboard
    from sqlalchemy import select, desc
    from datetime import datetime, timedelta

    stale_threshold = datetime.now() - timedelta(days=1)

    async for db in get_db_session():
        result = db.execute(
            select(Document)
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
        await message.answer(
            "⚠️ <b>Застарілі документи</b>\n\nЗастарілих документів немає! 👍",
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
        await message.answer(
            f"⚠️ <b>Застарілі документи</b> ({len(docs_list)})\n\nДокументи, що потребують уваги:",
            reply_markup=get_document_list_keyboard(docs_list, 0, 5, "stale"),
            parse_mode="HTML",
        )


async def handle_stale_explanation(message: Message, state: FSMContext) -> None:
    """Handle stale explanation text input."""
    from backend.core.database import get_db_session
    from backend.models.document import Document
    from sqlalchemy import select

    data = await state.get_data()
    doc_id = data.get("document_id")
    
    if not doc_id:
        await message.answer("❌ Помилка: не вдалося знайти документ.")
        await state.clear()
        return

    explanation = message.text.strip()
    
    async for db in get_db_session():
        result = db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()

        if doc:
            doc.stale_explanation = explanation
            db.commit()

            await message.answer(
                f"✅ Пояснення збережено для документа #{doc_id}.",
                reply_markup=get_back_keyboard("documents_stale"),
            )
        else:
            await message.answer("❌ Документ не знайдено.")

    await state.clear()


async def handle_cancel(message: Message, state: FSMContext) -> None:
    """Handle cancel command in any state."""
    await state.clear()
    await message.answer(
        "❌ Скасовано.",
        reply_markup=get_main_menu_keyboard(),
    )


async def handle_contact(message: Message) -> None:
    """
    Handle contact sharing.
    
    Creates a link request if user is not already linked.
    """
    from backend.core.database import get_db_session
    from backend.models.staff import Staff
    from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
    from sqlalchemy import select

    if not message.contact:
        return

    telegram_user_id = str(message.from_user.id)
    
    async for db in get_db_session():
        # Check if already linked to staff
        result = db.execute(
            select(Staff).where(Staff.telegram_user_id == telegram_user_id)
        )
        staff = result.scalar_one_or_none()

        if staff:
            # Already linked - show welcome
            await message.answer(
                f"✅ Ваш акаунт вже прив'язаний!\n\n"
                f"👤 <b>{staff.pib_nom}</b>\n"
                f"📋 {get_position_label(staff.position)}",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
            return

        # Check for existing pending request
        result = db.execute(
            select(TelegramLinkRequest).where(
                TelegramLinkRequest.telegram_user_id == telegram_user_id,
                TelegramLinkRequest.status == LinkRequestStatus.PENDING
            )
        )
        existing_request = result.scalar_one_or_none()

        if existing_request:
            await message.answer(
                "⏳ <b>Ваш запит вже на розгляді</b>\n\n"
                "Очікуйте підтвердження від адміністратора.\n"
                "Ми повідомимо вас, коли запит буде розглянуто.",
                parse_mode="HTML",
            )
            return

        # Create new link request
        link_request = TelegramLinkRequest(
            telegram_user_id=telegram_user_id,
            telegram_username=message.from_user.username,
            phone_number=message.contact.phone_number,
            first_name=message.from_user.first_name or message.contact.first_name or "Unknown",
            last_name=message.from_user.last_name or message.contact.last_name,
            status=LinkRequestStatus.PENDING,
        )
        db.add(link_request)
        db.commit()

        await message.answer(
            "✅ <b>Запит надіслано!</b>\n\n"
            "Дякуємо! Ваш запит на прив'язку Telegram акаунту надіслано.\n\n"
            "⏳ <b>Що далі?</b>\n"
            "• Адміністратор розгляне ваш запит\n"
            "• Після підтвердження ви отримаєте повідомлення\n"
            "• Вам буде надано доступ до системи\n\n"
            "<i>Зазвичай це займає 1-2 робочі дні.</i>",
            parse_mode="HTML",
        )


async def cmd_pending(message: Message) -> None:
    """Show pending link requests."""
    from backend.core.database import get_db_session
    from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
    from sqlalchemy import select
    from backend.telegram.keyboards import get_inline_keyboard

    async for db in get_db_session():
        result = db.execute(
            select(TelegramLinkRequest)
            .where(TelegramLinkRequest.status == LinkRequestStatus.PENDING)
            .order_by(TelegramLinkRequest.created_at.desc())
        )
        requests = result.scalars().all()

    if not requests:
        await message.answer("✅ Немає нових запитів на підключення.")
        return

    await message.answer(f"📋 <b>Знайдено {len(requests)} запитів:</b>", parse_mode="HTML")

    for req in requests:
        text = (
            f"👤 <b>{req.first_name} {req.last_name or ''}</b>\n"
            f"📱 {req.phone_number or 'Hidden'}\n"
            f"📧 @{req.telegram_username or 'N/A'}\n"
            f"🆔 <code>{req.telegram_user_id}</code>"
        )
        markup = get_inline_keyboard([
            [
                {"text": "✅ Схвалити", "callback_data": f"link_approve_{req.id}"},
                {"text": "❌ Відхилити", "callback_data": f"link_reject_{req.id}"},
            ]
        ])
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def handle_staff_id_for_link(message: Message, state: FSMContext) -> None:
    """Handle staff ID input for linking."""
    from backend.core.database import get_db_session
    from backend.models.staff import Staff
    from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
    from sqlalchemy import select
    import json
    from backend.api.routes.telegram import _send_approval_notification

    data = await state.get_data()
    request_id = data.get("request_id")
    
    try:
        staff_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Будь ласка, введіть числове ID співробітника.")
        return

    async for db in get_db_session():
        # Check staff
        result = db.execute(select(Staff).where(Staff.id == staff_id))
        staff = result.scalar_one_or_none()
        
        if not staff:
            await message.answer("❌ Співробітника з таким ID не знайдено.")
            return

        # Check request
        result = db.execute(select(TelegramLinkRequest).where(TelegramLinkRequest.id == request_id))
        req = result.scalar_one_or_none()
        
        if not req or req.status != LinkRequestStatus.PENDING:
            await message.answer("❌ Запит не знайдено або вже оброблено.")
            await state.clear()
            return

        # Approve
        staff.telegram_user_id = req.telegram_user_id
        staff.telegram_username = req.telegram_username
        default_permissions = ["view_documents", "sign_documents", "view_stale", "manage_stale"]
        staff.telegram_permissions = json.dumps(default_permissions)
        
        req.status = LinkRequestStatus.APPROVED
        req.staff_id = staff_id
        req.approved_by = f"Telegram Admin {message.from_user.id}"
        req.processed_at = datetime.now()
        
        db.commit()
        
        # Notify
        await _send_approval_notification(req.telegram_user_id, staff, default_permissions)
        
        await message.answer(
            f"✅ <b>Успішно!</b>\n\n"
            f"Користувача {req.first_name} прив'язано до {staff.pib_nom}.\n"
            f"Надано повні права доступу.",
            parse_mode="HTML"
        )
        await state.clear()


# ==================== Employee Search (Admin Only) ====================

def _has_admin_access(staff: Staff) -> bool:
    """Check if staff has admin access to view all employees."""
    if not staff or not staff.telegram_permissions:
        return False
    try:
        permissions = json.loads(staff.telegram_permissions)
        return "view_all_documents" in permissions or "admin" in permissions
    except (json.JSONDecodeError, TypeError):
        return False


async def cmd_search(message: Message, state: FSMContext) -> None:
    """Initiate employee search - admin only."""
    from backend.core.database import get_db_session

    telegram_user_id = str(message.from_user.id)

    async for db in get_db_session():
        result = db.execute(
            select(Staff).where(Staff.telegram_user_id == telegram_user_id)
        )
        staff = result.scalar_one_or_none()

    if not staff or not _has_admin_access(staff):
        await message.answer(
            "❌ <b>Доступ заборонено</b>\n\n"
            "Ця функція доступна лише адміністраторам.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    await state.set_state(EmployeeSearchStates.waiting_for_employee_name)
    await message.answer(
        "🔍 <b>Пошук співробітника</b>\n\n"
        "Введіть ПІБ співробітника (повністю або частково):\n\n"
        "<i>Приклад: Іванов Іван Іванович</i>\n\n"
        "❌ Скасувати - відміна пошуку",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="main_menu")]
        ]),
        parse_mode="HTML",
    )


async def handle_employee_name_input(message: Message, state: FSMContext) -> None:
    """Handle employee name input and show results."""
    from backend.core.database import get_db_session
    from sqlalchemy import or_

    search_name = message.text.strip().lower()

    if len(search_name) < 3:
        await message.answer(
            "❌ Введіть щонайменше 3 символи для пошуку.",
        )
        return

    async for db in get_db_session():
        # Search by name (case-insensitive partial match)
        result = db.execute(
            select(Staff)
            .where(
                or_(
                    Staff.pib_nom.ilike(f"%{search_name}%"),
                    Staff.pib_dav.ilike(f"%{search_name}%"),
                )
            )
            .where(Staff.is_active == True)
            .order_by(Staff.pib_nom)
        )
        staff_list = result.scalars().all()

    await state.clear()

    if not staff_list:
        await message.answer(
            f"❌ Співробітників за запитом <b>«{message.text}»</b> не знайдено.\n\n"
            "Спробуйте інший варіант ПІБ.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    # Group by person (same pib_nom = same person, different positions)
    from collections import defaultdict
    person_groups = defaultdict(list)
    for staff in staff_list:
        person_groups[staff.pib_nom].append(staff)

    # Build response
    result_text = f"🔍 <b>Результати пошуку:</b> <b>«{message.text}»</b>\n\n"
    result_text += f"Знайдено співробітників: <b>{len(person_groups)}</b>\n\n"

    # Create inline keyboard with results
    buttons = []

    for idx, (pib, positions) in enumerate(person_groups.items(), 1):
        if len(positions) == 1:
            staff = positions[0]
            pos_label = get_position_label(staff.position)
            result_text += f"{idx}. <b>{pib}</b>\n   📋 {pos_label}\n"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{idx}. {pib[:20]}... ({pos_label[:15]})",
                    callback_data=f"emp_docs_{staff.id}"
                )
            ])
        else:
            # Multiple positions
            pos_labels = ", ".join([get_position_label(s.position)[:10] for s in positions])
            result_text += f"{idx}. <b>{pib}</b>\n   📋 {len(positions)} посади: {pos_labels}\n"
            # Add buttons for each position
            for staff in positions:
                pos_label = get_position_label(staff.position)
                buttons.append([
                    InlineKeyboardButton(
                        text=f"  • {pos_label}",
                        callback_data=f"emp_docs_{staff.id}"
                    )
                ])

    result_text += "\nНатисніть на посаду для перегляду документів:"

    buttons.append([
        InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")
    ])

    await message.answer(
        result_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


def register_command_handlers(dp) -> None:
    """Реєструє обробники команд та повідомлень."""
    from aiogram import F
    from datetime import datetime
    from backend.telegram.states import LinkRequestStates, EmployeeSearchStates
    from backend.telegram.middleware import ChatHistoryCleanupMiddleware

    # Register chat history cleanup middleware for both messages and callbacks
    cleanup_middleware = ChatHistoryCleanupMiddleware()
    dp.message.outer_middleware(cleanup_middleware)
    dp.callback_query.outer_middleware(cleanup_middleware)

    # Commands
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_menu, Command("menu"))
    dp.message.register(cmd_docs, Command("docs"))
    dp.message.register(cmd_stale, Command("stale"))
    dp.message.register(cmd_pending, Command("pending"))
    dp.message.register(cmd_search, Command("search"))  # Admin employee search

    # Contact handler
    dp.message.register(handle_contact, F.contact)

    # Cancel handler (works in any state)
    dp.message.register(handle_cancel, lambda m: m.text == "❌ Скасувати")

    # FSM message handlers
    dp.message.register(handle_stale_explanation, StaleExplanationStates.waiting_for_explanation)
    dp.message.register(handle_staff_id_for_link, LinkRequestStates.waiting_for_staff_id)
    dp.message.register(handle_employee_name_input, EmployeeSearchStates.waiting_for_employee_name)

