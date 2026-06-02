"""
keyboards/inline.py
───────────────────
Every inline keyboard the bot uses, in one place.
Callback data uses a simple prefix convention:
    section:action:param
"""

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import REQUIRED_CHANNEL_LINK
from utils.helpers import get_credit_packages


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  MANDATORY JOIN                                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

def join_channel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📢 Join Channel", url=REQUIRED_CHANNEL_LINK),
        InlineKeyboardButton("✅ I've Joined", callback_data="check_join"),
    )
    return kb


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  MAIN MENU                                                         ║
# ╚══════════════════════════════════════════════════════════════════════╝

def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🛒 BUY", callback_data="menu:buy"))
    kb.add(
        InlineKeyboardButton("💰 Add Credits", callback_data="menu:credits"),
        InlineKeyboardButton("💳 Balance", callback_data="menu:balance"),
    )
    kb.add(
        InlineKeyboardButton("👤 Profile", callback_data="menu:profile"),
        InlineKeyboardButton("🎁 Refer/Earn", callback_data="menu:referral"),
    )
    kb.add(
        InlineKeyboardButton("📜 Orders", callback_data="menu:orders"),
        InlineKeyboardButton("🎟 Redeem Gift Code", callback_data="menu:giftcode"),
    )
    kb.add(
        InlineKeyboardButton("📞 Support", callback_data="menu:support"),
    )
    return kb


def back_to_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main"))
    return kb


def referral_menu_kb(can_convert: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔄 Redeem points", callback_data="ref:convert"))
    kb.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main"))
    return kb


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PRODUCTS / BUY PREMIUM                                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

def products_list_kb(products: list[dict]) -> InlineKeyboardMarkup:
    """Generate a list of product buttons for the user."""
    kb = InlineKeyboardMarkup(row_width=1)
    from database import get_available_stock_count
    for p in products:
        stock = get_available_stock_count(str(p['_id']))
        kb.add(InlineKeyboardButton(
            f"{p['name']} ({stock})  —  {p['credit_cost']} credit(s)",
            callback_data=f"prod:view:{p['_id']}",
        ))
    kb.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main"))
    return kb


def product_detail_kb(product_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🛒 Purchase", callback_data=f"prod:buy:{product_id}"),
        InlineKeyboardButton("🔙 Back to Products", callback_data="menu:buy"),
    )
    return kb


def confirm_purchase_kb(product_id: str, qty: int = 1) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Confirm", callback_data=f"prod:confirm:{product_id}:{qty}"),
        InlineKeyboardButton("❌ Cancel", callback_data="menu:buy"),
    )
    return kb


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  CREDIT PACKAGES                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

def credit_packages_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    packages = get_credit_packages()
    
    buttons = []
    for credits_qty in sorted(packages):
        pkg = packages[credits_qty]
        buttons.append(InlineKeyboardButton(
            f"💎 {credits_qty} (₹{pkg['inr']}/ ${pkg['usdt']})",
            callback_data=f"cred:pkg:{credits_qty}",
        ))
    kb.add(*buttons)
    
    kb.add(InlineKeyboardButton("📞 More than 20 credits? Contact Admin", callback_data="menu:support"))
    kb.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main"))
    return kb


def payment_method_kb(credits_qty: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💳 UPI", callback_data=f"pay:upi:{credits_qty}"),
        InlineKeyboardButton("🪙 Binance", callback_data=f"pay:binance:{credits_qty}"),
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="menu:credits"))
    return kb


def cancel_payment_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="menu:credits"))
    return kb


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN – payment review                                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

def admin_payment_review_kb(payment_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"admpay:approve:{payment_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"admpay:reject:{payment_id}"),
    )
    return kb


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN PANEL                                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

