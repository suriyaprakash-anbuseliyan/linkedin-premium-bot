"""
handlers/orders.py
──────────────────
User order history page.
"""

import telebot
from database import get_user_orders
from keyboards.inline import back_to_menu_kb, join_channel_kb
from utils.helpers import check_membership, format_datetime


ACCESS_RESTRICTED = (
    "🔒 <b>Access Restricted</b>\n\n"
    "To use this bot, please join our community first."
)


def register(bot: telebot.TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "menu:orders")
    def cb_orders(call: telebot.types.CallbackQuery):
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

        orders = get_user_orders(call.from_user.id)
        if not orders:
            bot.edit_message_text(
                "📜 <b>Your Orders</b>\n\n"
                "You haven't made any purchases yet.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=back_to_menu_kb(),
            )
            bot.answer_callback_query(call.id)
            return

        lines = ["📜 <b>Your Orders</b>\n"]
        buttons = []
        for i, order in enumerate(orders[:20], 1):  # show last 20
            items = order.get("items", [])
            if not items:
                items_str = ""
            elif len(items) <= 2:
                items_str = "".join([f"\n   🔗 <code>{item}</code>" for item in items])
            else:
                items_str = f"\n   🔗 <code>{items[0]}</code>\n   🔗 <code>{items[1]}</code>\n   <i>... and {len(items) - 2} more item(s)</i>"
            
            order_text = (
                f"{i}. <b>{order['product_name']}</b>\n"
                f"   💎 Credits: {order['credits_used']}  •  "
                f"📅 {format_datetime(order.get('created_at'))}{items_str}\n"
            )
            
            if len("\n".join(lines)) + len(order_text) > 3900:
                lines.append("\n<i>... and older orders</i>")
                break
                
            lines.append(order_text)
            
            # If the order has items, provide a download button
            if items:
                order_id = str(order['_id'])
                buttons.append(telebot.types.InlineKeyboardButton(f"📥 Download #{i}", callback_data=f"order:download:{order_id}"))
            
        text = "\n".join(lines)
        
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        if buttons:
            kb.add(*buttons)
        kb.add(telebot.types.InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main"))

        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("order:download:"))
    def cb_order_download(call: telebot.types.CallbackQuery):
        order_id = call.data.split(":")[2]
        from database import orders_col
        from bson import ObjectId
        
        try:
            order = orders_col.find_one({"_id": ObjectId(order_id)})
        except Exception:
            order = None
            
        if not order:
            bot.answer_callback_query(call.id, "Order not found.", show_alert=True)
            return
            
        if order.get("user_id") != call.from_user.id:
            bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
            return
            
        items = order.get("items", [])
        if not items:
            bot.answer_callback_query(call.id, "No links found for this order.", show_alert=True)
            return
            
        import io
        file_content = f"Order: {order.get('product_name', 'Unknown')}\n\n"
        for item in items:
            file_content += f"Link: {item}\n\n"
            
        doc = io.BytesIO(file_content.encode('utf-8'))
        doc.name = f"Order_links.txt"
        
        bot.send_document(
            call.message.chat.id, 
            document=doc, 
            caption=f"📦 Here are your links for <b>{order.get('product_name')}</b>",
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)
