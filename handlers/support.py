"""
handlers/support.py
───────────────────
Support / help page.
"""

import telebot
from config import ADMIN_ID
from keyboards.inline import back_to_menu_kb, join_channel_kb
from utils.helpers import check_membership


ACCESS_RESTRICTED = (
    "🔒 <b>Access Restricted</b>\n\n"
    "To use this bot, please join our community first."
)


def register(bot: telebot.TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "menu:support")
    def cb_support(call: telebot.types.CallbackQuery):
        if not check_membership(bot, call.from_user.id):
            bot.edit_message_text(
                ACCESS_RESTRICTED,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=join_channel_kb(),
            )
            bot.answer_callback_query(call.id)
            return

        text = (
            "📞 <b>Support</b>\n\n"
            "Need help? We're here for you!\n\n"
            "📩 <b>Contact Admin:</b>\n"
            f"<a href='tg://user?id={ADMIN_ID}'>Click here to message admin</a>\n\n"
            "💡 <b>Common Questions:</b>\n"
            "• <b>How to buy?</b> — Add credits → Buy product\n"
            "• <b>Payment not approved?</b> — Allow up to 24h\n"
            "• <b>Wrong UTR/Order ID?</b> — Contact admin\n"
            "• <b>Referral not counted?</b> — Only new users count\n\n"
            "⏰ <b>Response Time:</b> Usually within a few hours"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        bot.answer_callback_query(call.id)
