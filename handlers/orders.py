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
            
        text = "\n".join(lines)
        
        kb = telebot.types.InlineKeyboardMarkup(row_width=1)
        kb.add(telebot.types.InlineKeyboardButton("📥 Download Order", callback_data="order:prompt_download"))
        kb.add(telebot.types.InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main"))

        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "order:prompt_download")
    def cb_order_prompt(call: telebot.types.CallbackQuery):
        from utils.states import user_states
        user_states.set(call.from_user.id, {"action": "download_order"})
        
        bot.edit_message_text(
            "📥 <b>Download Order</b>\n\n"
            "Please copy and paste the <b>Order ID</b> of the order you wish to download:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=telebot.types.InlineKeyboardMarkup().add(
                telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="menu:orders")
            )
        )
        bot.answer_callback_query(call.id)
