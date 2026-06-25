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
import csv
import io
import threading
import time

def _run_broadcast_new_stock(bot: telebot.TeleBot, product_name: str, added_count: int, product_id: str):
    from database import get_all_user_ids, get_available_stock_count
    
    total_stock = get_available_stock_count(product_id)
    msg_text = (
        f"📢 <b>New Stock Added!</b>\n\n"
        f"📦 Product: <b>{product_name}</b>\n"
        f"✅ New Links Added: <b>{added_count}</b>\n"
        f"📊 Total Available: <b>{total_stock}</b>\n\n"
        "Head to the <b>🛒 BUY</b> menu to get yours now!"
    )
    
    all_ids = get_all_user_ids()
    for uid in all_ids:
        try:
            msg = bot.send_message(uid, msg_text, parse_mode="HTML")
            from database import schedule_message_cleanup
            schedule_message_cleanup(uid, msg.message_id, hours=24)
        except Exception:
            pass
        time.sleep(0.05)

def broadcast_new_stock(bot: telebot.TeleBot, product_name: str, added_count: int, product_id: str):
    if added_count > 0:
        threading.Thread(target=_run_broadcast_new_stock, args=(bot, product_name, added_count, product_id), daemon=True).start()


def register(bot: telebot.TeleBot):

    @bot.message_handler(func=lambda m: user_states.has(m.from_user.id))
    def handle_state_input(message: telebot.types.Message):
        user_id = message.from_user.id
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
        state = user_states.get(user_id)
        if not state:
            return

        action = state.get("action")
        text = message.text.strip() if message.text else ""
        html_text = getattr(message, 'html_text', message.text or "").strip()

        # ── PAYMENT: UTR number ──────────────────────────────────────
        if action == "awaiting_utr":
            _handle_payment_submission(bot, message, state, utr_number=text)
            return

        # ── PAYMENT: Binance Order ID ────────────────────────────────
        if action == "awaiting_binance_id":
            _handle_payment_submission(bot, message, state, binance_order_id=text)
            return

        # ── CREDIT PURCHASE: Enter Amount ────────────────────────────
        if action == "awaiting_credit_amount":
            _handle_credit_amount_input(bot, message, text)
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

        # ── ADMIN: Set numerical stock ───────────────────────────────
        if action == "admin_set_num_stock" and is_admin(user_id):
            _handle_admin_set_num_stock(bot, message, state, text)
            return

        # ── ADMIN: Bulk add stock ────────────────────────────────────
        if action == "admin_add_stock" and is_admin(user_id):
            _handle_add_stock(bot, message, state, text)
            return

        # ── ADMIN: Bulk add stock (multi-message mode) ───────────────
        if action == "admin_add_stock_multi" and is_admin(user_id):
            _handle_add_stock_multi(bot, message, state, text)
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
            _handle_broadcast(bot, message, html_text)
            return

        # ── ADMIN: Cancel Order ──────────────────────────────────────
        if action == "admin_cancel_order" and is_admin(user_id):
            _handle_admin_cancel_order(bot, message, text)
            return

        # ── ADMIN: Edit payment setting ──────────────────────────────
        if action == "admin_edit_setting" and is_admin(user_id):
            _handle_edit_setting(bot, message, state, text)
            return

        # ── ADMIN: Edit delivery setting ──────────────────────────────
        if action.startswith("admin_set_del_") and is_admin(user_id):
            _handle_admin_delivery_settings(bot, message, state, text, html_text)
            return

        # ── USER: Buy multiple links ─────────────────────────────────
        if action == "buy_quantity":
            _handle_buy_quantity(bot, message, state, text)
            return

        # ── USER: Download Order ─────────────────────────────────────
        if action == "download_order":
            _handle_download_order(bot, message, state, text)
            return

        # ── ADMIN: Edit Product ──────────────────────────────────────
        if action == "admin_edit_product" and is_admin(user_id):
            _handle_admin_edit_product(bot, message, state, text, html_text)
            return

        # ── ADMIN: Send Gift Code Privately ──────────────────────────
        if action == "admin_gift_send_private" and is_admin(user_id):
            _handle_gift_send_private(bot, message, state, text)
            return

        # ── ADMIN: Search ────────────────────────────────────────────
        if action == "admin_search" and is_admin(user_id):
            _handle_admin_search(bot, message, state, text)
            return

        # ── ADMIN: Send Direct Message ───────────────────────────────
        if action == "admin_send_msg" and is_admin(user_id):
            _handle_admin_send_msg(bot, message, state, html_text)
            return

        # ── ADMIN: UI Settings (Text / Emoji) ────────────────────────
        if action in ("admin_ui_set_text", "admin_ui_set_emoji") and is_admin(user_id):
            _handle_admin_ui_input(bot, message, state, text)
            return

    # ── Document handler for CSV stock uploads ───────────────────────
    @bot.message_handler(
        content_types=["document"],
        func=lambda m: user_states.has(m.from_user.id)
            and user_states.get(m.from_user.id, {}).get("action") in ("admin_add_stock", "admin_add_stock_multi")
            and is_admin(m.from_user.id),
    )
    def handle_stock_csv_upload(message: telebot.types.Message):
        """Handle CSV/TXT file uploads for bulk stock import."""
        user_id = message.from_user.id
        state = user_states.get(user_id)
        if not state:
            return

        doc = message.document
        file_name = doc.file_name or ""
        if not file_name.lower().endswith((".csv", ".txt")):
            bot.send_message(
                user_id,
                "❌ Please upload a <b>.csv</b> or <b>.txt</b> file.\n"
                "The file should contain one link per line (or one link per row in CSV).",
                parse_mode="HTML",
            )
            return

        # Download the file
        try:
            file_info = bot.get_file(doc.file_id)
            downloaded = bot.download_file(file_info.file_path)
            file_content = downloaded.decode("utf-8", errors="ignore")
        except Exception as exc:
            bot.send_message(user_id, f"❌ Failed to download file: {exc}")
            return

        # Parse links from file
        from utils.helpers import extract_all_links, validate_link

        all_links = []
        if file_name.lower().endswith(".csv"):
            # Parse CSV — links can be in any column
            reader = csv.reader(io.StringIO(file_content))
            for row in reader:
                for cell in row:
                    cell = cell.strip()
                    if cell:
                        found = extract_all_links(cell)
                        all_links.extend(found)
        else:
            # Plain text file — one link per line
            all_links = extract_all_links(file_content)

        if not all_links:
            bot.send_message(
                user_id,
                "❌ No valid items found in the file.",
            )
            return

        # Validate, deduplicate within the file, then add
        product_id = state["product_id"]
        product_name = state["product_name"]

        valid_links = []
        rejected = []
        seen = set()
        for url in all_links:
            if validate_link(url):
                if url not in seen:
                    valid_links.append(url)
                    seen.add(url)
            else:
                rejected.append(url)

        added, duplicates = 0, 0
        if valid_links:
            added, duplicates = add_stock_items(product_id, valid_links)
            
        broadcast_new_stock(bot, product_name, added, product_id)

        user_states.clear(user_id)
        logger.info(
            "CSV stock import: product=%s valid=%s rejected=%s duplicates=%s",
            product_name, added, len(rejected), duplicates,
        )

        lines = [f"📦 <b>CSV Stock Import — {product_name}</b>\n"]
        lines.append(f"📄 File: <code>{file_name}</code>")
        lines.append(f"✅ New links added: <b>{added}</b>")
        if duplicates:
            lines.append(f"🔄 Duplicates skipped: <b>{duplicates}</b>")
        lines.append(f"❌ Rejected (invalid format): <b>{len(rejected)}</b>")

        if rejected:
            lines.append("\n<b>Rejected links:</b>")
            for r in rejected[:10]:
                truncated = r[:60] + "…" if len(r) > 60 else r
                lines.append(f"• <code>{truncated}</code>")
            if len(rejected) > 10:
                lines.append(f"  … and {len(rejected) - 10} more")

        bot.send_message(
            user_id,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=admin_panel_kb(),
        )


    # ── Photo handler for QR code uploads ────────────────────────────
    @bot.message_handler(
        content_types=["photo"],
        func=lambda m: user_states.has(m.from_user.id)
            and (user_states.get(m.from_user.id) or {}).get("action") == "awaiting_qr_upload",
    )
    def handle_qr_photo_upload(message: telebot.types.Message):
        """Handle QR code image upload from user."""
        user_id = message.from_user.id
        state = user_states.get(user_id)
        if not state:
            return

        qr_order_id = state.get("qr_order_id")
        if not qr_order_id:
            bot.send_message(user_id, "❌ Invalid state. Please try again.")
            user_states.clear(user_id)
            return

        from database import get_qr_order, update_qr_order_status, check_duplicate_qr
        from keyboards.inline import admin_qr_review_kb, back_to_menu_kb

        qr_order = get_qr_order(qr_order_id)
        if not qr_order:
            bot.send_message(user_id, "❌ Order not found.", reply_markup=back_to_menu_kb())
            user_states.clear(user_id)
            return

        # Get the highest resolution photo
        photo = message.photo[-1]
        file_id = photo.file_id
        file_unique_id = photo.file_unique_id

        # Check for duplicate QR
        if check_duplicate_qr(user_id, file_unique_id):
            bot.send_message(
                user_id,
                "❌ <b>Duplicate QR Code</b>\n\n"
                "This QR code has already been uploaded. "
                "Please upload a <b>fresh new QR code</b>.",
                parse_mode="HTML",
            )
            return  # Keep state so they can upload a different QR

        # Update QR order with file info
        update_qr_order_status(
            qr_order_id,
            status="qr_uploaded",
            qr_file_id=file_id,
            qr_file_unique_id=file_unique_id,
        )
        user_states.clear(user_id)

        # Send success message to user
        bot.send_message(
            user_id,
            "✅ <b>QR code uploaded successfully.</b>\n\n"
            "Please wait, your order will be completed in less than a minute.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )

        # Forward QR image to admin with review buttons
        from config import ADMIN_ID
        from utils.helpers import format_datetime
        admin_text = (
            "📲 <b>New QR Upload</b>\n\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"👤 Username: @{message.from_user.username or 'N/A'}\n"
            f"📦 Product: <b>{qr_order.get('product_name', 'N/A')}</b>\n"
            f"💎 Credits Used: <b>{qr_order.get('credits_used', 0)}</b>\n"
            f"📅 {format_datetime(qr_order.get('created_at'))}"
        )
        try:
            bot.send_photo(
                ADMIN_ID,
                photo=file_id,
                caption=admin_text,
                parse_mode="HTML",
                reply_markup=admin_qr_review_kb(qr_order_id),
            )
        except Exception as exc:
            logger.error("Failed to send QR to admin: %s", exc)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  CREDIT AMOUNT submission                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_credit_amount_input(bot: telebot.TeleBot, message: telebot.types.Message, text: str):
    user_id = message.from_user.id
    try:
        credits_qty = int(text)
    except ValueError:
        bot.send_message(user_id, "❌ Please enter a valid number.")
        return

    if credits_qty < 2:
        bot.send_message(user_id, "❌ Minimum purchase is 2 credits.")
        return

    # Calculate prices based on 2 credits = ₹106 / $1
    inr_price = credits_qty * 53
    usdt_price = credits_qty * 0.5

    user_states.clear(user_id)
    
    from keyboards.inline import payment_method_kb, cancel_payment_kb
    bot.send_message(
        user_id,
        f"💳 <b>Select Payment Method</b>\n\n"
        f"You are purchasing <b>{credits_qty}</b> credits.\n"
        f"Price: <b>${usdt_price}</b> (or <b>₹{inr_price}</b>)\n\n"
        "Please select your preferred payment method below:",
        parse_mode="HTML",
        reply_markup=payment_method_kb(credits_qty),
    )


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
        html_desc = getattr(message, 'html_text', message.text)
        if not html_desc:
            html_desc = message.text
        user_states.update(user_id, step="credit_cost", product_desc=html_desc.strip() if html_desc else "")
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

        user_states.update(user_id, step="stock_type", product_cost=cost)
        from keyboards.inline import admin_stock_type_kb
        bot.send_message(
            user_id,
            "Step 4/5 — Select the <b>Stock Type</b>:",
            parse_mode="HTML",
            reply_markup=admin_stock_type_kb(),
        )

    elif step == "numerical_stock":
        try:
            initial_stock = int(text)
            if initial_stock < 0:
                raise ValueError
        except ValueError:
            bot.send_message(user_id, "❌ Please enter a valid non-negative integer.")
            return

        product_id = create_product(
            name=state["product_name"],
            description=state["product_desc"],
            credit_cost=state["product_cost"],
            is_numerical=True,
            numerical_stock=initial_stock,
        )
        user_states.clear(user_id)
        logger.info("Product created (Numerical): %s (id=%s)", state["product_name"], product_id)
        bot.send_message(
            user_id,
            f"✅ <b>Product Created!</b>\n\n"
            f"Name: <b>{state['product_name']}</b>\n"
            f"Cost: {state['product_cost']} credits\n"
            f"Type: Numerical Service\n"
            f"Initial Stock: {initial_stock}\n"
            f"ID: <code>{product_id}</code>",
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
    html_text: str,
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
        html_desc = html_text
        if not html_desc:
            html_desc = text
        update_product(pid, {"$set": {"description": html_desc.strip() if html_desc else ""}})
        field_str = "Description"
    elif field == "delmsg":
        html_desc = html_text
        if not html_desc:
            html_desc = text
        update_product(pid, {"$set": {"delivery_message": html_desc.strip() if html_desc else ""}})
        field_str = "Delivery Message"
    elif field == "expdays":
        try:
            val = int(text)
            if val < 0:
                raise ValueError
        except ValueError:
            bot.send_message(user_id, "❌ Please enter a valid non-negative integer for expiration days.")
            return
        update_product(pid, {"$set": {"expiration_days": val}})
        field_str = "Expiration Days"
        
    user_states.clear(user_id)
    
    bot.send_message(
        user_id,
        f"✅ Product {field_str} updated successfully!",
        reply_markup=admin_panel_kb()
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Set numerical stock                                         ║
# ╚══════════════════════════════════════════════════════════════════════╝
def _handle_admin_set_num_stock(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    from database import update_product
    from keyboards.inline import admin_panel_kb
    
    user_id = message.from_user.id
    pid = state["product_id"]
    
    try:
        val = int(text)
        if val < 0:
            raise ValueError
    except ValueError:
        bot.send_message(user_id, "❌ Please enter a valid non-negative integer.")
        return
        
    update_product(pid, {"$set": {"numerical_stock": val}})
    user_states.clear(user_id)
    
    bot.send_message(
        user_id,
        f"✅ Numerical stock updated to <b>{val}</b> successfully!",
        parse_mode="HTML",
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
    from utils.helpers import extract_all_links, validate_link

    user_id = message.from_user.id
    product_id = state["product_id"]
    product_name = state["product_name"]

    # Check if user wants to switch to multi-message mode
    if text.lower() == "multi":
        user_states.set(user_id, {
            "action": "admin_add_stock_multi",
            "product_id": product_id,
            "product_name": product_name,
            "accumulated_links": [],
        })
        bot.send_message(
            user_id,
            f"📦 <b>Multi-Message Stock Mode — {product_name}</b>\n\n"
            "Send your links in <b>multiple messages</b>.\n"
            "When you're done, type <b>done</b> to finish.\n\n"
            "💡 This mode bypasses Telegram's message limit.\n"
            "You can also upload a <b>.csv</b> or <b>.txt</b> file.",
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        return

    # Extract all possible links from the raw text
    extracted_urls = extract_all_links(text)
    
    if not extracted_urls:
        bot.send_message(user_id, "❌ No items found in the text.")
        return

    # Validate each link against LinkedIn referral format
    valid_links = []
    rejected = []
    
    for url in extracted_urls:
        if validate_link(url):
            # deduplicate within the batch
            if url not in valid_links:
                valid_links.append(url)
        else:
            rejected.append(url)

    # Add valid links to stock (returns added count and duplicate count)
    added, duplicates = 0, 0
    if valid_links:
        added, duplicates = add_stock_items(product_id, valid_links)
        
    broadcast_new_stock(bot, product_name, added, product_id)

    user_states.clear(user_id)
    logger.info(
        "Stock import: product=%s valid=%s rejected=%s duplicates=%s",
        product_name, added, len(rejected), duplicates,
    )

    # Build response
    lines = [f"📦 <b>Stock Import — {product_name}</b>\n"]
    lines.append(f"✅ New links added: <b>{added}</b>")
    if duplicates:
        lines.append(f"🔄 Duplicates skipped: <b>{duplicates}</b>")
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
            "\n⚠️ No items were added."
        )

    bot.send_message(
        user_id,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )


def _handle_add_stock_multi(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    """Handle multi-message stock adding. Accumulates links across messages until 'done'."""
    from utils.helpers import extract_all_links, validate_link

    user_id = message.from_user.id
    product_id = state["product_id"]
    product_name = state["product_name"]
    accumulated = state.get("accumulated_links", [])

    if text.lower() == "done":
        # Process all accumulated links
        if not accumulated:
            bot.send_message(
                user_id,
                "❌ No links were collected. Stock import cancelled.",
                reply_markup=admin_panel_kb(),
            )
            user_states.clear(user_id)
            return

        valid_links = []
        rejected = []
        for url in accumulated:
            if validate_link(url):
                if url not in valid_links:
                    valid_links.append(url)
            else:
                rejected.append(url)

        added, duplicates = 0, 0
        if valid_links:
            added, duplicates = add_stock_items(product_id, valid_links)
            
        broadcast_new_stock(bot, product_name, added, product_id)

        user_states.clear(user_id)
        logger.info(
            "Multi-msg stock import: product=%s valid=%s rejected=%s duplicates=%s",
            product_name, added, len(rejected), duplicates,
        )

        lines = [f"📦 <b>Stock Import — {product_name}</b>\n"]
        lines.append(f"✅ New links added: <b>{added}</b>")
        if duplicates:
            lines.append(f"🔄 Duplicates skipped: <b>{duplicates}</b>")
        lines.append(f"❌ Rejected (invalid format): <b>{len(rejected)}</b>")

        if rejected:
            lines.append("\n<b>Rejected links:</b>")
            for r in rejected[:10]:
                truncated = r[:60] + "…" if len(r) > 60 else r
                lines.append(f"• <code>{truncated}</code>")
            if len(rejected) > 10:
                lines.append(f"  … and {len(rejected) - 10} more")

        bot.send_message(
            user_id,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=admin_panel_kb(),
        )
        return

    # Extract links from this message and accumulate
    new_links = extract_all_links(text)
    if not new_links:
        bot.send_message(
            user_id,
            "⚠️ No links found in that message. Try again or type <b>done</b> to finish.",
            parse_mode="HTML",
        )
        return

    accumulated.extend(new_links)
    user_states.update(user_id, accumulated_links=accumulated)

    bot.send_message(
        user_id,
        f"✅ Collected <b>{len(new_links)}</b> link(s) from this message.\n"
        f"📊 Total so far: <b>{len(accumulated)}</b> link(s).\n\n"
        "Send more links or type <b>done</b> to import them all.",
        parse_mode="HTML",
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
        f"⭐ Points: {user.get('referral_points', 0)}\n"
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
        msg = bot.send_message(
            user_id,
            "🎉 <b>Success!</b>\n\nYour gift code has been redeemed and points have been added to your account.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb()
        )
        from database import schedule_message_cleanup
        schedule_message_cleanup(user_id, msg.message_id, hours=24)
        from utils.helpers import announce_event
        announce_event(bot, "GIFT CODE REDEEMED", user_id, 0, "Redeemed")
    else:
        msg = bot.send_message(
            user_id,
            f"❌ <b>Error:</b> {result}",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb()
        )
        from database import schedule_message_cleanup
        schedule_message_cleanup(user_id, msg.message_id, hours=24)
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
        if hours > 0:
            expiry_str = f"{hours} hrs {minutes} mins"
        else:
            expiry_str = f"{minutes} mins"
    else:
        expiry_str = "Never"
    
    from keyboards.inline import gift_code_actions_kb
    
    bot.send_message(
        message.chat.id,
        f"🎉 <b>YOUR EXCLUSIVE GIFT CODE IS READY!</b> 🎁\n\n"
        f"🎟 <code>{code}</code>\n"
        f"📋 Tap to Copy\n\n"
        f"🏆 Points: <b>{state['points']}</b>\n"
        f"⏳ Expires in {expiry_str}\n"
        f"⚡ Redeem fast  !!!  before it disappears 🚀",
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
# ║  ADMIN: Cancel Order                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_admin_cancel_order(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    text: str,
):
    user_id = message.from_user.id
    order_id = text.strip()
    
    from bson.errors import InvalidId
    from bson import ObjectId
    from database import orders_col, qr_orders_col, stock_col
    
    try:
        oid = ObjectId(order_id)
    except InvalidId:
        bot.send_message(user_id, "❌ Invalid Order ID format.", reply_markup=admin_panel_kb())
        user_states.clear(user_id)
        return
        
    order = orders_col.find_one({"_id": oid})
    if not order:
        qr_order = qr_orders_col.find_one({"_id": oid})
        if qr_order and qr_order.get("order_id"):
            try:
                order = orders_col.find_one({"_id": ObjectId(qr_order["order_id"])})
            except:
                pass
                
    if not order:
        bot.send_message(user_id, "❌ Order not found.", reply_markup=admin_panel_kb())
        user_states.clear(user_id)
        return
        
    buyer_id = order.get("user_id")
    credits_used = order.get("credits_used", 0)
    
    if credits_used > 0 and buyer_id:
        from database import add_credits
        add_credits(buyer_id, credits_used)
        
    qr_order = qr_orders_col.find_one({"order_id": str(order["_id"])})
    if qr_order:
        from database import refund_stock
        refund_stock(
            product_id=qr_order.get("product_id"),
            qty=qr_order.get("qty", 1),
            is_numerical=qr_order.get("is_numerical", False),
            items=qr_order.get("items", [])
        )
        qr_orders_col.update_one({"_id": qr_order["_id"]}, {"$set": {"status": "cancelled"}})
    else:
        items = order.get("items", [])
        if items:
            stock_col.update_many(
                {"content": {"$in": items}},
                {"$set": {"is_sold": False, "assigned_to": None, "assigned_at": None}}
            )
            
    orders_col.delete_one({"_id": order["_id"]})
    
    bot.send_message(
        user_id,
        f"✅ <b>Order Cancelled</b>\n\n"
        f"Order ID: <code>{order_id}</code>\n"
        f"Refunded: <b>{credits_used}</b> credits to user {buyer_id}.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    user_states.clear(user_id)
    
    try:
        bot.send_message(
            buyer_id,
            f"❌ <b>Your Order has been Cancelled</b>\n\n"
            f"Your order for <b>{order.get('product_name')}</b> was cancelled by an admin.\n"
            f"<b>{credits_used}</b> credits have been refunded to your account.",
            parse_mode="HTML"
        )
    except:
        pass


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
            msg = bot.send_message(uid, text, parse_mode="HTML")
            from database import schedule_message_cleanup
            schedule_message_cleanup(uid, msg.message_id, hours=24)
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
# ║  ADMIN: Edit delivery setting                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_admin_delivery_settings(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
    html_text: str,
):
    from database import get_delivery_settings, update_delivery_settings
    from keyboards.inline import admin_delivery_settings_kb

    user_id = message.from_user.id
    action = state["action"]

    if not text:
        bot.send_message(user_id, "❌ Value cannot be empty. Try again.")
        return

    update_data = {}
    if action == "admin_set_del_global_msg":
        val = html_text if html_text else text
        update_data["global_message"] = val.strip()
        field_name = "Global Delivery Message"
    elif action == "admin_set_del_exp_days":
        try:
            val = int(text)
            if val < 0:
                raise ValueError
        except ValueError:
            bot.send_message(user_id, "❌ Please enter a valid non-negative integer.")
            return
        update_data["expiration_days"] = val
        field_name = "Expiration Days"
    elif action == "admin_set_del_exp_warn":
        val = html_text if html_text else text
        update_data["expiration_warning"] = val.strip()
        field_name = "Expiration Warning Text"

    update_delivery_settings(update_data)
    user_states.clear(user_id)

    del_settings = get_delivery_settings()
    text_msg = (
        f"✅ <b>{field_name} Updated!</b>\n\n"
        "📦 <b>Delivery Settings</b>\n\n"
        f"<b>Global Delivery Message:</b>\n<code>{del_settings['global_message']}</code>\n\n"
        f"<b>Expiration Days (for new stock):</b> <code>{del_settings['expiration_days']}</code>\n\n"
        f"<b>Expiration Warning Text:</b>\n<code>{del_settings['expiration_warning']}</code>\n\n"
        "Tap a button below to edit:"
    )
    bot.send_message(
        user_id,
        text_msg,
        parse_mode="HTML",
        reply_markup=admin_delivery_settings_kb()
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

    # Handle referral config keys separately (need integer validation + dedicated storage)
    if setting_key in ("referral_points_per_credit", "referral_max_free_credits"):
        try:
            int_val = int(text)
            if int_val <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(user_id, "❌ Please enter a valid positive integer.")
            return

        from database import set_referral_config, get_referral_config
        from keyboards.inline import referral_settings_kb

        if setting_key == "referral_points_per_credit":
            set_referral_config(points_per_credit=int_val)
        else:
            set_referral_config(max_free_credits=int_val)

        user_states.clear(user_id)
        logger.info("Referral config updated: %s = %s", setting_key, int_val)

        ref_config = get_referral_config()
        bot.send_message(
            user_id,
            f"✅ <b>{setting_label}</b> updated!\n\n"
            f"New value: <code>{int_val}</code>",
            parse_mode="HTML",
            reply_markup=referral_settings_kb(ref_config),
        )
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
    
    expiry_str = "Never"
    if code_doc.get("expires_at"):
        from datetime import datetime, timezone
        exp = code_doc["expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        diff = exp - datetime.now(timezone.utc)
        if diff.total_seconds() > 0:
            mins = int(diff.total_seconds() / 60)
            if mins >= 60:
                expiry_str = f"{mins//60} hrs {mins%60} mins"
            else:
                expiry_str = f"{mins} mins"
        else:
            expiry_str = "Expired"

    msg_text = (
        "🎉 <b>YOUR EXCLUSIVE GIFT CODE IS READY!</b> 🎁\n\n"
        f"🎟 <code>{code}</code>\n"
        f"📋 Tap to Copy\n\n"
        f"🏆 Points: <b>{code_doc['points']}</b>\n"
        f"⏳ Expires in {expiry_str}\n"
        f"⚡ Redeem fast  !!!  before it disappears 🚀"
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

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Search                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_admin_search(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    from database import search_database
    from keyboards.inline import admin_back_kb
    from utils.helpers import format_datetime
    
    user_id = message.from_user.id
    query = text.strip()
    result = search_database(query)
    
    if result["type"] == "none":
        bot.send_message(
            user_id, 
            f"❌ No matching Link or Gift Code found for: <code>{query}</code>",
            parse_mode="HTML",
            reply_markup=admin_back_kb()
        )
    elif result["type"] == "stock":
        item = result["data"]
        from database import get_product
        product = get_product(str(item["product_id"]))
        prod_name = product["name"] if product else "Unknown Product"
        
        status = "🔴 SOLD" if item["is_sold"] else "🟢 AVAILABLE"
        
        msg = (
            f"🔍 <b>Search Result (Stock Link)</b>\n\n"
            f"🔗 <b>Link:</b> <code>{item['content']}</code>\n"
            f"📦 <b>Product:</b> {prod_name}\n"
            f"📊 <b>Status:</b> {status}\n\n"
            f"📅 <b>Added At:</b> {format_datetime(item['added_at'])}\n"
        )
        if item.get("expires_at"):
            msg += f"⏳ <b>Expires At:</b> {format_datetime(item['expires_at'])}\n"
            
        if item["is_sold"]:
            msg += (
                f"\n👤 <b>Sold To (User ID):</b> <code>{item['sold_to']}</code>\n"
                f"🕒 <b>Sold At:</b> {format_datetime(item['sold_at'])}\n"
            )
            
        bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=admin_back_kb())
        
    elif result["type"] == "gift_code":
        item = result["data"]
        
        msg = (
            f"🔍 <b>Search Result (Gift Code)</b>\n\n"
            f"🎟 <b>Code:</b> <code>{item['code']}</code>\n"
            f"🏆 <b>Points:</b> {item['points']}\n"
            f"👥 <b>Uses:</b> {item.get('current_uses', 0)} / {item['max_uses']}\n\n"
            f"👤 <b>Created By (User ID):</b> <code>{item['created_by']}</code>\n"
            f"📅 <b>Created At:</b> {format_datetime(item['created_at'])}\n"
        )
        if item.get("expires_at"):
            msg += f"⏳ <b>Expires At:</b> {format_datetime(item['expires_at'])}\n"
            
        if item.get("redeemed_by"):
            msg += f"\n👥 <b>Redeemed By:</b> {len(item['redeemed_by'])} users"
            
        bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=admin_back_kb())

    user_states.clear(user_id)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: Send Direct Message                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_admin_send_msg(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    from keyboards.inline import admin_back_kb
    
    user_id = message.from_user.id
    target_id = state["target_id"]
    user_states.clear(user_id)
    
    msg_text = f"📨 <b>Message from owner:</b>\n\n{text}"
    
    try:
        msg = bot.send_message(target_id, msg_text, parse_mode="HTML")
        from database import schedule_message_cleanup
        schedule_message_cleanup(target_id, msg.message_id, hours=24)
        bot.send_message(
            user_id,
            f"✅ Message sent to user <code>{target_id}</code>.",
            parse_mode="HTML",
            reply_markup=admin_back_kb()
        )
    except Exception as exc:
        bot.send_message(
            user_id,
            f"❌ Failed to send message to user <code>{target_id}</code>.\nError: {exc}",
            parse_mode="HTML",
            reply_markup=admin_back_kb()
        )

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN: UI Settings Input                                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _handle_admin_ui_input(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    from database import update_ui_setting
    from utils.helpers import clear_ui_cache
    from keyboards.inline import admin_ui_edit_kb
    
    user_id = message.from_user.id
    button_key = state["button_key"]
    action = state["action"]
    user_states.clear(user_id)
    
    if action == "admin_ui_set_text":
        update_ui_setting(button_key, "text", text)
        msg_text = f"✅ Text for <code>{button_key}</code> updated to: {text}"
    else:
        update_ui_setting(button_key, "emoji_id", text)
        msg_text = f"✅ Custom Emoji for <code>{button_key}</code> updated to ID: <code>{text}</code>"
        
    clear_ui_cache()
    
    bot.send_message(
        user_id,
        msg_text,
        parse_mode="HTML",
        reply_markup=admin_ui_edit_kb(button_key)
    )

def _handle_download_order(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    state: dict,
    text: str,
):
    user_id = message.from_user.id
    order_id = text.strip()
    
    from database import orders_col
    from bson import ObjectId
    
    try:
        order = orders_col.find_one({"_id": ObjectId(order_id)})
    except Exception:
        order = None
        
    from keyboards.inline import back_to_menu_kb
    
    if not order:
        bot.send_message(user_id, "❌ <b>Order not found.</b>\nPlease check your Order ID and try again.", parse_mode="HTML", reply_markup=back_to_menu_kb())
        user_states.clear(user_id)
        return
        
    if order.get("user_id") != user_id:
        bot.send_message(user_id, "⛔ <b>Not authorized.</b>\nThis order belongs to someone else.", parse_mode="HTML", reply_markup=back_to_menu_kb())
        user_states.clear(user_id)
        return
        
    items = order.get("items", [])
    if not items:
        bot.send_message(user_id, "❌ No links found for this order.", reply_markup=back_to_menu_kb())
        user_states.clear(user_id)
        return
        
    import io
    file_content = f"Order: {order.get('product_name', 'Unknown')}\n\n"
    for item in items:
        file_content += f"Link: {item}\n\n"
        
    doc = io.BytesIO(file_content.encode('utf-8'))
    doc.name = f"Order_{order_id}_links.txt"
    
    bot.send_document(
        user_id, 
        document=doc, 
        caption=f"📦 Here are your links for <b>{order.get('product_name')}</b>",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb()
    )
    user_states.clear(user_id)
