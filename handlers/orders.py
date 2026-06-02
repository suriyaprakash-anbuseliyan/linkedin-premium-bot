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
            items = order.get("items", [])
            items_str = "".join([f"\n   🔗 <code>{item}</code>" for item in items])
            lines.append(
                f"{i}. <b>{order['product_name']}</b>\n"
                f"   💎 Credits: {order['credits_used']}  •  "
                f"📅 {format_datetime(order.get('created_at'))}{items_str}\n"
            )
        text = "\n".join(lines)

        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        bot.answer_callback_query(call.id)