def admin_panel_kb(is_maintenance: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Add Product", callback_data="adm:add_product"),
        InlineKeyboardButton("📋 Manage Products", callback_data="adm:manage_products"),
    )
    kb.add(
        InlineKeyboardButton("✅ Pending Payments", callback_data="adm:pending_payments"),
        InlineKeyboardButton("📦 Orders", callback_data="adm:orders"),
    )
    kb.add(
        InlineKeyboardButton("👥 Users", callback_data="adm:users"),
        InlineKeyboardButton("➕ Add Credits", callback_data="adm:add_credits"),
    )
    kb.add(
        InlineKeyboardButton("➖ Remove Credits", callback_data="adm:remove_credits"),
        InlineKeyboardButton("📢 Send Announcement", callback_data="adm:broadcast"),
    )
    kb.add(
        InlineKeyboardButton("⚙️ Payment Settings", callback_data="adm:payment_settings"),
        InlineKeyboardButton("📊 Statistics", callback_data="adm:stats"),
    )
    
    maint_label = "🟢 Maintenance: ON" if is_maintenance else "🔴 Maintenance: OFF"
    kb.add(
        InlineKeyboardButton(maint_label, callback_data="adm:toggle_maintenance"),
        InlineKeyboardButton("🎁 Generate Gift Code", callback_data="adm:gen_gift_code"),
    )
    return kb


def payment_settings_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💳 Edit UPI ID", callback_data="admset:upi_id"),
        InlineKeyboardButton("👤 Edit UPI Name", callback_data="admset:upi_name"),
        InlineKeyboardButton("🪙 Edit Binance UID", callback_data="admset:binance_uid"),
        InlineKeyboardButton("🏷 Edit Package Prices", callback_data="adm:prices_settings"),
    )
    kb.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="adm:panel"))
    return kb


def admin_user_actions_kb(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Ban / Unban
    if is_banned:
        kb.add(InlineKeyboardButton("✅ Unban User", callback_data=f"admuser:unban:{user_id}"))
    else:
        kb.add(InlineKeyboardButton("🚫 Ban (Mute) User", callback_data=f"admuser:ban:{user_id}"))
        
    kb.add(InlineKeyboardButton("🗑️ Delete User", callback_data=f"admuser:delete:{user_id}"))
    kb.add(InlineKeyboardButton("🔙 Back to Search", callback_data="adm:users"))
    return kb


def prices_settings_kb(packages: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for qty in sorted(packages):
        kb.add(
            InlineKeyboardButton(f"✏️ {qty} Credit(s) - UPI (₹)", callback_data=f"admset:pkg_{qty}_inr"),
            InlineKeyboardButton(f"✏️ {qty} Credit(s) - Binance ($)", callback_data=f"admset:pkg_{qty}_usdt"),
        )
    kb.add(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm:payment_settings"))
    return kb


def admin_back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="adm:panel"))
    return kb


def gift_code_actions_kb(code: str) -> InlineKeyboardMarkup:
    """Keyboard shown after generating a gift code with send options."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📢 Send to All Users", callback_data=f"admgift:broadcast:{code}"),
        InlineKeyboardButton("📨 Send Privately", callback_data=f"admgift:private:{code}"),
        InlineKeyboardButton("🔙 Admin Panel", callback_data="adm:panel"),
    )
    return kb


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN – product management                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

def admin_products_list_kb(products: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        status = "✅" if p.get("active") else "❌"
        kb.add(InlineKeyboardButton(
            f"{status} {p['name']}",
            callback_data=f"admprod:view:{p['_id']}",
        ))
    kb.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="adm:panel"))
    return kb


def admin_product_actions_kb(product_id: str, is_active: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    toggle_label = "🔴 Disable" if is_active else "🟢 Enable"
    toggle_cb = f"admprod:toggle:{product_id}"
    
    kb.add(
        InlineKeyboardButton("📝 Edit Name", callback_data=f"admprod:edit_name:{product_id}"),
        InlineKeyboardButton("📝 Edit Desc", callback_data=f"admprod:edit_desc:{product_id}"),
    )
    kb.add(
        InlineKeyboardButton("💰 Edit Cost", callback_data=f"admprod:edit_cost:{product_id}"),
        InlineKeyboardButton("📦 Add Stock", callback_data=f"admprod:addstock:{product_id}"),
    )
    kb.add(
        InlineKeyboardButton(toggle_label, callback_data=toggle_cb),
        InlineKeyboardButton("🗑 Delete", callback_data=f"admprod:delete:{product_id}"),
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="adm:manage_products"))
    return kb
