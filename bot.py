"""
bot.py
──────
Entry point for the LinkedIn Premium Store Telegram Bot.
Initializes the bot, registers handlers, and starts polling.
"""

import telebot
from config import BOT_TOKEN, logger
from database import ensure_indexes
from handlers import register_all_handlers


def main():
    logger.info("Starting LinkedIn Premium Store Bot…")

    # ── Ensure MongoDB indexes ───────────────────────────────────────
    ensure_indexes()

    # ── Create bot instance ──────────────────────────────────────────
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, use_class_middlewares=True)

    # ── Gracefully handle stale callback errors ──────────────────────
    class SilentExceptionHandler(telebot.ExceptionHandler):
        def handle(self, exception):
            logger.error("Suppressed polling exception: %s", exception, exc_info=True)
            return True  # True = handled, don't crash

    bot.exception_handler = SilentExceptionHandler()

    # ── Global Middleware for Banned Users ───────────────────────────
    from telebot.handler_backends import BaseMiddleware, CancelUpdate
    
    class BanMiddleware(BaseMiddleware):
        def __init__(self):
            self.update_types = ['message', 'callback_query']
            
        def pre_process(self, message, data):
            from database import get_user
            user_id = message.from_user.id if hasattr(message, "from_user") else None
            if user_id:
                user = get_user(user_id)
                if user and user.get("is_banned"):
                    return CancelUpdate()
                    
        def post_process(self, message, data, exception):
            pass

    bot.setup_middleware(BanMiddleware())
    
    class MaintenanceMiddleware(BaseMiddleware):
        def __init__(self):
            self.update_types = ['message', 'callback_query']
            
        def pre_process(self, message, data):
            from database import is_maintenance_mode
            from utils.helpers import is_admin
            user_id = message.from_user.id if hasattr(message, "from_user") else None
            
            if user_id and is_maintenance_mode():
                if not is_admin(user_id):
                    # Answer callbacks if it's a callback query
                    if hasattr(message, "data"):
                        try:
                            bot.answer_callback_query(message.id, "🚧 Under Maintenance", show_alert=True)
                        except Exception:
                            pass
                    else:
                        try:
                            bot.send_message(
                                user_id, 
                                "🚧 <b>Under Maintenance</b>\n\nThe bot is currently undergoing maintenance. Please try again later.", 
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    return CancelUpdate()
                    
        def post_process(self, message, data, exception):
            pass

    bot.setup_middleware(MaintenanceMiddleware())

    # ── Register all handlers ────────────────────────────────────────
    register_all_handlers(bot)
    logger.info("All handlers registered.")

    # ── Startup Broadcast ────────────────────────────────────────────
    def broadcast_online():
        from config import ADMIN_ID
        try:
            bot.send_message(
                ADMIN_ID,
                "✅ <b>Server updated</b>",
                parse_mode="HTML"
            )
            logger.info("Sent startup notification to admin.")
        except Exception as exc:
            logger.error("Failed to send startup notification to admin: %s", exc)
        
    import threading
    threading.Thread(target=broadcast_online, daemon=True).start()

    # ── Start polling ────────────────────────────────────────────────
    logger.info("Bot is now polling for updates…")
    bot.infinity_polling(
        timeout=60,
        long_polling_timeout=60,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    main()
