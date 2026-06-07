"""
handlers/menu.py
────────────────
Main-menu callback router.
Every menu:* callback is funnelled through here and delegates to
the appropriate section handler.
"""

import telebot
from keyboards.inline import main_menu_kb
from utils.helpers import check_membership
from keyboards.inline import join_channel_kb

WELCOME_TEXT = (
    "🎯 <b>Welcome to LinkedIn Premium Store!</b>\n\n"
    "Purchase legitimate LinkedIn Premium referral/benefit links "
    "using credits.\n\n"
    "Use the menu below to get started 👇"
)

ACCESS_RESTRICTED = (
    "🔒 <b>Access Restricted</b>\n\n"
    "To use this bot, please join our community first."
)


def _membership_gate(bot: telebot.TeleBot, call: telebot.types.CallbackQuery) -> bool:
    """
    Check membership and deny access if not joined.
    Returns True if access is granted.
    """
    if not check_membership(bot, call.from_user.id):
        bot.edit_message_text(
            ACCESS_RESTRICTED,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=join_channel_kb(),
        )
        bot.answer_callback_query(call.id)
        return False
    return True


from utils.states import user_states

def register(bot: telebot.TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "menu:main")
    def cb_main_menu(call: telebot.types.CallbackQuery):
        if not _membership_gate(bot, call):
            return
            
        user_states.clear(call.from_user.id)
        
        try:
            bot.edit_message_text(
                WELCOME_TEXT,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=main_menu_kb(),
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e).lower():
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except Exception:
                    pass
                bot.send_message(
                    call.message.chat.id,
                    WELCOME_TEXT,
                    parse_mode="HTML",
                    reply_markup=main_menu_kb(),
                )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "menu:refresh")
    def cb_refresh_menu(call: telebot.types.CallbackQuery):
        if not _membership_gate(bot, call):
            return
            
        user_states.clear(call.from_user.id)
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
            
        bot.send_message(
            call.message.chat.id,
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        bot.answer_callback_query(call.id, "Session refreshed!")
