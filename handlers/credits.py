"""
handlers/credits.py
───────────────────
Credit-purchase flow: package selection → payment method → UTR / Order-ID input.
"""

import telebot
from config import ADMIN_ID, logger
from database import create_payment, get_user
from keyboards.inline import (
    payment_method_kb, cancel_payment_kb,
    admin_payment_review_kb, join_channel_kb,
)
from utils.helpers import check_membership, get_payment_settings
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

    # ── Show credit input prompt ─────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "menu:credits")
    def cb_add_credits(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        
        user_states.set(call.from_user.id, {"action": "awaiting_credit_amount"})

        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="menu:main"))

        bot.edit_message_text(
            "💳 <b>Add Credits</b>\n\n"
            "Please enter the number of credits you want to purchase.\n\n"
            "<i>Pricing Rules:</i>\n"
            "• 2 Credits = $1 / ₹106\n"
            "• Minimum purchase: 2 credits",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    # ── UPI payment instructions ─────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay:upi:"))
    def cb_pay_upi(call: telebot.types.CallbackQuery):
        credits_qty = int(call.data.split(":")[2])
        inr_price = credits_qty * 53

        from utils.payments import create_razorpay_payment_link
        import time
        ref_id = f"UPI_{call.from_user.id}_{int(time.time())}"
        
        bot.answer_callback_query(call.id, "Generating Payment Link...")
        
        link_data = create_razorpay_payment_link(inr_price, ref_id, f"Buy {credits_qty} credits")
        if not link_data:
            bot.edit_message_text(
                "❌ Failed to generate payment link. Please try again later or contact support.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=cancel_payment_kb()
            )
            return

        user_states.set(call.from_user.id, {
            "action": "verify_razorpay",
            "credits": credits_qty,
            "amount": inr_price,
            "method": "UPI",
            "payment_link_id": link_data["id"]
        })

        kb = telebot.types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            telebot.types.InlineKeyboardButton("🔗 Pay Now", url=link_data["short_url"]),
            telebot.types.InlineKeyboardButton("✅ I Have Paid", callback_data="verify_payment"),
            telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="menu:credits")
        )

        text = (
            "💳 <b>UPI Payment</b>\n\n"
            f"Amount: <b>₹{inr_price}</b>\n"
            f"Credits: <b>{credits_qty}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Click <b>Pay Now</b> to complete the payment via Razorpay.\n"
            "Once completed, click <b>✅ I Have Paid</b> to verify and receive your credits automatically."
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )

    # ── Binance payment instructions ─────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay:binance:"))
    def cb_pay_binance(call: telebot.types.CallbackQuery):
        credits_qty = int(call.data.split(":")[2])
        usdt_price = credits_qty * 0.5

        import time
        import random
        # Generate a unique short note (e.g., BOT-1A2B)
        expected_note = f"BOT-{random.randint(1000, 9999)}"

        user_states.set(call.from_user.id, {
            "action": "awaiting_binance_id",
            "credits": credits_qty,
            "amount": usdt_price,
            "method": "Binance",
            "expected_note": expected_note,
        })

        ps = get_payment_settings()
        text = (
            "🪙 <b>Binance Payment</b>\n\n"
            f"Amount: <b>${usdt_price} USDT</b>\n"
            f"Credits: <b>{credits_qty}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Binance UID:</b> <code>{ps['binance_uid']}</code>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ <b>IMPORTANT:</b> You MUST enter the exact note below in the <b>'Note' / 'Remarks'</b> field when sending the payment, or it will NOT be verified automatically.\n\n"
            f"<b>Required Note:</b> <code>{expected_note}</code>\n\n"
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

    # ── Automated Payment Verification ───────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "verify_payment")
    def cb_verify_payment(call: telebot.types.CallbackQuery):
        state = user_states.get(call.from_user.id)
        if not state:
            bot.answer_callback_query(call.id, "Session expired. Please start again.", show_alert=True)
            return
            
        action = state.get("action")
        if action not in ["verify_razorpay", "verify_binance"]:
            bot.answer_callback_query(call.id, "Invalid state.", show_alert=True)
            return
            
        bot.answer_callback_query(call.id, "Verifying payment...")
        
        is_paid = False
        method = state.get("method")
        
        if action == "verify_razorpay":
            from utils.payments import verify_razorpay_payment
            is_paid = verify_razorpay_payment(state["payment_link_id"])
            
        if not is_paid:
            bot.send_message(
                call.message.chat.id,
                "❌ Payment not received yet. Please wait a moment and try again if you've already paid."
            )
            return
            
        # Payment is successful!
        user_id = call.from_user.id
        credits = state["credits"]
        amount = state["amount"]
        
        # We can reuse _handle_payment_submission logic but automate approval
        from database import create_payment, add_credits
        from utils.helpers import announce_event
        from config import logger
        from keyboards.inline import back_to_menu_kb
        
        username = call.from_user.username or ""
        
        # Log payment in DB as automatically approved
        payment_id = create_payment(
            user_id=user_id,
            username=username,
            method=method,
            amount=amount,
            credits=credits,
            utr_number=state.get("payment_link_id") or state.get("prepay_id")
        )
        
        from database import approve_payment
        approve_payment(str(payment_id))
        
        add_credits(user_id, credits)
        user_states.clear(user_id)
        
        logger.info(
            "Auto Payment approved: user=%s method=%s credits=%s payment_id=%s",
            user_id, method, credits, payment_id,
        )
        
        from database import get_user
        u = get_user(user_id)
        if u:
            announce_event(bot, f"CREDIT ADDED ({method.upper()})", user_id, u["credits"], "Auto-Approved")
            
        bot.edit_message_text(
            "✅ <b>Payment Verified!</b>\n\n"
            f"💎 <b>{credits} credit(s)</b> have been automatically added to your account.\n"
            "Thank you! 🎉",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
