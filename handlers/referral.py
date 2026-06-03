"""
handlers/referral.py
────────────────────
Referral info page.
"""

import telebot
from config import BOT_USERNAME
from database import get_user, redeem_referral_points, is_referral_enabled, get_referral_config
from keyboards.inline import referral_menu_kb, join_channel_kb, back_to_menu_kb
from utils.helpers import check_membership


ACCESS_RESTRICTED = (
    "🔒 <b>Access Restricted</b>\n\n"
    "To use this bot, please join our community first."
)

REFERRAL_DISABLED = (
    "🚫 <b>Referral Program Paused</b>\n\n"
    "The referral program is currently not available. "
    "Please check back later!"
)


def register(bot: telebot.TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "menu:referral")
    def cb_referral(call: telebot.types.CallbackQuery):
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

        if not is_referral_enabled():
            bot.edit_message_text(
                REFERRAL_DISABLED,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=back_to_menu_kb(),
            )
            bot.answer_callback_query(call.id)
            return

        user = get_user(call.from_user.id)
        if not user:
            bot.answer_callback_query(call.id, "Please /start first.", show_alert=True)
            return

        ref_config = get_referral_config()
        points_per_credit = ref_config["points_per_credit"]
        max_free_credits = ref_config["max_free_credits"]

        ref_link = f"https://t.me/{BOT_USERNAME}?start={user['referral_code']}"
        points = user.get("referral_points", 0)
        can_convert = points >= points_per_credit and user["free_referral_credits"] < max_free_credits

        text = (
            "🎁 <b>Referral Program</b>\n\n"
            f"Share your referral link and earn <b>free credits</b>!\n\n"
            f"📊 <b>Total Referrals:</b> {user['referral_count']}\n"
            f"🪙 <b>Referral Points:</b> {points}\n"
            f"🎁 <b>Free Credits Earned:</b> {user['free_referral_credits']}/{max_free_credits}\n\n"
            f"💡 <b>Rules:</b>\n"
            f"• 1 referral = 1 point\n"
            f"• {points_per_credit} points = +1 credit\n"
            f"• Maximum {max_free_credits} free credits\n"
            f"• Only new users count\n"
            f"• No self-referrals\n\n"
            f"🔗 <b>Your Referral Link:</b>\n<code>{ref_link}</code>"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=referral_menu_kb(can_convert),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "ref:convert")
    def cb_convert_points(call: telebot.types.CallbackQuery):
        user_id = call.from_user.id
        if not check_membership(bot, user_id):
            bot.answer_callback_query(call.id, "Please join the channel first.", show_alert=True)
            return

        if not is_referral_enabled():
            bot.answer_callback_query(call.id, "🚫 Referral program is currently paused.", show_alert=True)
            return

        user = get_user(user_id)
        if not user:
            return

        ref_config = get_referral_config()
        points_per_credit = ref_config["points_per_credit"]
        max_free_credits = ref_config["max_free_credits"]

        points = user.get("referral_points", 0)
        
        if user["free_referral_credits"] >= max_free_credits:
            bot.answer_callback_query(call.id, "❌ You have reached the maximum free credits limit.", show_alert=True)
            return
            
        if points < points_per_credit:
            bot.answer_callback_query(call.id, f"❌ Not enough points. You need {points_per_credit} points.", show_alert=True)
            return

        if redeem_referral_points(user_id, points_per_credit):
            bot.answer_callback_query(call.id, f"🎉 Success! Converted {points_per_credit} points to 1 credit.", show_alert=True)
            # Re-render the menu
            cb_referral(call)
        else:
            bot.answer_callback_query(call.id, "❌ Failed to convert. Please try again.", show_alert=True)


