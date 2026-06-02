"""
handlers/referral.py
────────────────────
Referral info page.
"""

import telebot
from config import BOT_USERNAME, REFERRALS_PER_CREDIT, MAX_FREE_REFERRAL_CREDITS
from database import get_user, redeem_referral_points
from keyboards.inline import referral_menu_kb, join_channel_kb, back_to_menu_kb
from utils.helpers import check_membership


ACCESS_RESTRICTED = (
    "🔒 <b>Access Restricted</b>\n\n"
    "To use this bot, please join our community first."
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

        user = get_user(call.from_user.id)
        if not user:
            bot.answer_callback_query(call.id, "Please /start first.", show_alert=True)
            return

        ref_link = f"https://t.me/{BOT_USERNAME}?start={user['referral_code']}"
        points = user.get("referral_points", 0)
        can_convert = points >= REFERRALS_PER_CREDIT and user["free_referral_credits"] < MAX_FREE_REFERRAL_CREDITS

        text = (
            "🎁 <b>Referral Program</b>\n\n"
            f"Share your referral link and earn <b>free credits</b>!\n\n"
            f"📊 <b>Total Referrals:</b> {user['referral_count']}\n"
            f"🪙 <b>Referral Points:</b> {points}\n"
            f"🎁 <b>Free Credits Earned:</b> {user['free_referral_credits']}/{MAX_FREE_REFERRAL_CREDITS}\n\n"
            f"💡 <b>Rules:</b>\n"
            f"• 1 referral = 1 point\n"
            f"• {REFERRALS_PER_CREDIT} points = +1 credit\n"
            f"• Maximum {MAX_FREE_REFERRAL_CREDITS} free credits\n"
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

        user = get_user(user_id)
        if not user:
            return

        points = user.get("referral_points", 0)
        
        if user["free_referral_credits"] >= MAX_FREE_REFERRAL_CREDITS:
            bot.answer_callback_query(call.id, "❌ You have reached the maximum free credits limit.", show_alert=True)
            return
            
        if points < REFERRALS_PER_CREDIT:
            bot.answer_callback_query(call.id, f"❌ Not enough points. You need {REFERRALS_PER_CREDIT} points.", show_alert=True)
            return

        if redeem_referral_points(user_id, REFERRALS_PER_CREDIT):
            bot.answer_callback_query(call.id, f"🎉 Success! Converted {REFERRALS_PER_CREDIT} points to 1 credit.", show_alert=True)
            # Re-render the menu
            cb_referral(call)
        else:
            bot.answer_callback_query(call.id, "❌ Failed to convert. Please try again.", show_alert=True)

