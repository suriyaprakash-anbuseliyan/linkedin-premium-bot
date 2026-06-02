"""
handlers/profile.py
───────────────────
User profile page.
"""

import telebot
from config import BOT_USERNAME
from database import get_user
from keyboards.inline import back_to_menu_kb, join_channel_kb
from utils.helpers import check_membership, format_datetime


ACCESS_RESTRICTED = (
    "🔒 <b>Access Restricted</b>\n\n"
    "To use this bot, please join our community first."
)


def register(bot: telebot.TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "menu:profile")
    def cb_profile(call: telebot.types.CallbackQuery):
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

        user = get_user(call.from_user.id)
        if not user:
            bot.answer_callback_query(call.id, "Please /start first.", show_alert=True)
            return

        ref_link = f"https://t.me/{BOT_USERNAME}?start={user['referral_code']}"
        text = (
            "👤 <b>Your Profile</b>\n\n"
            f"🆔 <b>Telegram ID:</b> <code>{user['user_id']}</code>\n"
            f"👤 <b>Username:</b> @{user['username'] or 'N/A'}\n"
            f"💎 <b>Credits:</b> {user['credits']}\n"
            f"⭐ <b>Points:</b> {user.get('referral_points', 0)}\n"
            f"👥 <b>Referral Count:</b> {user['referral_count']}\n"
            f"🎁 <b>Free Referral Credits:</b> {user['free_referral_credits']}\n\n"
            f"🔗 <b>Referral Link:</b>\n<code>{ref_link}</code>\n\n"
            f"📅 <b>Joined:</b> {format_datetime(user.get('joined_at'))}"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "menu:balance")
    def cb_balance(call: telebot.types.CallbackQuery):
        user = get_user(call.from_user.id)
        if not user:
            bot.answer_callback_query(call.id, "Please /start first.", show_alert=True)
            return

        text = (
            "💳 <b>Your Balance</b>\n\n"
            f"💎 <b>Credits:</b> {user['credits']}\n"
            f"⭐ <b>Points:</b> {user.get('referral_points', 0)}\n\n"
            "<i>(You can redeem points for credits in the Refer/Earn menu)</i>"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        bot.answer_callback_query(call.id)
