"""
handlers/admin.py
─────────────────
Full admin panel: product CRUD, payment review, user management,
broadcast, statistics, and credit adjustments.
"""

import telebot
from config import ADMIN_ID, logger
from database import (
    get_all_products, get_product, update_product, delete_product, create_product,
    get_pending_payments, approve_payment, reject_payment,
    add_credits, remove_credits, get_user, search_user_by_id, get_all_user_ids,
    count_users, count_products, count_orders, count_payments, total_credits_sold,
    get_user_orders,
    get_available_stock_count, get_total_stock_count, add_stock_items, delete_product_stock,
    set_setting, ban_user, delete_user,
    is_maintenance_mode, set_maintenance_mode,
    is_referral_enabled, set_referral_enabled, get_referral_config, set_referral_config,
    is_credit_conversion_enabled, set_credit_conversion_enabled,
)
from keyboards.inline import (
    admin_panel_kb, admin_back_kb,
    admin_products_list_kb, admin_product_actions_kb,
    admin_payment_review_kb, payment_settings_kb, prices_settings_kb,
    referral_settings_kb,
)
from utils.helpers import is_admin, format_datetime, get_payment_settings, get_credit_packages
from utils.states import user_states


def _admin_only(call_or_msg) -> bool:
    """Return True if the sender is the admin."""
    uid = (
        call_or_msg.from_user.id
        if hasattr(call_or_msg, "from_user")
        else call_or_msg.chat.id
    )
    return is_admin(uid)


