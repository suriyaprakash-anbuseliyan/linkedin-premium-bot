"""
fallback_bot.py
───────────────
A tiny, ultra-fast script that listens for messages and callback queries
when the main bot is offline, immediately replying with a maintenance notice.
"""

import telebot
from config import BOT_TOKEN, logger

def main():
    logger.info("Starting Fallback Bot…")
    
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

    MAINTENANCE_TEXT = "🚧 The bot is currently offline for maintenance. Please wait..."

    @bot.message_handler(func=lambda m: True)
    def fallback_message(message: telebot.types.Message):
        try:
            bot.reply_to(message, MAINTENANCE_TEXT)
        except Exception as e:
            logger.debug(f"Fallback bot failed to reply to message: {e}")

    @bot.callback_query_handler(func=lambda c: True)
    def fallback_callback(call: telebot.types.CallbackQuery):
        try:
            bot.answer_callback_query(call.id, "🚧 Under maintenance, please wait...", show_alert=True)
        except Exception as e:
            logger.debug(f"Fallback bot failed to answer callback: {e}")

    logger.info("Fallback Bot is now polling…")
    
    # Run polling. If this crashes, the runner script will restart it anyway.
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == "__main__":
    main()
