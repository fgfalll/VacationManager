"""Inline keyboard builders for Telegram bot."""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from typing import List, Optional


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Головне меню бота (Reply Keyboard для мобільних).
    
    Returns:
        ReplyKeyboardMarkup: Клавіатура з основними кнопками
    """
    buttons = [
        [KeyboardButton(text="📄 Мої документи")],
        [KeyboardButton(text="📋 Сьогоднішні")],
        [KeyboardButton(text="⚠️ Проблемні")],
        [KeyboardButton(text="👤 Профіль"), KeyboardButton(text="❓ Допомога")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, persistent=True)


def get_document_list_keyboard(
    documents: List[dict], 
    page: int = 0, 
    per_page: int = 5,
    list_type: str = "today"
) -> InlineKeyboardMarkup:
    """
    Клавіатура зі списком документів з пагінацією.

    Args:
        documents: Список документів (dict з id, doc_type, status, staff_name)
        page: Номер сторінки (0-indexed)
        per_page: Документів на сторінку
        list_type: Тип списку для callback (today, stale, my)

    Returns:
        InlineKeyboardMarkup: Клавіатура зі списком
    """
    start = page * per_page
    end = start + per_page
    page_docs = documents[start:end]
    total_pages = (len(documents) + per_page - 1) // per_page

    buttons = []

    # Document buttons
    status_emoji = {
        "draft": "📝",
        "signed_by_applicant": "✍️",
        "approved_by_dispatcher": "👍",
        "signed_dep_head": "👨‍💼",
        "agreed": "🤝",
        "signed_rector": "🎓",
        "scanned": "📸",
        "processed": "✅",
    }

    for doc in page_docs:
        emoji = status_emoji.get(doc.get("status", "").lower(), "📄")
        # Truncate staff name if too long
        staff_name = doc.get("staff_name", "")[:10]
        type_lbl = doc.get("type_label", "")
        dates = doc.get("dates", "")

        parts = [f"{emoji} #{doc['id']}"]
        if type_lbl:
            parts.append(type_lbl)
        if dates:
            parts.append(dates)
        if staff_name:
            parts.append(staff_name)
            
        text = " ".join(parts)
        
        buttons.append([
            InlineKeyboardButton(
                text=text, 
                callback_data=f"doc_view_{doc['id']}"
            )
        ])

    # Pagination row
    pagination = []
    if page > 0:
        pagination.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"docs_{list_type}_page_{page-1}")
        )
    if total_pages > 1:
        pagination.append(
            InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop")
        )
    if page < total_pages - 1:
        pagination.append(
            InlineKeyboardButton(text="➡️", callback_data=f"docs_{list_type}_page_{page+1}")
        )
    if pagination:
        buttons.append(pagination)

    # Back button
    buttons.append([
        InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_document_detail_keyboard(document_id: int, status: str) -> InlineKeyboardMarkup:
    """
    Клавіатура для детального перегляду документа з діями на основі статусу.

    Args:
        document_id: ID документа
        status: Поточний статус документа (lowercase)

    Returns:
        InlineKeyboardMarkup: Клавіатура з діями
    """
    buttons = []
    action_row = []

    # Status-based actions
    if status == "draft":
        action_row.append(
            InlineKeyboardButton(text="✅ Підписати (заявник)", callback_data=f"doc_sign_{document_id}")
        )
    elif status == "signed_by_applicant":
        action_row.append(
            InlineKeyboardButton(text="👍 Погодити (диспетчер)", callback_data=f"doc_forward_{document_id}")
        )
    elif status == "approved_by_dispatcher":
        action_row.append(
            InlineKeyboardButton(text="✅ Підписати (зав. каф.)", callback_data=f"doc_sign_{document_id}")
        )
    elif status == "signed_dep_head":
        action_row.append(
            InlineKeyboardButton(text="🤝 Узгодити", callback_data=f"doc_forward_{document_id}")
        )
    elif status == "agreed":
        action_row.append(
            InlineKeyboardButton(text="🎓 Підписати (ректор)", callback_data=f"doc_sign_{document_id}")
        )
    elif status == "signed_rector":
        # Scan upload only available in Mini App
        action_row.append(
            InlineKeyboardButton(text="📸 Скан (тільки Mini App)", callback_data=f"doc_scan_info_{document_id}")
        )
    # No actions for scanned/processed

    if action_row:
        buttons.append(action_row)

    # Back button
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="documents_today"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_stale_document_keyboard(document_id: int) -> InlineKeyboardMarkup:
    """
    Клавіатура для дій із застарілим документом.

    Args:
        document_id: ID документа

    Returns:
        InlineKeyboardMarkup: Клавіатура з діями
    """
    buttons = [
        [
            InlineKeyboardButton(text="💬 Пояснити", callback_data=f"stale_explain_{document_id}"),
            InlineKeyboardButton(text="✅ Вирішено", callback_data=f"stale_resolve_{document_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="documents_stale"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_keyboard(action: str, document_id: int) -> InlineKeyboardMarkup:
    """
    Клавіатура підтвердження дії.

    Args:
        action: Тип дії (sign, forward, resolve)
        document_id: ID документа

    Returns:
        InlineKeyboardMarkup: Клавіатура підтвердження
    """
    buttons = [
        [
            InlineKeyboardButton(text="✅ Так, підтверджую", callback_data=f"confirm_{action}_{document_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Скасувати", callback_data=f"doc_view_{document_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавіатура для запиту контакту (прив'язка Telegram акаунту).

    Returns:
        ReplyKeyboardMarkup: Клавіатура з кнопкою контакту
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поділитися контактом", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    return keyboard


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавіатура з кнопкою скасування.

    Returns:
        ReplyKeyboardMarkup: Клавіатура з кнопкою скасування
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True,
    )
    return keyboard


def get_back_keyboard(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    """
    Проста клавіатура з кнопкою назад.

    Args:
        callback_data: Callback для кнопки назад

    Returns:
        InlineKeyboardMarkup: Клавіатура
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)]
    ])
