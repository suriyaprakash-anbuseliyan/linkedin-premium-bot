"""
handlers/products.py
────────────────────
Product browsing and purchasing flow for users.
"""

import telebot
from database import (
    get_active_products, get_product, get_user,
    remove_credits, create_order,
    get_available_stock_count, claim_stock_item,
    create_qr_order,
)
from keyboards.inline import (
    products_list_kb, product_detail_kb, confirm_purchase_kb,
    back_to_menu_kb, join_channel_kb, purchase_success_qr_kb,
)
from utils.helpers import check_membership
from utils.states import user_states
from config import logger


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

    # ── Product list ─────────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "menu:buy")
    def cb_buy_premium(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        products = get_active_products()
        if not products:
            bot.edit_message_text(
                "📭 <b>No products available at the moment.</b>\n"
                "Check back soon!",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=back_to_menu_kb(),
            )
            bot.answer_callback_query(call.id)
            return

        bot.edit_message_text(
            "🛒 <b>Available Products</b>\n\n"
            "Select a product to view details:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=products_list_kb(products),
        )
        bot.answer_callback_query(call.id)

    # ── Product detail ───────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("prod:view:"))
    def cb_product_detail(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        product_id = call.data.split(":")[2]
        product = get_product(product_id)
        if not product or not product.get("active"):
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return

        stock = get_available_stock_count(str(product['_id']))
        text = (
            f"📦 <b>{product['name']}</b>\n\n"
            f"{product['description']}\n\n"
            f"💎 <b>Cost:</b> {product['credit_cost']} credit(s)\n"
            f"📦 <b>In Stock:</b> {stock}"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=product_detail_kb(product_id),
        )
        bot.answer_callback_query(call.id)

    # ── Purchase intent ──────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("prod:buy:"))
    def cb_buy_product(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        product_id = call.data.split(":")[2]
        product = get_product(product_id)
        if not product or not product.get("active"):
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return

        # Check stock availability
        stock = get_available_stock_count(product_id)
        if stock == 0:
            bot.answer_callback_query(
                call.id, "❌ Out of stock! Check back later.", show_alert=True,
            )
            return

        requires_qr = product.get("requires_qr", False)

        if requires_qr:
            # Enforce strictly 1 pending QR order at a time
            from database import has_pending_qr_order
            if has_pending_qr_order(call.from_user.id):
                bot.answer_callback_query(call.id, "❌ You have an active QR payment. Please wait for it to be reviewed before placing a new order.", show_alert=True)
                return
            
            # Skip quantity step, enforce qty = 1
            qty = 1
            total_cost = product["credit_cost"] * qty
            from keyboards.inline import confirm_purchase_kb
            bot.edit_message_text(
                f"🛒 <b>Confirm Purchase</b>\n\n"
                f"📦 Product: <b>{product['name']}</b>\n"
                f"🔢 Quantity: <b>{qty}</b>\n"
                f"💰 Total Cost: <b>{total_cost}</b> credits\n\n"
                "Proceed with purchase?",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=confirm_purchase_kb(product_id, qty)
            )
            bot.answer_callback_query(call.id)
            return

        from utils.states import user_states
        user_states.set(call.from_user.id, {
            "action": "buy_quantity",
            "product_id": product_id,
            "max_stock": stock,
        })
        
        bot.edit_message_text(
            f"🛒 <b>{product['name']}</b>\n\n"
            f"How many would you like to buy?\n"
            f"(Available stock: {stock})\n\n"
            "<i>Please type a number below:</i>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=telebot.types.InlineKeyboardMarkup().add(
                telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="menu:buy")
            )
        )
        bot.answer_callback_query(call.id)

    # ── Purchase confirm ─────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("prod:confirm:"))
    def cb_confirm_purchase(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        parts = call.data.split(":")
        product_id = parts[2]
        qty = int(parts[3]) if len(parts) > 3 else 1
        
        product = get_product(product_id)
        user = get_user(call.from_user.id)

        if not product or not product.get("active"):
            bot.answer_callback_query(call.id, "Product no longer available.", show_alert=True)
            return
        if not user:
            bot.answer_callback_query(call.id, "Please /start first.", show_alert=True)
            return
            
        total_cost = product["credit_cost"] * qty
        if user["credits"] < total_cost:
            bot.answer_callback_query(
                call.id, "❌ Insufficient credits.", show_alert=True,
            )
            return

        # Check stock again before looping
        stock = get_available_stock_count(product_id)
        if stock < qty:
            bot.answer_callback_query(call.id, "❌ Not enough stock! Try a smaller quantity.", show_alert=True)
            return

        is_num = product.get("is_numerical", False)
        claimed_items = []
        actual_qty = qty
        
        if is_num:
            # Deduct numerical stock directly
            from database import update_product
            update_product(product_id, {"$inc": {"numerical_stock": -qty}})
        else:
            # Claim physical links
            for _ in range(qty):
                item = claim_stock_item(product_id, call.from_user.id)
                if item:
                    claimed_items.append(item)
                    
            if not claimed_items:
                bot.answer_callback_query(call.id, "❌ Out of stock! Try again later.", show_alert=True)
                return
            actual_qty = len(claimed_items)

        actual_cost = product["credit_cost"] * actual_qty

        # Deduct credits
        remove_credits(call.from_user.id, actual_cost)
        
        # Create order
        items_list = [item["content"] for item in claimed_items] if not is_num else [f"Service Order (x{actual_qty})"]
        order_id = create_order(call.from_user.id, product["name"], actual_cost, items_list)
        logger.info(
            "Purchase: user=%s product=%s credits=%s qty=%s is_numerical=%s",
            call.from_user.id, product["name"], actual_cost, actual_qty, is_num
        )
        u = get_user(call.from_user.id)
        if u:
            from utils.helpers import announce_event
            lbl = "service(s)" if is_num else "link(s)"
            announce_event(bot, "PRODUCT PURCHASED", call.from_user.id, u["credits"], f"Purchased {actual_qty} {lbl}")

        requires_qr = product.get("requires_qr", False)

        # Create QR order for this purchase if required
        if requires_qr:
            from database import has_pending_qr_order
            if has_pending_qr_order(call.from_user.id):
                bot.answer_callback_query(call.id, "❌ You have an active QR payment. Please wait for it to be reviewed before placing a new order.", show_alert=True)
                return

            qr_order_id = create_qr_order(
                user_id=call.from_user.id,
                product_id=product_id,
                product_name=product["name"],
                credits_used=actual_cost,
                items=items_list,
                order_id=order_id,
                qty=actual_qty,
                is_numerical=is_num,
            )
            qr_text = "📲 <b>Upload your UPI QR code</b> to complete the payment process.\n"
            reply_markup = purchase_success_qr_kb(qr_order_id)
        else:
            qr_text = ""
            from keyboards.inline import back_to_menu_kb
            reply_markup = back_to_menu_kb()

        if is_num:
            links_block = ""
            text = (
                "✅ <b>Purchase Successful!</b>\n\n"
                f"📦 <b>{product['name']}</b> (x{actual_qty})\n\n"
                f"{qr_text}"
                "Thank you for your purchase! 🎉"
            )
            bot.edit_message_text(
                text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        else:
            links_text = "\n\n".join(
                f"🔗 {item['content']}\n"
                f"⏰ Expires: {item.get('expires_at').strftime('%d %b %Y, %H:%M UTC') if item.get('expires_at') else 'N/A'}"
                for item in claimed_items
            )
            links_block = f"━━━━━━━━━━━━━━━━━━━\n{links_text}\n━━━━━━━━━━━━━━━━━━━\n\n⚠️ <i>Use these links within 7 days before they expire.</i>\n\n"

            text = (
                "✅ <b>Purchase Successful!</b>\n\n"
                f"📦 <b>{product['name']}</b> (x{actual_qty})\n\n"
                f"{links_block}"
                f"{qr_text}"
                "Thank you for your purchase! 🎉"
            )
            
            if len(text) > 4000:
                brief_text = (
                    "✅ <b>Purchase Successful!</b>\n\n"
                    f"📦 <b>{product['name']}</b> (x{actual_qty})\n\n"
                    f"{qr_text}"
                    "Thank you for your purchase! 🎉\n\n"
                    "<i>Your links are provided in the attached file below because there are too many to show here.</i>"
                )
                bot.edit_message_text(
                    brief_text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                import io
                
                # Format links for the text file
                file_content = f"Purchase: {product['name']} (x{actual_qty})\n\n"
                for item in claimed_items:
                    exp = item.get('expires_at').strftime('%d %b %Y, %H:%M UTC') if item.get('expires_at') else 'N/A'
                    file_content += f"Link: {item['content']}\nExpires: {exp}\n\n"
                    
                doc = io.BytesIO(file_content.encode('utf-8'))
                doc.name = f"Order_{order_id}_links.txt"
                bot.send_document(
                    call.message.chat.id, 
                    document=doc, 
                    caption="⚠️ <i>Use these links within 7 days before they expire.</i>", 
                    parse_mode="HTML"
                )
            else:
                bot.edit_message_text(
                    text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )

        bot.answer_callback_query(call.id, "✅ Purchase complete!")

    # ── QR Upload prompt ───────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("qr:upload:"))
    def cb_qr_upload(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        qr_order_id = call.data.split(":")[2]
        from database import get_qr_order
        qr_order = get_qr_order(qr_order_id)
        if not qr_order:
            bot.answer_callback_query(call.id, "❌ Order not found.", show_alert=True)
            return
        if qr_order["user_id"] != call.from_user.id:
            bot.answer_callback_query(call.id, "⛔ Not authorized.", show_alert=True)
            return
        if qr_order["status"] not in ("awaiting_qr", "reupload"):
            bot.answer_callback_query(call.id, "⚠️ QR already uploaded for this order.", show_alert=True)
            return

        user_states.set(call.from_user.id, {
            "action": "awaiting_qr_upload",
            "qr_order_id": qr_order_id,
        })
        bot.edit_message_text(
            "📲 <b>Upload QR Code</b>\n\n"
            "Please send your <b>UPI QR code image</b> now.\n\n"
            "<i>⚠️ Make sure the QR code is clear and not expired.</i>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        bot.answer_callback_query(call.id)
