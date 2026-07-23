"""
handlers/referral.py
────────────────────
Referral info page.
"""

import telebot
from config import BOT_USERNAME
from database import get_user, is_referral_enabled, get_referral_config, get_referral_stats, transfer_referral_commission
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
        commission_pct = ref_config.get("commission_percent", 2.0)
        first_bonus = ref_config.get("first_purchase_bonus", 0.10)
        min_transfer = ref_config.get("min_transfer", 2.00)

        ref_link = f"https://t.me/{BOT_USERNAME}?start={user['referral_code']}"
        
        stats = get_referral_stats(user['referral_code'])
        earned = user.get("referral_earned_usdt", 0.0)
        available = user.get("referral_available_usdt", 0.0)
        transferred = user.get("referral_transferred_usdt", 0.0)

        text = (
            "⭐ <b>Refer & Earn</b>\n\n"
            f"➕ 👥 <b>Referred (24h):</b> {stats['24h']}\n"
            f"➕ 👥 <b>Referred (7d):</b> {stats['7d']}\n"
            f"➕ 👥 <b>Referred (Total):</b> {stats['total']}\n\n"
            f"🗂 <b>Total Earned:</b> {earned:.2f} USDT\n"
            f"🧀 <b>Available:</b> {available:.2f} USDT\n"
            f"📉 <b>Transferred:</b> {transferred:.2f} USDT\n\n"
            f"👥 Earn <b>{commission_pct}%</b> of every purchase/deposit by your referred users.\n"
            f"👥 +<b>${first_bonus:.2f}</b> bonus on their first purchase.\n\n"
            f"Transfer earnings to wallet (Min ${min_transfer:.2f} USDT).\n\n"
            "⚠️ Self-referrals are tracked via payment methods and names. Any self-referral activity will lead to loss of all referral commissions.\n\n"
            f"Your Referral Link:\n<code>{ref_link}</code>"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=referral_menu_kb(),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "ref:transfer")
    def cb_transfer_funds(call: telebot.types.CallbackQuery):
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
        min_transfer = ref_config.get("min_transfer", 2.00)
        available = user.get("referral_available_usdt", 0.0)
        
        if available < min_transfer:
            bot.answer_callback_query(call.id, f"❌ Minimum transfer is ${min_transfer:.2f} USDT. You have ${available:.2f} USDT.", show_alert=True)
            return

        if transfer_referral_commission(user_id, available):
            bot.answer_callback_query(call.id, f"🎉 Success! Transferred ${available:.2f} USDT to your wallet.", show_alert=True)
            cb_referral(call)
        else:
            bot.answer_callback_query(call.id, "❌ Failed to transfer. Please try again.", show_alert=True)