def register(bot: telebot.TeleBot):

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  /admin command                                                  ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.message_handler(commands=["admin"])
    def cmd_admin(message: telebot.types.Message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ You are not authorized.")
            return
        is_maint = is_maintenance_mode()
        is_ref = is_referral_enabled()
        bot.send_message(
            message.chat.id,
            "🔧 <b>Admin Panel</b>",
            parse_mode="HTML",
            reply_markup=admin_panel_kb(is_maint, is_ref),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "adm:panel")
    def cb_admin_panel(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
        user_states.clear(call.from_user.id)
        is_maint = is_maintenance_mode()
        is_ref = is_referral_enabled()
        bot.edit_message_text(
            "🔧 <b>Admin Panel</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_panel_kb(is_maint, is_ref),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  SEARCH LINK OR CODE                                             ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:search")
    def cb_admin_search(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔", show_alert=True)
            return
        user_states.set(call.from_user.id, {
            "action": "admin_search",
        })
        bot.edit_message_text(
            "🔍 <b>Search Database</b>\n\n"
            "Please paste the <b>LinkedIn Link</b> or <b>Gift Code</b> you want to search:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  ADD PRODUCT (multi-step form)                                   ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:add_product")
    def cb_add_product(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔", show_alert=True)
            return
        user_states.set(call.from_user.id, {
            "action": "admin_add_product",
            "step": "name",
        })
        bot.edit_message_text(
            "➕ <b>Add Product</b>\n\n"
            "Step 1/3 — Enter the <b>product name</b>:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  MAINTENANCE & GIFT CODES                                        ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:toggle_maintenance")
    def cb_toggle_maintenance(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
            
        current = is_maintenance_mode()
        set_maintenance_mode(not current)
        
        is_maint = not current
        is_ref = is_referral_enabled()
        bot.edit_message_text(
            "🔧 <b>Admin Panel</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_panel_kb(is_maint, is_ref),
        )
        status_text = "ON" if is_maint else "OFF"
        bot.answer_callback_query(call.id, f"Maintenance Mode: {status_text}", show_alert=True)

    # ── Referral Program Toggle ──────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "adm:toggle_referral")
    def cb_toggle_referral(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
            
        current = is_referral_enabled()
        set_referral_enabled(not current)
        
        is_ref = not current
        is_maint = is_maintenance_mode()
        bot.edit_message_text(
            "🔧 <b>Admin Panel</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_panel_kb(is_maint, is_ref),
        )
        status_text = "ON" if is_ref else "OFF"
        bot.answer_callback_query(call.id, f"Referral Program: {status_text}", show_alert=True)

    # ── Referral Settings ────────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "adm:referral_settings")
    def cb_referral_settings(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
        
        ref_config = get_referral_config()
        is_ref = is_referral_enabled()
        is_conv = is_credit_conversion_enabled()
        status = "🟢 Enabled" if is_ref else "🔴 Disabled"
        conv_status = "🟢 ON" if is_conv else "🔴 OFF"
        
        text = (
            "⚙️ <b>Referral Settings</b>\n\n"
            f"<b>Referral Program:</b> {status}\n"
            f"<b>Credit Conversion:</b> {conv_status}\n"
            f"🔢 <b>Points per Credit:</b> {ref_config['points_per_credit']}\n"
            f"🎯 <b>Max Free Credits:</b> {ref_config['max_free_credits']}\n\n"
            "Tap a button below to edit:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=referral_settings_kb(ref_config, is_conv),
        )
        bot.answer_callback_query(call.id)

    # ── Credit Conversion Toggle ─────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "adm:toggle_conversion")
    def cb_toggle_conversion(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
            
        current = is_credit_conversion_enabled()
        set_credit_conversion_enabled(not current)
        
        # Re-render referral settings page
        ref_config = get_referral_config()
        is_ref = is_referral_enabled()
        is_conv = not current
        status = "🟢 Enabled" if is_ref else "🔴 Disabled"
        conv_status = "🟢 ON" if is_conv else "🔴 OFF"
        
        text = (
            "⚙️ <b>Referral Settings</b>\n\n"
            f"<b>Referral Program:</b> {status}\n"
            f"<b>Credit Conversion:</b> {conv_status}\n"
            f"🔢 <b>Points per Credit:</b> {ref_config['points_per_credit']}\n"
            f"🎯 <b>Max Free Credits:</b> {ref_config['max_free_credits']}\n\n"
            "Tap a button below to edit:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=referral_settings_kb(ref_config, is_conv),
        )
        status_text = "ON" if is_conv else "OFF"
        bot.answer_callback_query(call.id, f"Credit Conversion: {status_text}", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "adm:gen_gift_code")
    def cb_gen_gift_code(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
            
        user_states.set(call.from_user.id, {"action": "awaiting_gift_gen_credits"})
        bot.send_message(
            call.message.chat.id,
            "🎁 <b>Generate Gift Code</b>\n\nHow many <b>points</b> should this code give to the user?\n<i>(Enter a number, e.g., 5)</i>",
            parse_mode="HTML",
            reply_markup=admin_back_kb()
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admgift:broadcast:"))
    def cb_gift_broadcast(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
        
        code = call.data.split(":", 2)[2]
        from database import get_gift_code
        code_doc = get_gift_code(code)
        if not code_doc:
            bot.answer_callback_query(call.id, "❌ Code not found.", show_alert=True)
            return
        
        all_ids = get_all_user_ids()
        success, failed = 0, 0
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
        for uid in all_ids:
            try:
                bot.send_message(uid, msg_text, parse_mode="HTML")
                success += 1
            except Exception:
                failed += 1
        
        bot.send_message(
            call.message.chat.id,
            f"📢 <b>Gift Code Broadcast Complete</b>\n\n"
            f"🎟 Code: <code>{code}</code>\n"
            f"✅ Sent: {success}\n❌ Failed: {failed}",
            parse_mode="HTML",
            reply_markup=admin_back_kb()
        )
        bot.answer_callback_query(call.id, f"✅ Sent to {success} users")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admgift:private:"))
    def cb_gift_private(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
        
        code = call.data.split(":", 2)[2]
        user_states.set(call.from_user.id, {
            "action": "admin_gift_send_private",
            "gift_code": code,
        })
        bot.send_message(
            call.message.chat.id,
            "📨 <b>Send Gift Code Privately</b>\n\n"
            f"Code: <code>{code}</code>\n\n"
            "Enter the <b>Telegram User ID</b> to send this code to:",
            parse_mode="HTML",
            reply_markup=admin_back_kb()
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  MANAGE PRODUCTS                                                 ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:manage_products")
    def cb_manage_products(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔", show_alert=True)
            return
        products = get_all_products()
        if not products:
            bot.edit_message_text(
                "📋 No products found.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=admin_back_kb(),
            )
            bot.answer_callback_query(call.id)
            return

        bot.edit_message_text(
            "📋 <b>Manage Products</b>\n\nSelect a product:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_products_list_kb(products),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:view:"))
    def cb_admin_view_product(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        product = get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return

        available = get_available_stock_count(pid)
        total = get_total_stock_count(pid)
        sold = total - available

        is_num = product.get("is_numerical", False)
        
        if is_num:
            num_stock = product.get("numerical_stock", 0)
            stock_line = f"🔢 Stock: <b>{num_stock}</b> (Numerical Service)"
        else:
            stock_line = f"📦 Stock: <b>{available}</b> available / {sold} sold / {total} total"

        text = (
            f"📦 <b>{product['name']}</b>\n\n"
            f"{product['description']}\n\n"
            f"💎 Cost: {product['credit_cost']} credits\n"
            f"📌 Active: {'Yes' if product['active'] else 'No'}\n"
            f"{stock_line}\n"
            f"📅 Created: {format_datetime(product.get('created_at'))}"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_product_actions_kb(pid, product["active"], is_num),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:toggle:"))
    def cb_toggle_product(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        product = get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        new_active = not product["active"]
        update_product(pid, {"$set": {"active": new_active}})
        status = "enabled" if new_active else "disabled"
        bot.answer_callback_query(call.id, f"Product {status}.", show_alert=True)
        # Refresh the view
        cb_admin_view_product(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:delete:"))
    def cb_delete_product(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        delete_product_stock(pid)  # remove all stock items too
        delete_product(pid)
        bot.answer_callback_query(call.id, "🗑 Product & stock deleted.", show_alert=True)
        # Return to product list
        cb_manage_products(call)


    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:toggle_numerical:"))
    def cb_admin_toggle_numerical(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        product = get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return
            
        new_val = not product.get("is_numerical", False)
        update_product(pid, {"$set": {"is_numerical": new_val}})
        
        bot.answer_callback_query(call.id, f"Switched to {'Numerical' if new_val else 'Links'}")
        # Refresh the view
        call.data = f"admprod:view:{pid}"
        cb_admin_view_product(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:set_num_stock:"))
    def cb_admin_set_num_stock(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        product = get_product(pid)
        if not product:
            return
            
        user_states.set(call.from_user.id, {
            "action": "admin_set_num_stock",
            "product_id": pid,
        })
        bot.send_message(
            call.from_user.id,
            f"✏️ <b>Set Numerical Stock for:</b> {product['name']}\n\n"
            "Please enter the new integer value for the available stock:",
            parse_mode="HTML",
            reply_markup=admin_back_kb()
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:stock_type:"))
    def cb_admin_stock_type(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        
        stock_type = call.data.split(":")[2]  # 'links' or 'numerical'
        state = user_states.get(call.from_user.id)
        if not state or state.get("step") != "stock_type":
            bot.answer_callback_query(call.id, "Invalid state. Please start over.", show_alert=True)
            return

        if stock_type == "links":
            # Create product right away
            product_id = create_product(
                name=state["product_name"],
                description=state["product_desc"],
                credit_cost=state["product_cost"],
                is_numerical=False,
                numerical_stock=0,
            )
            user_states.clear(call.from_user.id)
            logger.info("Product created (Links): %s (id=%s)", state["product_name"], product_id)
            bot.edit_message_text(
                f"✅ <b>Product Created!</b>\n\n"
                f"Name: <b>{state['product_name']}</b>\n"
                f"Cost: {state['product_cost']} credits\n"
                f"Type: Links / Coupons\n"
                f"ID: <code>{product_id}</code>\n\n"
                "📦 Now go to <b>Manage Products</b> → select this product → "
                "<b>Add Stock</b> to bulk-import your links.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_panel_kb(),
            )
        else:
            # Numerical product -> ask for initial stock
            user_states.update(call.from_user.id, step="numerical_stock", is_numerical=True)
            bot.edit_message_text(
                "Step 5/5 — Enter the initial <b>numerical stock</b> limit (integer):",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_back_kb(),
            )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:edit_"))
    def cb_edit_product_field(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        # format: admprod:edit_name:<pid>
        parts = call.data.split(":")
        field_type = parts[1].split("_")[1] # "name", "desc", or "cost"
        pid = parts[2]
        
        product = get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return
            
        field_name_map = {
            "name": "Name",
            "desc": "Description",
            "cost": "Cost (Credits)"
        }
        
        user_states.set(call.from_user.id, {
            "action": "admin_edit_product",
            "product_id": pid,
            "field": field_type
        })
        
        current_val = product.get('name' if field_type == 'name' else 'description' if field_type == 'desc' else 'credit_cost')
        
        bot.edit_message_text(
            f"✏️ <b>Edit {field_name_map[field_type]}</b>\n\n"
            f"Current {field_name_map[field_type]}:\n"
            f"<code>{current_val}</code>\n\n"
            "Please send the new value below:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ── Bulk add stock ───────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:addstock:"))
    def cb_add_stock(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        product = get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return
        user_states.set(call.from_user.id, {
            "action": "admin_add_stock",
            "product_id": pid,
            "product_name": product["name"],
        })
        bot.edit_message_text(
            f"📦 <b>Add Stock — {product['name']}</b>\n\n"
            "<b>Option 1:</b> Paste links below, <b>one per line</b>.\n"
            "You can paste many links at once.\n\n"
            "<b>Option 2:</b> Type <b>multi</b> to send links\n"
            "across multiple messages (bypasses Telegram's\n"
            "4096-char limit).\n\n"
            "<b>Option 3:</b> Upload a <b>.csv</b> or <b>.txt</b> file\n"
            "containing your links.\n\n"
            "🔄 Duplicate links are automatically skipped.\n\n"
            "Example:\n"
            "<code>https://linkedin.com/premium/link1\n"
            "https://linkedin.com/premium/link2\n"
            "https://linkedin.com/premium/link3</code>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  PENDING PAYMENTS                                                ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:pending_payments")
    def cb_pending_payments(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        payments = get_pending_payments()
        if not payments:
            bot.edit_message_text(
                "✅ No pending payments.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=admin_back_kb(),
            )
            bot.answer_callback_query(call.id)
            return

        # Show each pending payment as a separate message
        bot.edit_message_text(
            f"⏳ <b>{len(payments)} Pending Payment(s)</b>\n\n"
            "Sending details below…",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        for p in payments:
            txn = p.get("utr_number") or p.get("binance_order_id") or "N/A"
            txn_label = "UTR Number" if p["method"] == "UPI" else "Binance Order ID"
            text = (
                "💳 <b>Payment Request</b>\n\n"
                f"👤 User ID: <code>{p['user_id']}</code>\n"
                f"👤 Username: @{p.get('username', 'N/A')}\n"
                f"💰 Method: {p['method']}\n"
                f"💵 Amount: {p['amount']}\n"
                f"💎 Credits: {p['credits']}\n"
                f"🔢 {txn_label}: <code>{txn}</code>\n"
                f"📅 {format_datetime(p.get('created_at'))}"
            )
            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="HTML",
                reply_markup=admin_payment_review_kb(str(p["_id"])),
            )
        bot.answer_callback_query(call.id)

    # ── Approve / Reject ─────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admpay:approve:"))
    def cb_approve_payment(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        payment = approve_payment(pid)
        if not payment:
            bot.answer_callback_query(call.id, "Payment not found.", show_alert=True)
            return

        # Add credits to user
        add_credits(payment["user_id"], payment["credits"])
        logger.info(
            "Payment approved: user=%s credits=%s by admin",
            payment["user_id"], payment["credits"],
        )
        from database import get_user
        user = get_user(payment["user_id"])
        if user:
            from utils.helpers import announce_event
            announce_event(bot, "CREDIT ADDED (PURCHASE)", payment["user_id"], user["credits"], "Approved")

        # Update admin message
        bot.edit_message_text(
            call.message.text + "\n\n✅ <b>APPROVED</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
        )

        # Notify user
        try:
            bot.send_message(
                payment["user_id"],
                "✅ <b>Payment Approved!</b>\n\n"
                f"💎 <b>{payment['credits']} credit(s)</b> added successfully.\n"
                "Thank you! 🎉",
                parse_mode="HTML",
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "✅ Approved")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admpay:reject:"))
    def cb_reject_payment(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        payment = reject_payment(pid)
        if not payment:
            bot.answer_callback_query(call.id, "Payment not found.", show_alert=True)
            return

        logger.info("Payment rejected: user=%s", payment["user_id"])

        bot.edit_message_text(
            call.message.text + "\n\n❌ <b>REJECTED</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
        )

        try:
            bot.send_message(
                payment["user_id"],
                "❌ <b>Payment Rejected</b>\n\n"
                "Your payment was not approved.\n"
                "Please contact support if you believe this is a mistake.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "❌ Rejected")

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  ORDERS (admin view)                                             ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:orders")
    def cb_admin_orders(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        from database import orders_col
        recent = list(orders_col.find().sort("created_at", -1).limit(20))
        if not recent:
            bot.edit_message_text(
                "📦 No orders yet.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=admin_back_kb(),
            )
            bot.answer_callback_query(call.id)
            return

        lines = ["📦 <b>Recent Orders</b> (last 20)\n"]
        for o in recent:
            lines.append(
                f"• <b>{o['product_name']}</b> — "
                f"User <code>{o['user_id']}</code> — "
                f"{o['credits_used']} cr — "
                f"{format_datetime(o.get('created_at'))}"
            )
        bot.edit_message_text(
            "\n".join(lines),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  USERS (search by ID)                                            ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:users")
    def cb_admin_users(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        user_states.set(call.from_user.id, {
            "action": "admin_search_user",
        })
        bot.edit_message_text(
            "👥 <b>User Search</b>\n\n"
            "Enter the Telegram ID of the user:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admuser:"))
    def cb_admin_user_actions(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
            
        action, target_id_str = call.data.split(":")[1:3]
        target_id = int(target_id_str)
        
        user = search_user_by_id(target_id)
        if not user and action != "delete":
            bot.answer_callback_query(call.id, "User not found.", show_alert=True)
            return
            
        if action == "ban":
            ban_user(target_id, True)
            bot.answer_callback_query(call.id, "User banned successfully.", show_alert=True)
            
            # Re-render the user info
            from handlers.states_handler import _handle_search_user
            message_mock = telebot.types.Message(
                message_id=0, from_user=call.from_user, date=0, chat=call.message.chat, content_type='text', options={}, json_string=""
            )
            # Instead of importing _handle_search_user which might cause circular imports, 
            # we just close the window and say it's done.
            bot.edit_message_text(
                f"🚫 User <code>{target_id}</code> has been banned.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_back_kb(),
            )
            
        elif action == "unban":
            ban_user(target_id, False)
            bot.answer_callback_query(call.id, "User unbanned successfully.", show_alert=True)
            
            bot.edit_message_text(
                f"✅ User <code>{target_id}</code> has been unbanned.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_back_kb(),
            )
            
        elif action == "delete":
            delete_user(target_id)
            bot.answer_callback_query(call.id, "User deleted successfully.", show_alert=True)
            
            bot.edit_message_text(
                f"🗑️ User <code>{target_id}</code> has been deleted.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_back_kb(),
            )
            
        elif action == "msg":
            user_states.set(call.from_user.id, {
                "action": "admin_send_msg",
                "target_id": target_id,
            })
            bot.edit_message_text(
                f"✉️ <b>Send Message to User</b>\n\n"
                f"Enter the message you want to send to user <code>{target_id}</code>.\n\n"
                f"<i>Note: It will be prefixed with 'Message from owner'</i>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_back_kb(),
            )
            bot.answer_callback_query(call.id)
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  ADD / REMOVE CREDITS                                            ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:add_credits")
    def cb_admin_add_credits(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        user_states.set(call.from_user.id, {
            "action": "admin_credits",
            "operation": "add",
            "step": "user_id",
        })
        bot.edit_message_text(
            "➕ <b>Add Credits</b>\n\n"
            "Enter the user's Telegram ID:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "adm:remove_credits")
    def cb_admin_remove_credits(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        user_states.set(call.from_user.id, {
            "action": "admin_credits",
            "operation": "remove",
            "step": "user_id",
        })
        bot.edit_message_text(
            "➖ <b>Remove Credits</b>\n\n"
            "Enter the user's Telegram ID:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  BROADCAST                                                       ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:broadcast")
    def cb_admin_broadcast(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        user_states.set(call.from_user.id, {
            "action": "admin_broadcast",
        })
        bot.edit_message_text(
            "📢 <b>Broadcast Message</b>\n\n"
            "Enter the message to send to all users:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  STATISTICS                                                      ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:stats")
    def cb_admin_stats(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        text = (
            "📊 <b>Statistics</b>\n\n"
            f"👥 Total Users: <b>{count_users()}</b>\n"
            f"📦 Active Products: <b>{count_products()}</b>\n"
            f"🛒 Total Orders: <b>{count_orders()}</b>\n"
            f"💳 Total Payments: <b>{count_payments()}</b>\n"
            f"💎 Total Credits Sold: <b>{total_credits_sold()}</b>"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔════════════════════════════════════════════════════════════════════╗
    # ║  PAYMENT SETTINGS                                                  ║
    # ╚════════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:payment_settings")
    def cb_payment_settings(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        ps = get_payment_settings()
        text = (
            "⚙️ <b>Payment Settings</b>\n\n"
            f"💳 <b>UPI ID:</b> <code>{ps['upi_id']}</code>\n"
            f"👤 <b>UPI Name:</b> {ps['upi_name']}\n"
            f"🪙 <b>Binance UID:</b> <code>{ps['binance_uid']}</code>\n\n"
            "Tap a button below to edit:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=payment_settings_kb(),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "adm:prices_settings")
    def cb_prices_settings(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        packages = get_credit_packages()
        text = (
            "🏷 <b>Edit Package Prices</b>\n\n"
            "Select a package and currency to edit its price:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=prices_settings_kb(packages),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admset:"))
    def cb_edit_setting(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        setting_key = call.data.split(":")[1]
        
        # Determine label and current value
        current = "N/A"
        label = setting_key
        
        if setting_key.startswith("pkg_"):
            # Format: pkg_1_inr, pkg_3_usdt
            parts = setting_key.split("_")
            qty = parts[1]
            curr = "UPI (₹)" if parts[2] == "inr" else "Binance ($)"
            label = f"{qty} Credit(s) - {curr}"
            
            packages = get_credit_packages()
            pkg = packages.get(int(qty), {})
            current = pkg.get(parts[2], "N/A")
        elif setting_key.startswith("referral_"):
            ref_config = get_referral_config()
            referral_labels = {
                "referral_points_per_credit": "🔢 Points per Credit",
                "referral_max_free_credits": "🎯 Max Free Credits",
            }
            referral_config_keys = {
                "referral_points_per_credit": "points_per_credit",
                "referral_max_free_credits": "max_free_credits",
            }
            label = referral_labels.get(setting_key, setting_key)
            current = ref_config.get(referral_config_keys.get(setting_key, ""), "N/A")
        else:
            labels = {
                "upi_id": "💳 UPI ID",
                "upi_name": "👤 UPI Name",
                "binance_uid": "🪙 Binance UID",
            }
            label = labels.get(setting_key, setting_key)
            ps = get_payment_settings()
            current = ps.get(setting_key, "N/A")

        user_states.set(call.from_user.id, {
            "action": "admin_edit_setting",
            "setting_key": setting_key,
            "setting_label": label,
        })
        bot.edit_message_text(
            f"⚙️ <b>Edit {label}</b>\n\n"
            f"Current value: <code>{current}</code>\n\n"
            "Enter the new value:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  UI SETTINGS                                                         ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    
    @bot.callback_query_handler(func=lambda c: c.data == "adm:ui_settings")
    def cb_ui_settings(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        
        from keyboards.inline import admin_ui_button_list_kb
        bot.edit_message_text(
            "🎨 <b>UI Settings</b>\n\n"
            "Select a button to customize its text, color style, or premium emoji:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_ui_button_list_kb(),
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admui:"))
    def cb_admui_actions(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
            
        parts = call.data.split(":")
        action = parts[1]
        button_key = parts[2]
        
        from keyboards.inline import admin_ui_edit_kb, admin_ui_style_kb, admin_back_kb
        from utils.helpers import get_ui_buttons, clear_ui_cache
        from database import update_ui_setting
        from handlers.states_handler import user_states
        
        ui = get_ui_buttons()
        cfg = ui.get(button_key, {})
        
        if action == "edit":
            text = cfg.get('text', '<i>(Default)</i>')
            style = cfg.get('style', '<i>(Default)</i>')
            emoji = cfg.get('emoji_id', '<i>None</i>')
            
            bot.edit_message_text(
                f"🎨 <b>Editing Button:</b> <code>{button_key}</code>\n\n"
                f"<b>Current Text:</b> {text}\n"
                f"<b>Current Style:</b> {style}\n"
                f"<b>Custom Emoji ID:</b> <code>{emoji}</code>\n\n"
                "Choose what to edit:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_ui_edit_kb(button_key),
            )
            
        elif action == "style":
            bot.edit_message_text(
                f"🎨 <b>Select Style for:</b> <code>{button_key}</code>\n\n"
                "Primary = Blue\nSuccess = Green\nDanger = Red\nNone = Default",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_ui_style_kb(button_key),
            )
            
        elif action == "setstyle":
            style_val = parts[3]
            update_ui_setting(button_key, "style", style_val)
            clear_ui_cache()
            bot.answer_callback_query(call.id, f"Style set to {style_val}", show_alert=True)
            # Re-render edit menu
            call.data = f"admui:edit:{button_key}"
            cb_admui_actions(call)
            return
            
        elif action == "rmemoji":
            update_ui_setting(button_key, "emoji_id", None)
            clear_ui_cache()
            bot.answer_callback_query(call.id, "Custom emoji removed", show_alert=True)
            # Re-render edit menu
            call.data = f"admui:edit:{button_key}"
            cb_admui_actions(call)
            return
            
        elif action == "settext":
            user_states.set(call.from_user.id, {
                "action": "admin_ui_set_text",
                "button_key": button_key,
            })
            bot.send_message(
                call.message.chat.id,
                f"✏️ <b>Enter new text for button:</b> <code>{button_key}</code>",
                parse_mode="HTML",
                reply_markup=admin_back_kb()
            )
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
        elif action == "setemoji":
            user_states.set(call.from_user.id, {
                "action": "admin_ui_set_emoji",
                "button_key": button_key,
            })
            bot.send_message(
                call.message.chat.id,
                f"✨ <b>Enter Premium Emoji ID for button:</b> <code>{button_key}</code>\n\n"
                "<i>(Must be a valid numerical ID for a premium animated emoji)</i>",
                parse_mode="HTML",
                reply_markup=admin_back_kb()
            )
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  QR ORDER REVIEW                                                 ║
    # ╚══════════════════════════════════════════════════════════════════╝

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admqr:"))
    def cb_admin_qr_review(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return

        parts = call.data.split(":")
        action = parts[1]  # approve, reject, reupload
        qr_order_id = parts[2]

        from database import get_qr_order, update_qr_order_status, add_credits

        qr_order = get_qr_order(qr_order_id)
        if not qr_order:
            bot.answer_callback_query(call.id, "❌ QR order not found.", show_alert=True)
            return

        user_id = qr_order["user_id"]

        if action == "approve":
            update_qr_order_status(qr_order_id, "approved")

            # Update admin message
            try:
                bot.edit_message_caption(
                    caption=call.message.caption + "\n\n✅ <b>APPROVED</b>",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass

            # Notify user
            try:
                bot.send_message(
                    user_id,
                    "✅ <b>Your QR payment was successful.</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            bot.answer_callback_query(call.id, "✅ Payment Approved", show_alert=True)

        elif action == "reject":
            update_qr_order_status(qr_order_id, "rejected")

            # Refund credits to user
            credits_to_refund = qr_order.get("credits_used", 0)
            if credits_to_refund > 0:
                add_credits(user_id, credits_to_refund)
                logger.info(
                    "QR refund: user=%s credits=%s qr_order=%s",
                    user_id, credits_to_refund, qr_order_id,
                )

            # Update admin message
            try:
                bot.edit_message_caption(
                    caption=call.message.caption + f"\n\n❌ <b>REJECTED</b> — {credits_to_refund} credit(s) refunded",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass

            # Notify user
            try:
                bot.send_message(
                    user_id,
                    "❌ <b>Your QR payment was rejected, and the credit has been refunded successfully.</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            bot.answer_callback_query(call.id, "❌ Rejected & Refunded", show_alert=True)

        elif action == "reupload":
            update_qr_order_status(qr_order_id, "reupload")

            # Update admin message
            try:
                bot.edit_message_caption(
                    caption=call.message.caption + "\n\n🔄 <b>REUPLOAD REQUESTED</b>",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass

            # Set user state to awaiting QR upload again
            user_states.set(user_id, {
                "action": "awaiting_qr_upload",
                "qr_order_id": qr_order_id,
            })

            # Notify user with reupload prompt
            from keyboards.inline import purchase_success_qr_kb
            try:
                bot.send_message(
                    user_id,
                    "⚠️ <b>Your QR is expired or there was a payment error.</b>\n\n"
                    "Please reupload a <b>fresh new QR code</b>.\n\n"
                    "<i>⚠️ Do not upload the same QR code again.</i>",
                    parse_mode="HTML",
                    reply_markup=purchase_success_qr_kb(qr_order_id),
                )
            except Exception:
                pass
            bot.answer_callback_query(call.id, "🔄 Reupload requested", show_alert=True)
