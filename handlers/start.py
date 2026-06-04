"""
handlers/start.py
─────────────────
/start command – entry point for every user.

Responsibilities:
  1. Mandatory channel-join gate.
  2. Auto-register new users (with referral attribution).
  3. Show main menu to verified members.
"""

import telebot
from config import BOT_USERNAME, REFERRALS_PER_CREDIT, logger
from database import (
    get_user, register_user, get_user_by_referral_code,
    increment_referral_count, is_referral_enabled,
)
from keyboards.inline import join_channel_kb, main_menu_kb
from utils.helpers import check_membership, generate_referral_code
from utils.states import user_states


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


def register(bot: telebot.TeleBot):

    @bot.message_handler(commands=["start"])
    def cmd_start(message: telebot.types.Message):
        user_id = message.from_user.id
        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""

        # ── Extract referral code from /start payload ────────────────
        referral_payload: str | None = None
        parts = message.text.strip().split()
        if len(parts) > 1:
            referral_payload = parts[1]

        # ── Mandatory join check ─────────────────────────────────────
        if not check_membership(bot, user_id):
            if referral_payload:
                user_states.set(user_id, {"pending_referral": referral_payload})
                
            bot.send_message(
                user_id,
                ACCESS_RESTRICTED,
                parse_mode="HTML",
                reply_markup=join_channel_kb(),
            )
            return

        # ── Register user if new ─────────────────────────────────────
        user = get_user(user_id)
        if user is None:
            ref_code = generate_referral_code()
            referred_by: str | None = None

            # Validate referral (only if referral program is enabled)
            if referral_payload and is_referral_enabled():
                referrer = get_user_by_referral_code(referral_payload)
                if referrer and referrer["user_id"] != user_id:
                    referred_by = referral_payload
                    # Credit the referrer
                    updated_referrer = increment_referral_count(referrer["user_id"])
                    if updated_referrer:
                        _maybe_award_referral(bot, updated_referrer)

            register_user(user_id, username, first_name, ref_code, referred_by)
            bot.send_message(
                chat_id,
                f"👋 <b>Welcome {username}!</b>\n\n"
                "You have successfully registered. Let's get started!",
                parse_mode="HTML",
                reply_markup=main_menu_kb()
            )
            from database import is_welcome_bonus_enabled
            if is_welcome_bonus_enabled():
                msg = bot.send_message(
                    chat_id,
                    "🎉 <b>Welcome Bonus!</b>\n\nYou received <b>1 Point</b> for joining us. You can redeem points for free credits in the Referral menu!",
                    parse_mode="HTML"
                )
                from database import schedule_message_cleanup
                schedule_message_cleanup(chat_id, msg.message_id, hours=24)
            logger.info("New user registered: %s (%s)", user_id, username)
            from utils.helpers import announce_event
            announce_event(bot, "NEW USER JOINED", user_id, 0, "Registered")

        # ── Show main menu ───────────────────────────────────────────
        bot.send_message(
            user_id,
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )

    # ── "I've Joined" callback ───────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "check_join")
    def cb_check_join(call: telebot.types.CallbackQuery):
        user_id = call.from_user.id

        if not check_membership(bot, user_id):
            bot.answer_callback_query(
                call.id,
                "❌ You haven't joined yet. Please join and try again.",
                show_alert=True,
            )
            return

        # Auto-register if needed
        user = get_user(user_id)
        if user is None:
            ref_code = generate_referral_code()
            referred_by: str | None = None
            
            # Check if they had a pending referral from before they joined
            state = user_states.get(user_id) or {}
            referral_payload = state.get("pending_referral")
            
            if referral_payload and is_referral_enabled():
                referrer = get_user_by_referral_code(referral_payload)
                if referrer and referrer["user_id"] != user_id:
                    referred_by = referral_payload
                    updated_referrer = increment_referral_count(referrer["user_id"])
                    if updated_referrer:
                        _maybe_award_referral(bot, updated_referrer)
            
            register_user(
                user_id,
                call.from_user.username or "",
                call.from_user.first_name or "",
                ref_code,
                referred_by
            )
            user_states.clear(user_id)
            logger.info("New user registered via join-check: %s", user_id)
            from utils.helpers import announce_event
            announce_event(bot, "NEW USER JOINED", user_id, 0, "Registered")
            
            from database import is_welcome_bonus_enabled
            if is_welcome_bonus_enabled():
                msg = bot.send_message(
                    user_id,
                    "🎉 <b>Welcome Bonus!</b>\n\nYou received <b>1 Point</b> for joining us. You can redeem points for free credits in the Referral menu!",
                    parse_mode="HTML"
                )
                from database import schedule_message_cleanup
                schedule_message_cleanup(user_id, msg.message_id, hours=24)

        bot.edit_message_text(
            WELCOME_TEXT,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        bot.answer_callback_query(call.id, "✅ Welcome!")


def _maybe_award_referral(bot: telebot.TeleBot, referrer: dict) -> None:
    """Notify the referrer that someone used their link."""
    try:
        msg = bot.send_message(
            referrer["user_id"],
            "🎉 <b>Someone just joined using your referral link!</b>\n\n"
            "You earned <b>1 referral point</b>. Go to the <b>Referral</b> menu "
            "to convert your points into free credits! 🚀",
            parse_mode="HTML",
        )
        from database import schedule_message_cleanup
        schedule_message_cleanup(referrer["user_id"], msg.message_id, hours=24)
    except Exception:
        pass  # user may have blocked the bot
