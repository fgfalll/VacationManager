"""Telegram bot runner for polling mode (development/testing)."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[2]))


def get_db_telegram_settings() -> dict:
    """
    Read Telegram settings from database.
    
    Returns:
        dict with enabled, bot_token, webhook_url, mini_app_url
    """
    import sqlite3
    db_path = Path(__file__).resolve().parents[2] / "vacation_manager.db"
    
    result = {
        "enabled": False,
        "bot_token": "",
        "webhook_url": "",
        "mini_app_url": "",
    }
    
    if not db_path.exists():
        return result
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM settings WHERE key = 'telegram_enabled'")
        row = cursor.fetchone()
        result["enabled"] = row[0].lower() in ('true', '1', 'yes') if row and row[0] else False
        
        cursor.execute("SELECT value FROM settings WHERE key = 'telegram_bot_token'")
        row = cursor.fetchone()
        result["bot_token"] = row[0] if row and row[0] else ""
        
        cursor.execute("SELECT value FROM settings WHERE key = 'telegram_webhook_url'")
        row = cursor.fetchone()
        result["webhook_url"] = row[0] if row and row[0] else ""
        
        cursor.execute("SELECT value FROM settings WHERE key = 'telegram_mini_app_url'")
        row = cursor.fetchone()
        result["mini_app_url"] = row[0] if row and row[0] else ""
        
        conn.close()
    except Exception as e:
        logging.warning(f"Could not read database settings: {e}")
    
    return result


async def main(skip_updates: bool = False, log_level: str = "INFO"):
    """
    Main bot entry point.
    
    Args:
        skip_updates: Skip pending updates on start
        log_level: Logging level
    """
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    
    # Read settings from database first, then fall back to environment
    import os
    db_settings = get_db_telegram_settings()
    
    # Override environment from database if not already set
    if db_settings["bot_token"] and not os.getenv("VM_TELEGRAM_BOT_TOKEN"):
        os.environ["VM_TELEGRAM_BOT_TOKEN"] = db_settings["bot_token"]
    if db_settings["enabled"]:
        os.environ["VM_TELEGRAM_ENABLED"] = "true"
    if db_settings["webhook_url"] and not os.getenv("VM_TELEGRAM_WEBHOOK_URL"):
        os.environ["VM_TELEGRAM_WEBHOOK_URL"] = db_settings["webhook_url"]
    if db_settings["mini_app_url"] and not os.getenv("VM_TELEGRAM_MINI_APP_URL"):
        os.environ["VM_TELEGRAM_MINI_APP_URL"] = db_settings["mini_app_url"]
    
    # Clear settings cache so they reload with new env vars
    from backend.core.config import get_settings
    get_settings.cache_clear()
    
    # Now import bot (which uses settings)
    from backend.telegram.bot import bot, dp
    from backend.telegram.handlers import register_command_handlers, register_callback_handlers
    from backend.telegram.handlers.messages import register_message_handlers
    
    if not bot:
        logger.error("Bot token not configured!")
        logger.error("Configure it in Desktop app → Settings → Telegram")
        logger.error("Or set VM_TELEGRAM_BOT_TOKEN environment variable")
        return
    
    # Register all handlers
    register_command_handlers(dp)
    register_callback_handlers(dp)
    register_message_handlers(dp)
    
    logger.info("Starting Telegram bot in polling mode...")
    logger.info(f"Bot token: ...{os.getenv('VM_TELEGRAM_BOT_TOKEN', '')[-6:]}")
    logger.info(f"Mini App URL: {os.getenv('VM_TELEGRAM_MINI_APP_URL', 'Not configured')}")
    
    # Delete webhook and start polling
    try:
        await bot.delete_webhook(drop_pending_updates=skip_updates)
        logger.info("Webhook cleared, starting polling...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Telegram bot in polling mode")
    parser.add_argument(
        "--skip-updates", 
        action="store_true", 
        help="Skip pending updates on start"
    )
    parser.add_argument(
        "--log-level", 
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(
            skip_updates=args.skip_updates,
            log_level=args.log_level
        ))
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"\nBot error: {e}")
        sys.exit(1)
