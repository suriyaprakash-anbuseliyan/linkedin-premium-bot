"""
handlers/products.py
────────────────────
Product browsing and purchasing flow for users.
"""

import telebot
import threading
from database import (
    get_active_products, get_product, get_user,
    remove_balance, create_order,
    get_available_stock_count, claim_stock_item,
    create_qr_order, update_qr_order_status, add_balance, refund_stock
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

TIMER_CONTEXTS = {}

def _qr_timeout(bot: telebot.TeleBot, qr_order_id: str, user_id: int):
    from database import get_qr_order
    qr_order = get_qr_order(qr_order_id)
    if qr_order and qr_order["status"] in ("awaiting_qr", "reupload"):
        update_qr_order_status(qr_order_id, "cancelled")
        credits_to_refund = qr_order.get("price_paid_usd", 0.0)
        if credits_to_refund > 0:
            add_balance(user_id, credits_to_refund)
            
        refund_stock(
            product_id=qr_order.get("product_id"),
            qty=qr_order.get("qty", 1),
            is_numerical=qr_order.get("is_numerical", False),
            items=qr_order.get("items", [])
        )
        
        try:
            bot.send_message(
                user_id,
                "❌ <b>QR Upload Timeout</b>\n\n"
                f"You did not upload the QR code within 150 seconds. "
                f"Your order for {qr_order.get('qty')}x <b>{qr_order.get('product_name')}</b> has been cancelled and ${credits_to_refund:.2f} has been refunded.",
                parse_mode="HTML"
            )
        except Exception:
            pass

def start_qr_timeout(bot: telebot.TeleBot, qr_order_id: str, user_id: int, chat_id: int = None, message_id: int = None, base_text: str = None, reply_markup = None):
    TIMER_CONTEXTS[qr_order_id] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "base_text": base_text,
        "reply_markup": reply_markup
    }
    
    def _timer_worker():
        import time
        from database import get_qr_order
        timeout = 150
        step = 5
        
        for remaining in range(timeout, 0, -step):
            qr_order = get_qr_order(qr_order_id)
            if not qr_order or qr_order["status"] not in ("awaiting_qr", "reupload"):
                TIMER_CONTEXTS.pop(qr_order_id, None)
                return
                
            ctx = TIMER_CONTEXTS.get(qr_order_id, {})
            c_chat = ctx.get("chat_id")
            c_msg = ctx.get("message_id")
            c_text = ctx.get("base_text")
            c_markup = ctx.get("reply_markup")
            
            if c_chat and c_msg and c_text:
                timer_text = f"\n\n⏳ <b>Time remaining to upload QR:</b> {remaining} seconds"
                try:
                    bot.edit_message_text(
                        c_text + timer_text,
                        chat_id=c_chat,
                        message_id=c_msg,
                        parse_mode="HTML",
                        reply_markup=c_markup
                    )
                except Exception:
                    pass
            time.sleep(step)
            
        TIMER_CONTEXTS.pop(qr_order_id, None)
        _qr_timeout(bot, qr_order_id, user_id)

    threading.Thread(target=_timer_worker, daemon=True).start()

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
            f"💎 <b>Cost:</b> ${product.get('price_usd', 0.0):.2f}\n"
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
            total_cost_usd = product.get("price_usd", 0.0) * qty
            from keyboards.inline import product_payment_method_kb
            from database import get_user
            user = get_user(call.from_user.id)
            
            bot.edit_message_text(
                f"🛒 <b>Checkout</b>\n\n"
                f"📦 Product: <b>{product['name']}</b>\n"
                f"🔢 Quantity: <b>{qty}</b>\n"
                f"💰 Total Cost: <b>${total_cost_usd:.2f}</b>\n"
                f"Your Wallet Balance: <b>${user.get('wallet_balance', 0.0):.2f}</b>\n\n"
                "<i>Select your payment method below:</i>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=product_payment_method_kb(product_id, qty, total_cost_usd)
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

    # ── Purchase confirm (Wallet) ─────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("prod:confirm:wallet:"))
    def cb_confirm_purchase_wallet(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        parts = call.data.split(":")
        product_id = parts[3]
        qty = int(parts[4]) if len(parts) > 4 else 1
        
        product = get_product(product_id)
        user = get_user(call.from_user.id)

        if not product or not product.get("active"):
            bot.answer_callback_query(call.id, "Product no longer available.", show_alert=True)
            return
        if not user:
            bot.answer_callback_query(call.id, "Please /start first.", show_alert=True)
            return
            
        total_cost_usd = product.get("price_usd", 0.0) * qty
        if user.get("wallet_balance", 0.0) < total_cost_usd:
            bot.answer_callback_query(
                call.id, "❌ Insufficient wallet balance.", show_alert=True,
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

        actual_cost_usd = product.get("price_usd", 0.0) * actual_qty

        # Deduct wallet balance
        from database import remove_balance
        remove_balance(call.from_user.id, actual_cost_usd)
        
        # Create order
        items_list = [item["content"] for item in claimed_items] if not is_num else [f"Service Order (x{actual_qty})"]
        order_id = create_order(call.from_user.id, product["name"], actual_cost_usd, items_list)
        logger.info(
            "Purchase: user=%s product=%s amount_usd=%s qty=%s is_numerical=%s",
            call.from_user.id, product["name"], actual_cost_usd, actual_qty, is_num
        )
        u = get_user(call.from_user.id)
        if u:
            from utils.helpers import announce_event
            announce_event(bot, "PRODUCT PURCHASED (WALLET)", call.from_user.id, u.get("wallet_balance", 0.0), f"{product['name']} x{actual_qty} purchased")

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
                credits_used=actual_cost_usd,
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

        from database import get_delivery_settings
        del_settings = get_delivery_settings()

        delivery_msg = product.get("delivery_message", "").strip()
        if not delivery_msg:
            delivery_msg = del_settings.get("global_message", "Thank you for your purchase! 🎉")

        if is_num:
            links_block = ""
            text = (
                "✅ <b>Purchase Successful!</b>\n\n"
                f"📦 <b>{product['name']}</b> (x{actual_qty})\n\n"
                f"{qr_text}"
                f"{delivery_msg}"
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
            product_exp_days = product.get("expiration_days", del_settings.get("expiration_days", 7))
            warn_text = del_settings.get("expiration_warning", "⚠️ <i>Use these links within {days} days before they expire.</i>").replace("{days}", str(product_exp_days))
            links_block = f"━━━━━━━━━━━━━━━━━━━\n{links_text}\n━━━━━━━━━━━━━━━━━━━\n\n{warn_text}\n\n"

            text = (
                "✅ <b>Purchase Successful!</b>\n\n"
                f"📦 <b>{product['name']}</b> (x{actual_qty})\n\n"
                f"{links_block}"
                f"{qr_text}"
                f"{delivery_msg}"
            )
            
            if len(text) > 4000:
                brief_text = (
                    "✅ <b>Purchase Successful!</b>\n\n"
                    f"📦 <b>{product['name']}</b> (x{actual_qty})\n\n"
                    f"{qr_text}"
                    f"{delivery_msg}\n\n"
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
                    caption=warn_text, 
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
        
        if requires_qr and qr_order_id:
            final_text = brief_text if ('brief_text' in locals() and len(text) > 4000) else text
            start_qr_timeout(bot, qr_order_id, call.from_user.id, call.message.chat.id, call.message.message_id, final_text, reply_markup)

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
        base_text = (
            "📲 <b>Upload QR Code</b>\n\n"
            "Please send your <b>UPI QR code image</b> now.\n\n"
            "<i>⚠️ Make sure the QR code is clear and not expired.</i>"
        )
        bot.edit_message_text(
            base_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        if qr_order_id in TIMER_CONTEXTS:
            TIMER_CONTEXTS[qr_order_id].update({
                "base_text": base_text,
                "reply_markup": back_to_menu_kb()
            })
        bot.answer_callback_query(call.id)

# ── Direct Payment (UPI / Binance / BEP-20) ─────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("prod:direct:"))
    def cb_direct_pay(call: telebot.types.CallbackQuery):
        if not _gate(bot, call):
            return
        parts = call.data.split(":")
        method = parts[2].upper()
        product_id = parts[3]
        qty = int(parts[4]) if len(parts) > 4 else 1
        
        product = get_product(product_id)
        if not product or not product.get("active"):
            bot.answer_callback_query(call.id, "Product no longer available.", show_alert=True)
            return
            
        total_cost_usd = product.get("price_usd", 0.0) * qty
        
        from database import get_payment_settings
        ps = get_payment_settings()
        from keyboards.inline import cancel_payment_kb
        
        if method == "UPI":
            user_states.set(call.from_user.id, {
                "action": "awaiting_utr",
                "amount_usd": total_cost_usd,
                "method": "UPI",
                "intent": "direct_pay",
                "product_id": product_id,
                "qty": qty
            })
            
            # conversion 1$ = 100 Rs
            inr_price = int(total_cost_usd * 100)
            UPI_ID = ps.get("upi_id", "example@upi")
            UPI_NAME = ps.get("upi_name", "Bot Admin")
        
            text = (
                "💳 <b>UPI Payment (Direct Pay)</b>\n\n"
                f"Product: <b>{product['name']} (x{qty})</b>\n"
                f"Amount to Pay: <b>₹{inr_price}</b> (for ${total_cost_usd:.2f})\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"<b>UPI ID:</b> <code>{UPI_ID}</code>\n"
                f"<b>Name:</b> {UPI_NAME}\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "Please transfer the exact amount and then <b>enter your 12-digit UTR Number</b> below 👇"
            )
            
            from config import UPI_QR_PATH
            try:
                with open(UPI_QR_PATH, "rb") as qr:
                    bot.send_photo(
                        chat_id=call.message.chat.id,
                        photo=qr,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=cancel_payment_kb()
                    )
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=cancel_payment_kb())

        elif method == "BINANCE":
            user_states.set(call.from_user.id, {
                "action": "awaiting_binance_id",
                "amount_usd": total_cost_usd,
                "method": "Binance",
                "intent": "direct_pay",
                "product_id": product_id,
                "qty": qty
            })
            
            text = (
                "🪙 <b>Binance Payment (Direct Pay)</b>\n\n"
                f"Product: <b>{product['name']} (x{qty})</b>\n"
                f"Amount to Pay: <b>${total_cost_usd:.2f} USDT</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"<b>Binance UID:</b> <code>{ps.get('binance_uid', 'N/A')}</code>\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "After transferring via Binance Pay, <b>enter your Binance Order ID</b> below 👇"
            )
            bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=cancel_payment_kb())
            
        elif method == "BEP20":
            user_states.set(call.from_user.id, {
                "action": "awaiting_bep20_id",
                "amount_usd": total_cost_usd,
                "method": "BEP-20",
                "intent": "direct_pay",
                "product_id": product_id,
                "qty": qty
            })
            
            text = (
                "🔗 <b>BEP-20 (USDT) Payment (Direct Pay)</b>\n\n"
                f"Product: <b>{product['name']} (x{qty})</b>\n"
                f"Amount to Pay: <b>${total_cost_usd:.2f} USDT</b>\n"
                "Network: <b>BNB Smart Chain (BEP-20)</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"<b>Deposit Address:</b>\n<code>{ps.get('bep20_address', 'N/A')}</code>\n"
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
            except Exception:
                bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=cancel_payment_kb())

        bot.answer_callback_query(call.id)
    
def process_direct_pay_delivery(bot: telebot.TeleBot, user_id: int, product_id: str, amount_usd: float, method: str):
    product = get_product(product_id)
    if not product:
        bot.send_message(user_id, "❌ Product not found during delivery.", reply_markup=back_to_menu_kb())
        return
        
    qty = 1 # By default, but we should pass qty from the state actually. Wait, state has qty. We need to pass it from _handle_payment_submission.
    # In states_handler.py, we only passed amount_usd. Let's fix this inside process_direct_pay_delivery or assume we can read user_states before it gets cleared?
    # No, it's cleared. So we'll have to add qty to the signature, but for now we can infer it.
    qty = int(amount_usd / product.get('price_usd', 1)) if product.get('price_usd', 0) > 0 else 1
    
    is_num = product.get("is_numerical", False)
    claimed_items = []
    
    if is_num:
        from database import update_product
        update_product(product_id, {"$inc": {"numerical_stock": -qty}})
    else:
        for _ in range(qty):
            item = claim_stock_item(product_id, user_id)
            if item:
                claimed_items.append(item)
        if not claimed_items:
            # We took their money but out of stock! Refund to wallet
            add_balance(user_id, amount_usd) # Wallet balance
            bot.send_message(user_id, f"❌ Out of stock! We have credited <b>${amount_usd:.2f}</b> to your Wallet Balance.", parse_mode="HTML", reply_markup=back_to_menu_kb())
            return
            
        qty = len(claimed_items)

    actual_cost_usd = product.get("price_usd", 0.0) * qty

    items_list = [item["content"] for item in claimed_items] if not is_num else [f"Service Order (x{qty})"]
    order_id = create_order(user_id, product["name"], actual_cost_usd, items_list)
    logger.info(f"Direct Pay Delivery: user={user_id} product={product['name']} amount={actual_cost_usd} method={method}")
    
    requires_qr = product.get("requires_qr", False)
    qr_order_id = None
    if requires_qr:
        qr_order_id = create_qr_order(
            user_id=user_id,
            product_id=product_id,
            product_name=product["name"],
            credits_used=actual_cost_usd,
            items=items_list,
            order_id=order_id,
            qty=qty,
            is_numerical=is_num,
        )
        qr_text = "📲 <b>Upload your UPI QR code</b> to complete the payment process.\n"
        reply_markup = purchase_success_qr_kb(qr_order_id)
    else:
        qr_text = ""
        from keyboards.inline import back_to_menu_kb
        reply_markup = back_to_menu_kb()

    from database import get_delivery_settings
    del_settings = get_delivery_settings()
    delivery_msg = product.get("delivery_message", "").strip() or del_settings.get("global_message", "Thank you for your purchase! 🎉")

    if is_num:
        text = f"✅ <b>Purchase Successful! ({method})</b>\n\n📦 <b>{product['name']}</b> (x{qty})\n\n{qr_text}{delivery_msg}"
        msg = bot.send_message(user_id, text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        links_text = "\n\n".join(
            f"🔗 {item['content']}\n⏰ Expires: {item.get('expires_at').strftime('%d %b %Y, %H:%M UTC') if item.get('expires_at') else 'N/A'}"
            for item in claimed_items
        )
        warn_text = del_settings.get("expiration_warning", "⚠️ <i>Use these links within 7 days before they expire.</i>")
        links_block = f"━━━━━━━━━━━━━━━━━━━\n{links_text}\n━━━━━━━━━━━━━━━━━━━\n\n{warn_text}\n\n"
        
        text = f"✅ <b>Purchase Successful! ({method})</b>\n\n📦 <b>{product['name']}</b> (x{qty})\n\n{links_block}{qr_text}{delivery_msg}"
        
        if len(text) > 4000:
            brief_text = f"✅ <b>Purchase Successful! ({method})</b>\n\n📦 <b>{product['name']}</b> (x{qty})\n\n{qr_text}{delivery_msg}\n\n<i>Your links are provided in the attached file below because there are too many to show here.</i>"
            msg = bot.send_message(user_id, brief_text, parse_mode="HTML", reply_markup=reply_markup)
            
            import io
            file_content = f"Purchase: {product['name']} (x{qty})\n\n"
            for item in claimed_items:
                exp = item.get('expires_at').strftime('%d %b %Y, %H:%M UTC') if item.get('expires_at') else 'N/A'
                file_content += f"Link: {item['content']}\nExpires: {exp}\n\n"
            doc = io.BytesIO(file_content.encode('utf-8'))
            doc.name = f"Order_{order_id}_links.txt"
            bot.send_document(user_id, document=doc, caption=warn_text, parse_mode="HTML")
        else:
            msg = bot.send_message(user_id, text, parse_mode="HTML", reply_markup=reply_markup)
            
    if requires_qr and qr_order_id:
        start_qr_timeout(bot, qr_order_id, user_id, msg.chat.id, msg.message_id, brief_text if len(text)>4000 else text, reply_markup)

