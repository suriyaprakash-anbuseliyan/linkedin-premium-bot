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
    add_balance, remove_balance, get_user, search_user_by_id, get_all_user_ids,
    count_users, count_products, count_orders, count_payments, total_credits_sold,
    get_user_orders,
    get_available_stock_count, get_total_stock_count, add_stock_items, delete_product_stock,
    set_setting, ban_user, delete_user,
    is_maintenance_mode, set_maintenance_mode,
    is_referral_enabled, set_referral_enabled, get_referral_config, set_referral_config,
    is_credit_conversion_enabled, set_credit_conversion_enabled,
    get_payment_settings,
)
from keyboards.inline import (
    admin_panel_kb, admin_back_kb,
    admin_products_list_kb, admin_product_actions_kb,
    admin_payment_review_kb, payment_settings_kb,
    referral_settings_kb, admin_delivery_settings_kb,
)
from utils.helpers import is_admin, format_datetime
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
        from database import is_referral_enabled, is_credit_conversion_enabled, is_welcome_bonus_enabled
        is_ref = is_referral_enabled()
        is_conv = is_credit_conversion_enabled()
        is_welcome = is_welcome_bonus_enabled()
        status = "🟢 Enabled" if is_ref else "🔴 Disabled"
        conv_status = "🟢 ON" if is_conv else "🔴 OFF"
        welcome_status = "🟢 ON" if is_welcome else "🔴 OFF"
        
        text = (
            "⚙️ <b>Referral Settings</b>\n\n"
            f"<b>Referral Program:</b> {status}\n"
            f"<b>Credit Conversion:</b> {conv_status}\n"
            f"<b>Welcome Bonus:</b> {welcome_status}\n"
            f"🔢 <b>Points per Credit:</b> {ref_config['points_per_credit']}\n"
            f"🎯 <b>Max Free Bonus:</b> {ref_config['max_free_credits']}\n\n"
            "Tap a button below to edit:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=referral_settings_kb(ref_config, is_conv, is_welcome),
        )
        bot.answer_callback_query(call.id)

    # ── Delivery Settings ────────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "adm:delivery_settings")
    def cb_delivery_settings(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
        
        from database import get_delivery_settings
        del_settings = get_delivery_settings()
        
        text = (
            "📦 <b>Delivery Settings</b>\n\n"
            f"<b>Global Delivery Message:</b>\n<code>{del_settings['global_message']}</code>\n\n"
            f"<b>Expiration Days (for new stock):</b> <code>{del_settings['expiration_days']}</code>\n\n"
            f"<b>Expiration Warning Text:</b>\n<code>{del_settings['expiration_warning']}</code>\n\n"
            "Tap a button below to edit:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_delivery_settings_kb(),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admset:del_"))
    def cb_edit_delivery_setting(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔", show_alert=True)
            return
            
        setting_type = call.data.split(":")[1]
        
        if setting_type == "del_global_msg":
            prompt = "📝 <b>Edit Global Delivery Message</b>\n\nSend the new default delivery message (HTML supported):"
            action = "admin_set_del_global_msg"
        elif setting_type == "del_exp_days":
            prompt = "⏳ <b>Edit Expiration Days</b>\n\nSend the number of days links are valid for (integer):"
            action = "admin_set_del_exp_days"
        elif setting_type == "del_exp_warn":
            prompt = "⚠️ <b>Edit Expiration Warning Text</b>\n\nSend the new expiration warning message (HTML supported).\nUse <code>{days}</code> as a placeholder for the number of days."
            action = "admin_set_del_exp_warn"
        else:
            return
            
        user_states.set(call.from_user.id, {"action": action})
        bot.send_message(
            call.message.chat.id,
            prompt,
            parse_mode="HTML",
            reply_markup=admin_back_kb()
        )
        bot.answer_callback_query(call.id)

    # ── Credit Conversion Toggle ─────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "adm:toggle_conversion")
    def cb_toggle_conversion(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
            
        current = is_credit_conversion_enabled()
        from database import set_credit_conversion_enabled, is_referral_enabled, is_welcome_bonus_enabled
        set_credit_conversion_enabled(not current)
        
        # Re-render referral settings page
        ref_config = get_referral_config()
        is_ref = is_referral_enabled()
        is_conv = not current
        is_welcome = is_welcome_bonus_enabled()
        status = "🟢 Enabled" if is_ref else "🔴 Disabled"
        conv_status = "🟢 ON" if is_conv else "🔴 OFF"
        welcome_status = "🟢 ON" if is_welcome else "🔴 OFF"
        
        text = (
            "⚙️ <b>Referral Settings</b>\n\n"
            f"<b>Referral Program:</b> {status}\n"
            f"<b>Credit Conversion:</b> {conv_status}\n"
            f"<b>Welcome Bonus:</b> {welcome_status}\n"
            f"🔢 <b>Points per Credit:</b> {ref_config['points_per_credit']}\n"
            f"🎯 <b>Max Free Bonus:</b> {ref_config['max_free_credits']}\n\n"
            "Tap a button below to edit:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=referral_settings_kb(ref_config, is_conv, is_welcome),
        )
        status_text = "ON" if is_conv else "OFF"
        bot.answer_callback_query(call.id, f"Credit Conversion: {status_text}", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "adm:toggle_welcome_bonus")
    def cb_toggle_welcome_bonus(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
            
        from database import is_welcome_bonus_enabled, set_welcome_bonus_enabled, is_referral_enabled, is_credit_conversion_enabled
        current = is_welcome_bonus_enabled()
        set_welcome_bonus_enabled(not current)
        
        # Re-render referral settings page
        ref_config = get_referral_config()
        is_ref = is_referral_enabled()
        is_conv = is_credit_conversion_enabled()
        is_welcome = not current
        status = "🟢 Enabled" if is_ref else "🔴 Disabled"
        conv_status = "🟢 ON" if is_conv else "🔴 OFF"
        welcome_status = "🟢 ON" if is_welcome else "🔴 OFF"
        
        text = (
            "⚙️ <b>Referral Settings</b>\n\n"
            f"<b>Referral Program:</b> {status}\n"
            f"<b>Credit Conversion:</b> {conv_status}\n"
            f"<b>Welcome Bonus:</b> {welcome_status}\n"
            f"🔢 <b>Points per Credit:</b> {ref_config['points_per_credit']}\n"
            f"🎯 <b>Max Free Bonus:</b> {ref_config['max_free_credits']}\n\n"
            "Tap a button below to edit:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=referral_settings_kb(ref_config, is_conv, is_welcome),
        )
        status_text = "ON" if is_welcome else "OFF"
        bot.answer_callback_query(call.id, f"Welcome Bonus: {status_text}", show_alert=True)

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
            f"💎 Cost: ${product.get('price_usd', 0.0):.2f}\n"
            f"📌 Active: {'Yes' if product['active'] else 'No'}\n"
            f"{stock_line}\n"
            f"📅 Created: {format_datetime(product.get('created_at'))}"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_product_actions_kb(pid, product["active"], is_num, product.get("requires_qr", False)),
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

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:toggle_qr:"))
    def cb_admin_toggle_qr(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        pid = call.data.split(":")[2]
        product = get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return
            
        new_val = not product.get("requires_qr", False)
        update_product(pid, {"$set": {"requires_qr": new_val}})
        
        bot.answer_callback_query(call.id, f"QR Upload set to {'ON' if new_val else 'OFF'}")
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
                price_usd=state["product_cost"],
                is_numerical=False,
                numerical_stock=0,
            )
            user_states.clear(call.from_user.id)
            logger.info("Product created (Links): %s (id=%s)", state["product_name"], product_id)
            bot.edit_message_text(
                f"✅ <b>Product Created!</b>\n\n"
                f"Name: <b>{state['product_name']}</b>\n"
                f"Cost: ${state['product_cost']:.2f}\n"
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
        field_type = parts[1].split("_")[1] # "name", "desc", "cost", or "delmsg"
        pid = parts[2]
        
        product = get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return
            
        field_name_map = {
            "name": "Name",
            "desc": "Description",
            "cost": "Cost (USD)",
            "delmsg": "Delivery Message",
            "expdays": "Expiration Days"
        }
        
        user_states.set(call.from_user.id, {
            "action": "admin_edit_product",
            "product_id": pid,
            "field": field_type
        })
        
        if field_type == 'name':
            current_val = product.get('name')
        elif field_type == 'desc':
            current_val = product.get('description')
        elif field_type == 'delmsg':
            current_val = product.get('delivery_message', '')
        elif field_type == 'expdays':
            current_val = product.get('expiration_days', 'Global Default')
        else:
            current_val = product.get('price_usd')
        
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
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:addstock:") or c.data.startswith("admprod:addstock_dup:"))
    def cb_add_stock(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        
        allow_duplicates = call.data.startswith("admprod:addstock_dup:")
        pid = call.data.split(":")[2]
        
        product = get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return
        user_states.set(call.from_user.id, {
            "action": "admin_add_stock",
            "product_id": pid,
            "product_name": product["name"],
            "allow_duplicates": allow_duplicates,
        })
        dup_text = "⚠️ <b>Duplicate links WILL BE ADDED</b>." if allow_duplicates else "🔄 Duplicate links are automatically skipped."
        bot.edit_message_text(
            f"📦 <b>Add Stock — {product['name']}</b>\n\n"
            "<b>Option 1:</b> Paste links below, <b>one per line</b>.\n"
            "You can paste many links at once.\n\n"
            "<b>Option 2:</b> Type <b>multi</b> to send links\n"
            "across multiple messages (bypasses Telegram's\n"
            "4096-char limit).\n\n"
            "<b>Option 3:</b> Upload a <b>.csv</b> or <b>.txt</b> file\n"
            "containing your links.\n\n"
            f"{dup_text}\n\n"
            "Example:\n"
            "<code>https://example.com/link1\n"
            "PROMO-CODE-123\n"
            "username:password</code>",
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

        user_id = payment["user_id"]
        amount_usd = payment.get("amount_usd", 0.0)
        intent = payment.get("intent", "add_to_wallet")

        if intent == "add_to_wallet":
            from database import add_balance
            add_balance(user_id, amount_usd)
            logger.info("Payment approved (Wallet): user=%s amount_usd=%s by admin", user_id, amount_usd)
            
            from database import get_user
            user = get_user(user_id)
            if user:
                from utils.helpers import announce_event
                announce_event(bot, "WALLET ADDED (MANUAL)", user_id, user.get("wallet_balance", 0.0), "Approved by admin")

            try:
                bot.send_message(
                    user_id,
                    "✅ <b>Payment Approved!</b>\n\n"
                    f"💵 <b>${amount_usd:.2f}</b> added to your wallet successfully.\n"
                    "Thank you! 🎉",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        
        elif intent == "direct_pay":
            from handlers.products import process_direct_pay_delivery
            logger.info("Payment approved (Direct Pay): user=%s amount_usd=%s by admin", user_id, amount_usd)
            process_direct_pay_delivery(bot, user_id, payment.get("product_id"), amount_usd, payment.get("method", "Manual"))

        # Update admin message
        bot.edit_message_text(
            call.message.text + "\n\n✅ <b>APPROVED</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
        )
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
            
        elif action == "convert":
            points = user.get("referral_points", 0)
            from database import get_referral_config, users_col
            config = get_referral_config()
            ppc = config["points_per_credit"]
            
            if points < ppc:
                bot.answer_callback_query(call.id, f"❌ Not enough points. User has {points}, {ppc} points needed for 1 credit.", show_alert=True)
                return
                
            credits_to_add = points // ppc
            points_to_deduct = credits_to_add * ppc
            
            users_col.update_one(
                {"user_id": target_id},
                {"$inc": {"credits": credits_to_add, "free_referral_credits": credits_to_add, "referral_points": -points_to_deduct}}
            )
            bot.answer_callback_query(call.id, f"✅ Converted {points_to_deduct} points into {credits_to_add} credits.", show_alert=True)
            
            # Re-fetch user and re-render
            user = search_user_by_id(target_id)
            from utils.helpers import format_datetime
            info = (
                "👤 <b>User Info</b>\n\n"
                f"🆔 ID: <code>{user['user_id']}</code>\n"
                f"👤 Username: @{user.get('username', 'N/A')}\n"
                f"📛 Name: {user.get('first_name', 'N/A')}\n"\
                f"💵 Wallet Balance: ${user.get('wallet_balance', 0.0):.2f}\n"
                f"⭐ Points: {user.get('referral_points', 0)}\n"
                f"👥 Referrals: {user['referral_count']}\n"
                f"🎁 Free Bonus: ${user.get('free_referral_bonus', 0.0):.2f}\n"
                f"🔗 Referred By: {user.get('referred_by', 'N/A')}\n"
                f"📅 Joined: {format_datetime(user.get('joined_at'))}"
            )
            bot.edit_message_text(
                info,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_user_actions_kb(user['user_id'], user.get('is_banned', False))
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
            
        elif action == "orders":
            from database import get_user_orders
            from utils.helpers import format_datetime
            
            orders = get_user_orders(target_id)
            if not orders:
                bot.edit_message_text(
                    f"📜 <b>Orders for {target_id}</b>\n\n"
                    "This user hasn't made any purchases yet.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML",
                    reply_markup=admin_user_actions_kb(target_id, user.get('is_banned', False)),
                )
                bot.answer_callback_query(call.id)
                return
                
            lines = [f"📜 <b>Orders for {target_id}</b>\n"]
            for i, order in enumerate(orders[:20], 1):  # show last 20
                order_id = str(order['_id'])
                order_text = (
                    f"{i}. <b>{order['product_name']}</b>\n"
                    f"   💰 Paid: ${order.get('price_paid_usd', 0.0):.2f}  •  "
                    f"📅 {format_datetime(order.get('created_at'))}\n"
                    f"   🆔 Order ID: <code>{order_id}</code>\n"
                )
                
                if len("\n".join(lines)) + len(order_text) > 3900:
                    lines.append("\n<i>... and older orders</i>")
                    break
                lines.append(order_text)
                
            bot.edit_message_text(
                "\n".join(lines),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=admin_user_actions_kb(target_id, user.get('is_banned', False)),
            )
            bot.answer_callback_query(call.id)
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  ADD / REMOVE CREDITS                                            ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:add_balance")
    def cb_admin_add_balance(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        user_states.set(call.from_user.id, {
            "action": "admin_credits",
            "operation": "add",
            "step": "user_id",
        })
        bot.edit_message_text(
            "➕ <b>Add Balance</b>\n\n"
            "Enter the user's Telegram ID:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "adm:remove_balance")
    def cb_admin_remove_balance(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        user_states.set(call.from_user.id, {
            "action": "admin_credits",
            "operation": "remove",
            "step": "user_id",
        })
        bot.edit_message_text(
            "➖ <b>Remove Balance</b>\n\n"
            "Enter the user's Telegram ID:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╚══════════════════════════════════════════════════════════════════╝
    
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  SEARCH ORDER                                                    ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:search_order")
    def cb_admin_search_order(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        user_states.set(call.from_user.id, {
            "action": "admin_search_order",
        })
        bot.edit_message_text(
            "🔎 <b>Search Order</b>\n\n"
            "Please enter the <b>Order ID</b> or <b>User ID</b> you want to search:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
        )
        bot.answer_callback_query(call.id)

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  CANCEL ORDER                                                    ║
    # ╚══════════════════════════════════════════════════════════════════╝
    @bot.callback_query_handler(func=lambda c: c.data == "adm:cancel_order")
    def cb_admin_cancel_order(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        user_states.set(call.from_user.id, {
            "action": "admin_cancel_order",
        })
        bot.edit_message_text(
            "❌ <b>Cancel Order</b>\n\n"
            "Please enter the <b>Order ID</b> you want to cancel:",
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
        upi_status = "🟢 ON" if ps.get("upi_enabled", True) else "🔴 OFF"
        binance_status = "🟢 ON" if ps.get("binance_enabled", True) else "🔴 OFF"
        text = (
            "⚙️ <b>Payment Settings</b>\n\n"
            f"💳 <b>UPI ID:</b> <code>{ps.get('upi_id', 'N/A')}</code> ({upi_status})\n"
            f"👤 <b>UPI Name:</b> {ps.get('upi_name', 'N/A')}\n"
            f"🪙 <b>Binance UID:</b> <code>{ps.get('binance_uid', 'N/A')}</code> ({binance_status})\n\n"
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

    @bot.callback_query_handler(func=lambda c: c.data == "admset:toggle_upi")
    def cb_toggle_upi(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        ps = get_payment_settings()
        new_val = not ps.get("upi_enabled", True)
        from database import settings_col
        settings_col.update_one(
            {"_id": "payment_settings"},
            {"$set": {"upi_enabled": new_val}},
            upsert=True
        )
        bot.answer_callback_query(call.id, f"UPI Payment {'Enabled' if new_val else 'Disabled'}", show_alert=True)
        cb_payment_settings(call)

    @bot.callback_query_handler(func=lambda c: c.data == "admset:toggle_binance")
    def cb_toggle_binance(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        ps = get_payment_settings()
        new_val = not ps.get("binance_enabled", True)
        from database import settings_col
        settings_col.update_one(
            {"_id": "payment_settings"},
            {"$set": {"binance_enabled": new_val}},
            upsert=True
        )
        bot.answer_callback_query(call.id, f"Binance Payment {'Enabled' if new_val else 'Disabled'}", show_alert=True)
        cb_payment_settings(call)

    @bot.callback_query_handler(func=lambda c: c.data == "admset:toggle_bep20")
    def cb_toggle_bep20(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        ps = get_payment_settings()
        new_val = not ps.get("bep20_enabled", True)
        from database import settings_col
        settings_col.update_one(
            {"_id": "payment_settings"},
            {"$set": {"bep20_enabled": new_val}},
            upsert=True
        )
        bot.answer_callback_query(call.id, f"BEP-20 Payment {'Enabled' if new_val else 'Disabled'}", show_alert=True)
        cb_payment_settings(call)
        
    @bot.callback_query_handler(func=lambda c: c.data in ["admset:upload_upi_qr", "admset:upload_bep20_qr"])
    def cb_upload_qr(call: telebot.types.CallbackQuery):
        if not _admin_only(call):
            return
        
        qr_type = "UPI" if "upi" in call.data else "BEP-20"
        
        user_states.set(call.from_user.id, {
            "action": "admin_upload_qr",
            "qr_type": qr_type,
        })
        
        bot.edit_message_text(
            f"🖼 <b>Upload {qr_type} QR Code</b>\n\n"
            "Please send the QR code image now as a <b>Photo</b>.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_kb(),
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
        
        if setting_key.startswith("referral_"):
            ref_config = get_referral_config()
            referral_labels = {
                "referral_points_per_credit": "🔢 Points per Credit",
                "referral_max_free_credits": "🎯 Max Free Bonus",
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
                "bep20_address": "🔗 BEP-20 Address",
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

        from database import get_qr_order, update_qr_order_status, add_balance

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
                add_balance(user_id, credits_to_refund)
                
            # Refund stock to inventory
            from database import refund_stock
            refund_stock(
                product_id=qr_order.get("product_id"),
                qty=qr_order.get("qty", 1),
                is_numerical=qr_order.get("is_numerical", False),
                items=qr_order.get("items", [])
            )

            logger.info(
                "QR reject: user=%s credits_refunded=%s qr_order=%s",
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
                base_text = (
                    "⚠️ <b>Your QR is expired or there was a payment error.</b>\n\n"
                    "Please reupload a <b>fresh new QR code</b>.\n\n"
                    "<i>⚠️ Do not upload the same QR code again.</i>"
                )
                reply_kb = purchase_success_qr_kb(qr_order_id)
                msg = bot.send_message(
                    user_id,
                    base_text,
                    parse_mode="HTML",
                    reply_markup=reply_kb,
                )
                from handlers.products import start_qr_timeout
                start_qr_timeout(bot, qr_order_id, user_id, msg.chat.id, msg.message_id, base_text, reply_kb)
            except Exception:
                pass
            bot.answer_callback_query(call.id, "🔄 Reupload requested", show_alert=True)
