"""
handlers/wallet.py
───────────────────
Wallet top-up flow: enter USD amount → payment method → UTR / Order-ID input.
"""

import telebot
from config import logger, USD_TO_INR_RATE, UPI_ID, UPI_NAME, UPI_QR_PATH
from database import create_payment, get_user
from keyboards.inline import (
    payment_method_kb, cancel_payment_kb,
    join_channel_kb,
)
from utils.helpers import check_membership
from database import get_payment_settings
from utils.states import user_states

ACCESS_RESTRICTED = (
    "🔒 <b>Access Restricted</b>\n\n"
    "To use this bot, please join our community first."
)

def _gate(bot, call):
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

def register(bot: telebot.TeleBot):

    # ── Show add funds prompt ─────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data in ["menu:wallet_add", "menu:credits"])
    def cb_add_funds(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        
        user_states.set(call.from_user.id, {"action": "awaiting_topup_amount"})

        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="menu:main"))

        bot.edit_message_text(
            "💳 <b>Add Funds to Wallet</b>\n\n"
            "Please enter the amount in USD ($) you want to add.\n\n"
            "<i>Minimum top-up: $1.00</i>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    # ── UPI payment instructions ─────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay:upi:"))
    def cb_pay_upi(call: telebot.types.CallbackQuery):
        try:
            amount_usd = float(call.data.split(":")[2])
        except ValueError:
            bot.answer_callback_query(call.id, "Invalid amount", show_alert=True)
            return

        inr_price = int(amount_usd * USD_TO_INR_RATE)

        user_states.set(call.from_user.id, {
            "action": "awaiting_utr",
            "amount_usd": amount_usd,
            "method": "UPI",
            "intent": "add_to_wallet"
        })

        text = (
            "💳 <b>UPI Payment</b>\n\n"
            f"Amount to Pay: <b>₹{inr_price}</b> (for ${amount_usd:.2f})\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"<b>UPI ID:</b> <code>{UPI_ID}</code>\n"
            f"<b>Name:</b> {UPI_NAME}\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "Please transfer the exact amount and then <b>enter your 12-digit UTR Number</b> below 👇"
        )
        
        try:
            with open(UPI_QR_PATH, "rb") as qr:
                bot.send_photo(
                    chat_id=call.message.chat.id,
                    photo=qr,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=cancel_payment_kb()
                )
            # delete old message if we sent a photo
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            logger.warning(f"Could not open UPI QR at {UPI_QR_PATH}: {e}")
            bot.edit_message_text(
                text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=cancel_payment_kb(),
            )

    # ── Binance payment instructions ─────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay:binance:"))
    def cb_pay_binance(call: telebot.types.CallbackQuery):
        try:
            amount_usd = float(call.data.split(":")[2])
        except ValueError:
            bot.answer_callback_query(call.id, "Invalid amount", show_alert=True)
            return

        user_states.set(call.from_user.id, {
            "action": "awaiting_binance_id",
            "amount_usd": amount_usd,
            "method": "Binance",
            "intent": "add_to_wallet"
        })

        ps = get_payment_settings()
        text = (
            "🪙 <b>Binance Payment</b>\n\n"
            f"Amount to Pay: <b>${amount_usd:.2f} USDT</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Binance UID:</b> <code>{ps['binance_uid']}</code>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "After transferring via Binance Pay, <b>enter your Binance Order ID</b> below 👇"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=cancel_payment_kb(),
        )
        bot.answer_callback_query(call.id)

    # ── BEP-20 payment instructions ─────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay:bep20:"))
    def cb_pay_bep20(call: telebot.types.CallbackQuery):
        try:
            amount_usd = float(call.data.split(":")[2])
        except ValueError:
            bot.answer_callback_query(call.id, "Invalid amount", show_alert=True)
            return

        user_states.set(call.from_user.id, {
            "action": "awaiting_bep20_id",
            "amount_usd": amount_usd,
            "method": "BEP-20",
            "intent": "add_to_wallet"
        })

        ps = get_payment_settings()
        text = (
            "🔗 <b>BEP-20 (USDT) Payment</b>\n\n"
            f"Amount to Pay: <b>${amount_usd:.2f} USDT</b>\n"
            "Network: <b>BNB Smart Chain (BEP-20)</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Deposit Address:</b>\n<code>{ps.get('bep20_address')}</code>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "Please transfer the exact amount and then <b>enter your Transaction ID (TxHash)</b> below 👇"
        )
        
        from config import BEP20_QR_PATH
        try:
            with open(BEP20_QR_PATH, "rb") as qr:
                bot.send_photo(
                    chat_id=call.message.chat.id,
                    photo=qr,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=cancel_payment_kb()
                )
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            logger.warning(f"Could not open BEP-20 QR at {BEP20_QR_PATH}: {e}")
            bot.edit_message_text(
                text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=cancel_payment_kb(),
            )
