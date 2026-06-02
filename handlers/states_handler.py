"""
handlers/states_handler.py
──────────────────────────
Catch-all text handler that processes multi-step form inputs.
This module MUST be registered LAST so it doesn't swallow other
message handlers.

Handles:
  • Payment UTR / Binance Order ID input
  • Admin: add product (3 steps)
  • Admin: bulk add stock
  • Admin: search user
  • Admin: add / remove credits
  • Admin: broadcast
"""

import telebot
from config import ADMIN_ID, logger
from database import (
    create_payment, get_user, search_user_by_id,
    add_credits, remove_credits, get_all_user_ids,
    create_product, add_stock_items, set_setting,
)
from keyboards.inline import (
    admin_payment_review_kb, admin_back_kb, back_to_menu_kb,
    admin_panel_kb, payment_settings_kb, admin_user_actions_kb,
)
from utils.helpers import is_admin, format_datetime
from utils.states import user_states


def register(bot: telebot.TeleBot):

    @bot.message_handler(func=lambda m: user_states.has(m.from_user.id))
    def handle_state_input(message: telebot.types.Message):
        user_id = message.from_user.id
        state = user_states.get(user_id)
        if not state:
            return

        action = state.get("action")
        text = message.text.strip() if message.text else ""

        # ── PAYMENT: UTR number ──────────────────────────────────────
        if action == "awaiting_utr":
            _handle_payment_submission(bot, message, state, utr_number=text)
            return

        # ── PAYMENT: Binance Order ID ────────────────────────────────
        if action == "awaiting_binance_id":
            _handle_payment_submission(bot, message, state, binance_order_id=text)
            return

        # ── REDEEM GIFT CODE ─────────────────────────────────────────
        if action == "awaiting_gift_code":
            _handle_redeem_gift_code(bot, message, text)
            return

        # ── ADMIN: Generate Gift Code (multi-step) ───────────────────
        if action == "awaiting_gift_gen_credits" and is_admin(user_id):
            _handle_gift_gen_credits(bot, message, state, text)
            return
            
        if action == "awaiting_gift_gen_uses" and is_admin(user_id):
            _handle_gift_gen_uses(bot, message, state, text)
            return
            
        if action == "awaiting_gift_gen_expiry" and is_admin(user_id):
            _handle_gift_gen_expiry(bot, message, state, text)
            return

        # ── ADMIN: Add Product (multi-step) ──────────────────────────
        if action == "admin_add_product" and is_admin(user_id):
            _handle_add_product_step(bot, message, state, text)
            return

        # ── ADMIN: Bulk add stock ────────────────────────────────────
        if action == "admin_add_stock" and is_admin(user_id):
            _handle_add_stock(bot, message, state, text)
            return

        # ── ADMIN: Search User ───────────────────────────────────────
        if action == "admin_search_user" and is_admin(user_id):
            _handle_search_user(bot, message, text)
            return

        # ── ADMIN: Add / Remove Credits ──────────────────────────────
        if action == "admin_credits" and is_admin(user_id):
            _handle_admin_credits(bot, message, state, text)
            return

        # ── ADMIN: Broadcast ─────────────────────────────────────────
        if action == "admin_broadcast" and is_admin(user_id):
            _handle_broadcast(bot, message, text)
            return

        # ── ADMIN: Edit payment setting ──────────────────────────────
        if action == "admin_edit_setting" and is_admin(user_id):
            _handle_edit_setting(bot, message, state, text)
            return

        # ── USER: Buy multiple links ─────────────────────────────────
        if action == "buy_quantity":
            _handle_buy_quantity(bot, message, state, text)
            return

        # ── ADMIN: Edit Product ──────────────────────────────────────
        if action == "admin_edit_product" and is_admin(user_id):
            _handle_admin_edit_product(bot, message, state, text)
            return

        # ── ADMIN: Send Gift Code Privately ──────────────────────────
        if action == "admin_gift_send_private" and is_admin(user_id):
            _handle_gift_send_private(bot, message, state, text)
            return


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAYMENT submission                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_payment_submission(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    utr_number: str | None = None,
    binance_order_id: str | None = None,
):
    user_id = message.from_user.id
    username = message.from_user.username or ""

    # Auto-verify Binance
    is_auto_verified = False
    if state["method"] == "Binance" and binance_order_id:
        from database import check_binance_order_exists
        if check_binance_order_exists(binance_order_id):
            bot.send_message(
                user_id,
                "❌ <b>Duplicate Order ID</b>\nThis transaction has already been processed.",
                parse_mode="HTML",
                reply_markup=back_to_menu_kb()
            )
            user_states.clear(user_id)
            return
            
        bot.send_message(user_id, "⏳ Verifying Binance transaction automatically...")
        from utils.payments import verify_binance_pay_transaction
        expected_note = state.get("expected_note", "")
        if verify_binance_pay_transaction(binance_order_id, state["amount"], expected_note):
            is_auto_verified = True

    payment_id = create_payment(
        user_id=user_id,
        username=username,
        method=state["method"],
        amount=state["amount"],
        credits=state["credits"],
        utr_number=utr_number,
        binance_order_id=binance_order_id,
    )
    user_states.clear(user_id)
    logger.info(
        "Payment submitted: user=%s method=%s credits=%s payment_id=%s auto_verified=%s",
        user_id, state["method"], state["credits"], payment_id, is_auto_verified
    )

    if is_auto_verified:
        from database import approve_payment, add_credits
        from utils.helpers import announce_event
        
        approve_payment(str(payment_id))
        add_credits(user_id, state["credits"])
        announce_event(bot, f"CREDIT ADDED ({state['method'].upper()})", user_id, state["credits"], "Auto-Approved")
        
        bot.send_message(
            user_id,
            "✅ <b>Payment Verified Automatically!</b>\n\n"
            f"💎 <b>{state['credits']} credit(s)</b> have been added to your account.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        
        # Notify admin of auto-approval
        admin_text = (
            "✅ <b>Auto-Approved Payment</b>\n\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"👤 Username: @{username}\n"
            f"💰 Method: {state['method']}\n"
            f"💵 Amount: {state['amount']}\n"
            f"💎 Credits: {state['credits']}\n"
            f"🔢 Order ID: <code>{binance_order_id}</code>"
        )
        try:
            bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
        except Exception:
            pass
        return

    # Confirm to user (manual review)
    bot.send_message(
        user_id,
        "✅ <b>Payment submitted successfully!</b>\n\n"
        "We could not verify it automatically. Your credits will be added shortly after manual review.",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )

    # Notify admin
    txn = utr_number or binance_order_id or "N/A"
    txn_label = "UTR Number" if state["method"] == "UPI" else "Binance Order ID"
    admin_text = (
        "🔔 <b>New Payment Request (Needs Review)</b>\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"👤 Username: @{username}\n"
        f"💰 Method: {state['method']}\n"
        f"💵 Amount: {state['amount']}\n"
        f"💎 Credits: {state['credits']}\n"
        f"🔢 {txn_label}: <code>{txn}</code>"
    )
    try:
        bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="HTML",
            reply_markup=admin_payment_review_kb(payment_id),
        )
    except Exception as exc:
        logger.error("Failed to notify admin: %s", exc)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Add Product (3-step form)                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_add_product_step(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    user_id = message.from_user.id
    step = state.get("step")

    if step == "name":
        user_states.update(user_id, step="description", product_name=text)
        bot.send_message(
            user_id,
            "Step 2/3 — Enter the <b>description</b>:",
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )

    elif step == "description":
        user_states.update(user_id, step="credit_cost", product_desc=text)
        bot.send_message(
            user_id,
            "Step 3/3 — Enter the <b>credit cost</b> (integer):",
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )

    elif step == "credit_cost":
        try:
            cost = int(text)
            if cost <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(user_id, "❌ Please enter a valid positive integer.")
            return

        product_id = create_product(
            name=state["product_name"],
            description=state["product_desc"],
            credit_cost=cost,
        )
        user_states.clear(user_id)
        logger.info("Product created: %s (id=%s)", state["product_name"], product_id)
        bot.send_message(
            user_id,
            f"✅ <b>Product Created!</b>\n\n"
            f"Name: <b>{state['product_name']}</b>\n"
            f"Cost: {cost} credits\n"
            f"ID: <code>{product_id}</code>\n\n"
            "📦 Now go to <b>Manage Products</b> → select this product → "
            "<b>Add Stock</b> to bulk-import your links.",
            parse_mode="HTML",
            reply_markup=admin_panel_kb(),
        )

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Edit product                                                ║
# ╚══════════════════════════════════════════════════════════════════════╝
def _handle_admin_edit_product(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    from database import update_product
    from keyboards.inline import admin_panel_kb
    
    user_id = message.from_user.id
    pid = state["product_id"]
    field = state["field"]
    
    if field == "cost":
        try:
            val = int(text)
            if val < 0:
                raise ValueError
        except ValueError:
            bot.send_message(user_id, "❌ Please enter a valid non-negative integer for the cost.")
            return
        update_product(pid, {"$set": {"credit_cost": val}})
        field_str = "Cost"
    elif field == "name":
        update_product(pid, {"$set": {"name": text.strip()}})
        field_str = "Name"
    elif field == "desc":
        update_product(pid, {"$set": {"description": text.strip()}})
        field_str = "Description"
        
    user_states.clear(user_id)
    
    bot.send_message(
        user_id,
        f"✅ Product {field_str} updated successfully!",
        reply_markup=admin_panel_kb()
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Bulk add stock                                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_add_stock(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    from utils.helpers import extract_all_linkedin_links, validate_linkedin_link

    user_id = message.from_user.id
    product_id = state["product_id"]
    product_name = state["product_name"]

    # Extract all possible links from the raw text
    extracted_urls = extract_all_linkedin_links(text)
    
    if not extracted_urls:
        bot.send_message(user_id, "❌ No LinkedIn Premium links found in the text.\nMake sure they contain 'linkedin.com/premium/redeem/'")
        return

    # Validate each link against LinkedIn referral format
    valid_links = []
    rejected = []
    
    # We still want to show the admin what was rejected.
    # We can split the original text by whitespace/newlines to find rejected parts,
    # or we can just say "X rejected" based on what failed validation.
    # Actually, any extracted_url might fail the stricter `validate_linkedin_link` checks (like missing coupon).
    for url in extracted_urls:
        if validate_linkedin_link(url):
            # deduplicate
            if url not in valid_links:
                valid_links.append(url)
        else:
            rejected.append(url)

    # Add valid links to stock
    added = 0
    if valid_links:
        added = add_stock_items(product_id, valid_links)

    user_states.clear(user_id)
    logger.info(
        "Stock import: product=%s valid=%s rejected=%s",
        product_name, added, len(rejected),
    )

    # Build response
    lines = [f"📦 <b>Stock Import — {product_name}</b>\n"]
    lines.append(f"✅ Valid links added: <b>{added}</b>")
    lines.append(f"❌ Rejected (invalid format): <b>{len(rejected)}</b>")

    if rejected:
        # Show first 10 rejected links so admin can inspect
        lines.append("\n<b>Rejected links:</b>")
        for r in rejected[:10]:
            truncated = r[:60] + "…" if len(r) > 60 else r
            lines.append(f"• <code>{truncated}</code>")
        if len(rejected) > 10:
            lines.append(f"  … and {len(rejected) - 10} more")

    if added == 0 and rejected:
        lines.append(
            "\n⚠️ No links were added. Make sure links match:\n"
            "<code>https://www.linkedin.com/premium/redeem/?...&coupon=XXXXX&...</code>"
        )

    bot.send_message(
        user_id,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Search user by Telegram ID                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_search_user(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    text: str,
):
    user_id = message.from_user.id
    user_states.clear(user_id)

    try:
        target_id = int(text)
    except ValueError:
        bot.send_message(user_id, "❌ Invalid Telegram ID.", reply_markup=admin_back_kb())
        return

    user = search_user_by_id(target_id)
    if not user:
        bot.send_message(
            user_id,
            f"❌ User <code>{target_id}</code> not found.",
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        return

    info = (
        "👤 <b>User Info</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Username: @{user.get('username', 'N/A')}\n"
        f"📛 Name: {user.get('first_name', 'N/A')}\n"
        f"💎 Credits: {user['credits']}\n"
        f"👥 Referrals: {user['referral_count']}\n"
        f"🎁 Free Credits: {user['free_referral_credits']}\n"
        f"🔗 Referred By: {user.get('referred_by', 'N/A')}\n"
        f"📅 Joined: {format_datetime(user.get('joined_at'))}"
    )
    bot.send_message(
        user_id, 
        info, 
        parse_mode="HTML", 
        reply_markup=admin_user_actions_kb(user['user_id'], user.get('is_banned', False))
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Add / Remove Credits                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_admin_credits(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    user_id = message.from_user.id
    step = state.get("step")
    operation = state.get("operation")  # "add" or "remove"

    if step == "user_id":
        try:
            target_id = int(text)
        except ValueError:
            bot.send_message(user_id, "❌ Invalid Telegram ID.")
            return
        target = get_user(target_id)
        if not target:
            bot.send_message(
                user_id,
                f"❌ User <code>{target_id}</code> not found.",
                parse_mode="HTML",
                reply_markup=admin_back_kb(),
            )
            user_states.clear(user_id)
            return
        user_states.update(user_id, step="amount", target_id=target_id)
        bot.send_message(
            user_id,
            f"User found: @{target.get('username', 'N/A')} "
            f"(current credits: {target['credits']})\n\n"
            f"Enter the number of credits to <b>{operation}</b>:",
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )

    elif step == "amount":
        try:
            amount = int(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(user_id, "❌ Please enter a valid positive integer.")
            return

        target_id = state["target_id"]
        if operation == "add":
            add_credits(target_id, amount)
            action_text = f"➕ Added <b>{amount}</b> credits"
        else:
            remove_credits(target_id, amount)
            action_text = f"➖ Removed <b>{amount}</b> credits"

        user_states.clear(user_id)
        logger.info("Admin %s credits: user=%s amount=%s", operation, target_id, amount)
        
        if operation == "add":
            from database import get_user
            u = get_user(target_id)
            if u:
                from utils.helpers import announce_event
                announce_event(bot, "CREDIT ADDED (ADMIN)", target_id, u["credits"], "Approved")

        bot.send_message(
            user_id,
            f"✅ {action_text} for user <code>{target_id}</code>.",
            parse_mode="HTML",
            reply_markup=admin_panel_kb(),
        )

        # Notify the target user
        try:
            emoji = "➕" if operation == "add" else "➖"
            bot.send_message(
                target_id,
                f"{emoji} <b>{amount} credit(s)</b> have been "
                f"{'added to' if operation == 'add' else 'removed from'} your account by admin.",
                parse_mode="HTML",
            )
        except Exception:
            pass


def _handle_redeem_gift_code(bot: telebot.TeleBot, message: telebot.types.Message, code: str):
    user_id = message.from_user.id
    if not code:
        bot.send_message(user_id, "❌ Invalid code format.", reply_markup=back_to_menu_kb())
        user_states.clear(user_id)
        return
        
    from database import redeem_gift_code
    result = redeem_gift_code(code, user_id)
    
    if result is True:
        bot.send_message(
            user_id,
            "🎉 <b>Success!</b>\n\nYour gift code has been redeemed and points have been added to your account.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb()
        )
        from utils.helpers import announce_event
        announce_event(bot, "GIFT CODE REDEEMED", user_id, 0, "Redeemed")
    else:
        bot.send_message(
            user_id,
            f"❌ <b>Error:</b> {result}",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb()
        )
    user_states.clear(user_id)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Generate Gift Code (3-step form)                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_gift_gen_credits(bot: telebot.TeleBot, message: telebot.types.Message, state: dict, text: str):
    try:
        points_val = int(text)
        if points_val <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid positive number.")
        return
        
    state["points"] = points_val
    state["action"] = "awaiting_gift_gen_uses"
    user_states.set(message.from_user.id, state)
    
    bot.send_message(
        message.chat.id,
        "🎁 How many users can redeem this code? (Enter a number, e.g., 1 for single-use, 100 for multi-use):",
        reply_markup=admin_back_kb()
    )


def _handle_gift_gen_uses(bot: telebot.TeleBot, message: telebot.types.Message, state: dict, text: str):
    try:
        uses = int(text)
        if uses <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid positive number.")
        return
        
    state["max_uses"] = uses
    state["action"] = "awaiting_gift_gen_expiry"
    user_states.set(message.from_user.id, state)
    
    bot.send_message(
        message.chat.id,
        "🎁 When should this code expire?\n\n"
        "Enter time in format: <b>HH MM</b> (hours and minutes)\n"
        "Examples:\n"
        "• <code>0 30</code> → 0 hrs 30 min\n"
        "• <code>2 0</code> → 2 hrs 0 min\n"
        "• <code>1 30</code> → 1 hr 30 min\n"
        "• <code>0 0</code> → No expiration",
        parse_mode="HTML",
        reply_markup=admin_back_kb()
    )


def _handle_gift_gen_expiry(bot: telebot.TeleBot, message: telebot.types.Message, state: dict, text: str):
    parts = text.strip().split()
    try:
        if len(parts) == 1:
            # Backwards compat: single number = hours only
            hours = int(parts[0])
            minutes = 0
        elif len(parts) == 2:
            hours = int(parts[0])
            minutes = int(parts[1])
        else:
            raise ValueError
        if hours < 0 or minutes < 0 or minutes > 59:
            raise ValueError
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Invalid format. Please enter time as <b>HH MM</b> (e.g. <code>0 30</code> or <code>2 0</code>).",
            parse_mode="HTML",
        )
        return
        
    import random, string
    from datetime import datetime, timedelta, timezone
    from database import create_gift_code
    
    total_minutes = hours * 60 + minutes
    expires_at = None
    if total_minutes > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=total_minutes)
        
    code = "GIFT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    create_gift_code(
        code=code,
        points_value=state["points"],
        max_uses=state["max_uses"],
        expires_at=expires_at,
        created_by=message.from_user.id
    )
    
    user_states.clear(message.from_user.id)
    
    if total_minutes > 0:
        expiry_str = f"{hours} hrs {minutes} min"
    else:
        expiry_str = "Never"
    
    from keyboards.inline import gift_code_actions_kb
    
    bot.send_message(
        message.chat.id,
        f"🎉 <b>Gift Code Generated!</b>\n\n"
        f"┌─────────────────────────\n"
        f"│ 🎟 Code: <code>{code}</code>\n"
        f"│ (tap to copy)\n"
        f"└─────────────────────────\n\n"
        f"🏆 Points: <b>{state['points']}</b>\n"
        f"👥 Max Uses: <b>{state['max_uses']}</b>\n"
        f"⏳ Expires: <b>{expiry_str}</b>",
        parse_mode="HTML",
        reply_markup=gift_code_actions_kb(code)
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Add Product (3-step form)                                   ║                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  BUY QUANTITY                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_buy_quantity(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    from database import get_product, get_user
    from keyboards.inline import confirm_purchase_kb, products_list_kb

    user_id = message.from_user.id
    product_id = state["product_id"]
    max_stock = state.get("max_stock", 1)

    try:
        qty = int(text)
        if qty <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(user_id, "❌ Please enter a valid positive number.")
        return

    if qty > max_stock:
        bot.send_message(user_id, f"❌ We only have {max_stock} in stock. Please enter a smaller number.")
        return

    product = get_product(product_id)
    if not product:
        bot.send_message(user_id, "❌ Product not found.")
        user_states.clear(user_id)
        return

    user = get_user(user_id)
    total_cost = product["credit_cost"] * qty

    if user["credits"] < total_cost:
        bot.send_message(
            user_id,
            f"❌ Insufficient credits.\n"
            f"You need {total_cost} credits for {qty} link(s), but you have {user['credits']}.\n"
            f"Please add more credits.",
            reply_markup=telebot.types.InlineKeyboardMarkup().add(
                telebot.types.InlineKeyboardButton("🔙 Back to Buy Menu", callback_data="menu:buy")
            )
        )
        user_states.clear(user_id)
        return

    user_states.clear(user_id)

    text_msg = (
        f"⚠️ <b>Confirm Purchase</b>\n\n"
        f"Product: <b>{product['name']}</b>\n"
        f"Quantity: <b>{qty} link(s)</b>\n"
        f"Total Cost: <b>{total_cost} credit(s)</b>\n"
        f"Your balance: <b>{user['credits']} credit(s)</b>\n\n"
        f"Proceed?"
    )
    # We will encode quantity into the callback data: prod:confirm:{product_id}:{qty}
    # Need to make sure confirm_purchase_kb accepts qty
    bot.send_message(
        user_id,
        text_msg,
        parse_mode="HTML",
        reply_markup=confirm_purchase_kb(product_id, qty),
    )

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Broadcast                                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_broadcast(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    text: str,
):
    user_id = message.from_user.id
    user_states.clear(user_id)

    all_ids = get_all_user_ids()
    success, failed = 0, 0
    for uid in all_ids:
        try:
            bot.send_message(uid, text, parse_mode="HTML")
            success += 1
        except Exception:
            failed += 1

    logger.info("Broadcast: sent=%s failed=%s", success, failed)
    bot.send_message(
        user_id,
        f"📢 <b>Broadcast Complete</b>\n\n"
        f"✅ Sent: {success}\n❌ Failed: {failed}",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Edit payment setting                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_edit_setting(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    user_id = message.from_user.id
    setting_key = state["setting_key"]
    setting_label = state["setting_label"]

    if not text:
        bot.send_message(user_id, "❌ Value cannot be empty. Try again.")
        return

    set_setting(setting_key, text)
    user_states.clear(user_id)
    logger.info("Setting updated: %s = %s", setting_key, text)

    bot.send_message(
        user_id,
        f"✅ <b>{setting_label}</b> updated!\n\n"
        f"New value: <code>{text}</code>",
        parse_mode="HTML",
        reply_markup=payment_settings_kb(),
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Send Gift Code Privately                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_gift_send_private(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    user_id = message.from_user.id
    code = state["gift_code"]
    user_states.clear(user_id)
    
    try:
        target_id = int(text)
    except ValueError:
        bot.send_message(user_id, "❌ Invalid Telegram ID.", reply_markup=admin_back_kb())
        return
    
    from database import get_gift_code
    code_doc = get_gift_code(code)
    if not code_doc:
        bot.send_message(user_id, "❌ Gift code not found.", reply_markup=admin_back_kb())
        return
    
    msg_text = (
        "🎁 <b>Gift Code!</b>\n\n"
        f"You received a private gift code:\n\n"
        f"┌─────────────────────────\n"
        f"│ 🎟 <code>{code}</code>\n"
        f"│ (tap to copy)\n"
        f"└─────────────────────────\n\n"
        f"🏆 Points: <b>{code_doc['points']}</b>\n\n"
        "Go to <b>🎟 Redeem Gift Code</b> in the menu to redeem!"
    )
    
    try:
        bot.send_message(target_id, msg_text, parse_mode="HTML")
        bot.send_message(
            user_id,
            f"✅ Gift code <code>{code}</code> sent to user <code>{target_id}</code>.",
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
    except Exception as exc:
        bot.send_message(
            user_id,
            f"❌ Failed to send to user <code>{target_id}</code>.\n"
            f"Error: {exc}",
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
