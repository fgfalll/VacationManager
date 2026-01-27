"""Telegram API routes for Mini App integration."""

import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.security import create_access_token
from backend.models.staff import Staff
from sqlalchemy import select

router = APIRouter()
settings = get_settings()


# ==================== Pydantic Schemas ====================


class TelegramUserResponse(BaseModel):
    """Інформація про користувача."""
    id: int
    pib_nom: str
    position: str
    department: str
    telegram_username: Optional[str] = None
    email: Optional[str] = None


class TelegramAuthRequest(BaseModel):
    """Запит на автентифікацію через Telegram WebApp."""
    init_data: str = Field(..., description="Telegram WebApp initData")


class TelegramAuthResponse(BaseModel):
    """Відповідь на автентифікацію."""
    access_token: str
    token_type: str = "bearer"
    user: TelegramUserResponse


class TelegramLinkRequest(BaseModel):
    """Запит на прив'язку Telegram акаунту."""
    telegram_user_id: str = Field(..., description="Telegram user ID")


class TelegramLinkResponse(BaseModel):
    """Відповідь на прив'язку Telegram акаунту."""
    success: bool
    message: str


# ==================== Helper Functions ====================


def verify_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """
    Перевіряє підпис Telegram WebApp initData.

    Args:
        init_data: Рядок initData від Telegram WebApp
        bot_token: Token бота

    Returns:
        bool: True якщо підпис валідний
    """
    try:
        # initData формат: query_string з параметрами
        # Останній параметр - hash
        params = dict(x.split('=', 1) for x in init_data.split('&'))

        if 'hash' not in params:
            return False

        hash_value = params.pop('hash')

        # Сортуємо параметри та формуємо рядок для перевірки
        sorted_params = sorted(params.items())
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted_params)

        # Створюємо HMAC-SHA256
        secret_key = hmac.new(
            key="WebAppData".encode(),
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        return calculated_hash == hash_value
    except Exception:
        return False


def parse_init_data(init_data: str) -> dict:
    """
    Парсить initData в словник.

    Args:
        init_data: Рядок initData від Telegram WebApp

    Returns:
        dict: Параметри з initData
    """
    try:
        return dict(x.split('=', 1) for x in init_data.split('&'))
    except Exception:
        return {}


# ==================== API Endpoints ====================


@router.post("/auth", response_model=TelegramAuthResponse)
async def telegram_auth(
    request: TelegramAuthRequest,
    request_obj: Request
):
    """
    Автентифікація через Telegram WebApp.

    Перевіряє initData з Telegram Mini App та видає JWT токен.
    """
    # Перевіряємо initData
    if not verify_telegram_init_data(request.init_data, settings.telegram_bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram init data")

    # Парсимо initData
    params = parse_init_data(request.init_data)

    # Отримуємо user_id
    user_id = params.get('user', {}).get('id') if params.get('user', '{}') != '{}' else None
    if not user_id:
        # Або парсимо user як JSON
        import json
        try:
            user_data = json.loads(params.get('user', '{}'))
            user_id = user_data.get('id')
        except:
            raise HTTPException(status_code=401, detail="Cannot extract user_id from init data")

    telegram_user_id = str(user_id)

    # Шукаємо користувача в базі
    from backend.core.database import get_db_session
    async for db in get_db_session():
        result = db.execute(
            select(Staff).where(Staff.telegram_user_id == telegram_user_id)
        )
        staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Telegram account not linked to any staff member"
        )

    # Створюємо JWT токен
    access_token = create_access_token(data={"sub": str(staff.id)})

    return TelegramAuthResponse(
        access_token=access_token,
        user=TelegramUserResponse(
            id=staff.id,
            pib_nom=staff.pib_nom,
            position=staff.position,
            department=staff.department,
            telegram_username=staff.telegram_username,
            email=staff.email,
        )
    )


@router.get("/user", response_model=TelegramUserResponse)
async def get_telegram_user(staff: Staff = Depends(lambda: None)):
    """
    Отримати інформацію про поточного користувача.

    Requires authentication via JWT token.
    """
    from backend.core.dependencies import get_current_user

    current_user = await get_current_user()
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return TelegramUserResponse(
        id=current_user.id,
        pib_nom=current_user.pib_nom,
        position=current_user.position,
        department=current_user.department,
        telegram_username=current_user.telegram_username,
        email=current_user.email,
    )


@router.post("/link", response_model=TelegramLinkResponse)
async def link_telegram_account(
    request: TelegramLinkRequest,
    staff: Staff = Depends(lambda: None)
):
    """
    Прив'язати Telegram акаунт до запису співробітника.

    Requires authentication via JWT token (сurrent user).
    """
    from backend.core.dependencies import get_current_user

    current_user = await get_current_user()
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Перевіряємо, чи цей telegram_user_id вже прив'язаний
    from backend.core.database import get_db_session
    async for db in get_db_session():
        result = db.execute(
            select(Staff).where(Staff.telegram_user_id == request.telegram_user_id)
        )
        existing_staff = result.scalar_one_or_none()

        if existing_staff and existing_staff.id != current_user.id:
            return TelegramLinkResponse(
                success=False,
                message="This Telegram account is already linked to another staff member"
            )

        # Оновлюємо поточного користувача
        current_user.telegram_user_id = request.telegram_user_id
        db.commit()
        db.refresh(current_user)

    return TelegramLinkResponse(
        success=True,
        message="Telegram account linked successfully"
    )


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Отримує webhook оновлення від Telegram.

    Це endpoint, куди Telegram надсилає оновлення.
    """
    # Перевіряємо, чи увімкнений Telegram
    if not settings.telegram_enabled:
        raise HTTPException(status_code=503, detail="Telegram bot is not enabled")

    # Отримуємо update з тіла запиту
    update_data = await request.json()

    # Обробляємо update через aiogram dispatcher
    try:
        from aiogram.types import Update
        from backend.telegram.bot import dp, bot
        if bot is None:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")
        
        # Parse JSON into Update object for aiogram 3.x
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing update: {str(e)}")


@router.get("/info")
async def get_telegram_info():
    """
    Отримати інформацію про Telegram бота.

    Повертає статус бота та URL Mini App.
    """
    return {
        "enabled": settings.telegram_enabled,
        "mini_app_url": settings.telegram_mini_app_url,
        "webhook_url": settings.telegram_webhook_url,
    }


# ==================== Link Request Management ====================


class LinkRequestResponse(BaseModel):
    """Response for a single link request."""
    id: int
    telegram_user_id: str
    telegram_username: Optional[str]
    phone_number: Optional[str]
    first_name: str
    last_name: Optional[str]
    status: str
    staff_id: Optional[int]
    staff_name: Optional[str]
    approved_by: Optional[str]
    rejection_reason: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]


class ApproveRequestBody(BaseModel):
    """Body for approving a link request."""
    staff_id: int = Field(..., description="ID of staff to link")
    permissions: list[str] = Field(
        default=["view_documents"],
        description="List of permissions to grant"
    )


class RejectRequestBody(BaseModel):
    """Body for rejecting a link request."""
    reason: Optional[str] = Field(None, description="Rejection reason")


@router.get("/link-requests", response_model=list[LinkRequestResponse])
async def list_link_requests(
    status: Optional[str] = None,
    db=Depends(get_db),
):
    """
    Отримати список запитів на прив'язку.

    Args:
        status: Фільтр за статусом (pending, approved, rejected)
    """
    from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
    
    query = select(TelegramLinkRequest).order_by(TelegramLinkRequest.created_at.desc())
    
    if status:
        try:
            status_enum = LinkRequestStatus(status)
            query = query.where(TelegramLinkRequest.status == status_enum)
        except ValueError:
            pass
    
    result = db.execute(query)
    requests = result.scalars().all()
    
    response = []
    for req in requests:
        staff_name = None
        if req.staff_id:
            staff = db.execute(select(Staff).where(Staff.id == req.staff_id)).scalar_one_or_none()
            if staff:
                staff_name = staff.pib_nom
        
        response.append(LinkRequestResponse(
            id=req.id,
            telegram_user_id=req.telegram_user_id,
            telegram_username=req.telegram_username,
            phone_number=req.phone_number,
            first_name=req.first_name,
            last_name=req.last_name,
            status=req.status.value,
            staff_id=req.staff_id,
            staff_name=staff_name,
            approved_by=req.approved_by,
            rejection_reason=req.rejection_reason,
            created_at=req.created_at,
            processed_at=req.processed_at,
        ))
    
    return response


@router.post("/link-requests/{request_id}/approve")
async def approve_link_request(
    request_id: int,
    body: ApproveRequestBody,
    db=Depends(get_db),
):
    """
    Схвалити запит на прив'язку.

    Прив'язує Telegram акаунт до обраного співробітника.
    """
    import json
    from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
    
    # Get the request
    link_request = db.execute(
        select(TelegramLinkRequest).where(TelegramLinkRequest.id == request_id)
    ).scalar_one_or_none()
    
    if not link_request:
        raise HTTPException(status_code=404, detail="Запит не знайдено")
    
    if link_request.status != LinkRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Запит вже оброблено")
    
    # Get the staff
    staff = db.execute(select(Staff).where(Staff.id == body.staff_id)).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")
    
    # Check if staff already linked to another account
    if staff.telegram_user_id and staff.telegram_user_id != link_request.telegram_user_id:
        raise HTTPException(
            status_code=400, 
            detail="Цей співробітник вже прив'язаний до іншого Telegram акаунту"
        )
    
    # Update staff with telegram info and permissions
    staff.telegram_user_id = link_request.telegram_user_id
    staff.telegram_username = link_request.telegram_username
    staff.telegram_permissions = json.dumps(body.permissions)
    
    # Update request status
    link_request.status = LinkRequestStatus.APPROVED
    link_request.staff_id = body.staff_id
    link_request.approved_by = "Admin"  # TODO: use actual admin name
    link_request.processed_at = datetime.now(timezone.utc)
    
    db.commit()
    
    # Send notification to user
    await _send_approval_notification(
        telegram_user_id=link_request.telegram_user_id,
        staff=staff,
        permissions=body.permissions,
    )
    
    return {
        "success": True,
        "message": f"Запит схвалено. {staff.pib_nom} прив'язано до Telegram.",
    }


@router.post("/link-requests/{request_id}/reject")
async def reject_link_request(
    request_id: int,
    body: RejectRequestBody,
    db=Depends(get_db),
):
    """
    Відхилити запит на прив'язку.
    """
    from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
    
    link_request = db.execute(
        select(TelegramLinkRequest).where(TelegramLinkRequest.id == request_id)
    ).scalar_one_or_none()
    
    if not link_request:
        raise HTTPException(status_code=404, detail="Запит не знайдено")
    
    if link_request.status != LinkRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Запит вже оброблено")
    
    link_request.status = LinkRequestStatus.REJECTED
    link_request.rejection_reason = body.reason
    link_request.approved_by = "Admin"
    link_request.processed_at = datetime.now(timezone.utc)
    
    db.commit()
    
    # Send rejection notification
    await _send_rejection_notification(
        telegram_user_id=link_request.telegram_user_id,
        reason=body.reason,
    )
    
    return {"success": True, "message": "Запит відхилено"}


@router.post("/link-requests/{request_id}/unlink")
async def unlink_telegram_request(
    request_id: int,
    db=Depends(get_db),
):
    """
    Відв'язати Telegram акаунт.
    """
    from backend.models.telegram_link_request import TelegramLinkRequest, LinkRequestStatus
    
    link_request = db.execute(
        select(TelegramLinkRequest).where(TelegramLinkRequest.id == request_id)
    ).scalar_one_or_none()
    
    if not link_request:
        raise HTTPException(status_code=404, detail="Запит не знайдено")
    
    # Unlink from staff
    if link_request.staff_id:
        staff = db.execute(select(Staff).where(Staff.id == link_request.staff_id)).scalar_one_or_none()
        if staff:
            staff.telegram_user_id = None
            staff.telegram_username = None
            staff.telegram_permissions = None
    
    # Update request status
    link_request.status = LinkRequestStatus.REJECTED
    link_request.rejection_reason = "Unlinked by admin"
    link_request.processed_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {"success": True, "message": "Юзера успішно відв'язано"}


async def _send_approval_notification(
    telegram_user_id: str,
    staff: Staff,
    permissions: list[str],
) -> None:
    """Send approval notification to user via Telegram."""
    try:
        from backend.telegram.bot import bot
        from backend.telegram.keyboards import get_main_menu_keyboard
        
        if not bot:
            return
        
        permission_labels = {
            "view_documents": "📄 Перегляд документів",
            "sign_documents": "✍️ Підписання документів",
            "view_stale": "⏰ Перегляд застарілих",
            "manage_stale": "🔧 Управління застарілими",
        }
        
        perm_text = "\n".join(
            f"• {permission_labels.get(p, p)}" 
            for p in permissions
        )
        
        await bot.send_message(
            chat_id=int(telegram_user_id),
            text=(
                f"🎉 <b>Вітаємо, {staff.pib_nom}!</b>\n\n"
                f"Ваш Telegram акаунт успішно прив'язано до системи VacationManager.\n\n"
                f"📋 <b>Ваша посада:</b> {staff.position}\n"
                f"🏢 <b>Підрозділ:</b> {staff.department or 'Не вказано'}\n\n"
                f"<b>🔐 Ваші права доступу:</b>\n{perm_text}\n\n"
                f"Оберіть дію з меню нижче:"
            ),
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to send approval notification: {e}")


async def _send_rejection_notification(
    telegram_user_id: str,
    reason: Optional[str],
) -> None:
    """Send rejection notification to user via Telegram."""
    try:
        from backend.telegram.bot import bot
        
        if not bot:
            return
        
        reason_text = f"\n\n<b>Причина:</b> {reason}" if reason else ""
        
        await bot.send_message(
            chat_id=int(telegram_user_id),
            text=(
                f"❌ <b>Запит відхилено</b>\n\n"
                f"На жаль, ваш запит на прив'язку Telegram акаунту було відхилено.{reason_text}\n\n"
                f"Зверніться до адміністратора для уточнення."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to send rejection notification: {e}")

