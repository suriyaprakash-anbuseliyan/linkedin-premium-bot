import telebot
from database import redeem_gift_code
from keyboards.inline import back_to_menu_kb
from utils.states import user_states

def register(bot: telebot.TeleBot):
    
    @bot.callback_query_handler(func=lambda c: c.data == "menu:giftcode")
    def cb_menu_giftcode(call: telebot.types.CallbackQuery):
        user_id = call.from_user.id
        user_states.set(user_id, {"action": "awaiting_gift_code"})
        
        bot.edit_message_text(
            "🎟 <b>Redeem Gift Code</b>\n\n"
            "Please enter your Gift Code below 👇",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_to_menu_kb()
        )

    # ── Text handler for awaiting_gift_code is added in states_handler.py ──
