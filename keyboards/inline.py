"""
keyboards/inline.py
───────────────────
Every inline keyboard the bot uses, in one place.
Callback data uses a simple prefix convention:
    section:action:param
"""

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import REQUIRED_CHANNEL_LINK
from utils.helpers import get_credit_packages, btn_config


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  MANDATORY JOIN                                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

def join_channel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(**btn_config("join_channel", "Join Channel", "📢"), url=REQUIRED_CHANNEL_LINK),
        InlineKeyboardButton(**btn_config("check_join", "I've Joined", "✅", "success"), callback_data="check_join"),
    )
    return kb


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  MAIN MENU                                                         ║
# ╚══════════════════════════════════════════════════════════════════════╝

def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton(**btn_config("menu_buy", "BUY", "🛒", "success"), callback_data="menu:buy"))
    kb.add(
        InlineKeyboardButton(**btn_config("menu_credits", "Add Credits", "💰", "primary"), callback_data="menu:credits"),
        InlineKeyboardButton(**btn_config("menu_balance", "Balance", "💳"), callback_data="menu:balance"),
    )
    kb.add(
        InlineKeyboardButton(**btn_config("menu_profile", "Profile", "👤"), callback_data="menu:profile"),
        InlineKeyboardButton(**btn_config("menu_referral", "Refer/Earn", "🎁", "success"), callback_data="menu:referral"),
    )
    kb.add(
        InlineKeyboardButton(**btn_config("menu_orders", "Orders", "📜"), callback_data="menu:orders"),
        InlineKeyboardButton(**btn_config("menu_giftcode", "Redeem Gift Code", "🎟"), callback_data="menu:giftcode"),
    )
    kb.add(
        InlineKeyboardButton(**btn_config("menu_support", "Support", "📞"), callback_data="menu:support"),
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
        
        btn_kwargs = btn_config(f"prod_btn_{p['_id']}", p['name'])
        # Re-attach the dynamic stock and price
        btn_kwargs['text'] = f"{btn_kwargs['text']} ({stock})  —  {p['credit_cost']} credit(s)"
        btn_kwargs['callback_data'] = f"prod:view:{p['_id']}"
        
        # Override style based on stock availability
        if stock > 0:
            btn_kwargs['style'] = 'success'
        else:
            btn_kwargs['style'] = 'danger'
        
        kb.add(InlineKeyboardButton(**btn_kwargs))
    kb.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main"))
    return kb


def product_detail_kb(product_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(**btn_config("prod_buy", "Purchase", "🛒", "success"), callback_data=f"prod:buy:{product_id}"),
        InlineKeyboardButton(**btn_config("prod_back", "Back to Products", "🔙"), callback_data="menu:buy"),
    )
    return kb


def confirm_purchase_kb(product_id: str, qty: int = 1) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(**btn_config("prod_confirm", "Confirm", "✅", "success"), callback_data=f"prod:confirm:{product_id}:{qty}"),
        InlineKeyboardButton(**btn_config("prod_cancel", "Cancel", "❌", "danger"), callback_data="menu:buy"),
    )
    return kb


def purchase_success_qr_kb(qr_order_id: str) -> InlineKeyboardMarkup:
    """Keyboard shown after successful purchase with Upload QR option."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📤 Upload QR", callback_data=f"qr:upload:{qr_order_id}"),
        InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main"),
    )
    return kb


def admin_qr_review_kb(qr_order_id: str) -> InlineKeyboardMarkup:
    """Admin keyboard for reviewing a QR upload."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("✅ Payment Approved", callback_data=f"admqr:approve:{qr_order_id}"),
        InlineKeyboardButton("❌ Rejected / Refunded", callback_data=f"admqr:reject:{qr_order_id}"),
        InlineKeyboardButton("🔄 Reupload QR", callback_data=f"admqr:reupload:{qr_order_id}"),
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

def admin_panel_kb(is_maintenance: bool = False, is_referral: bool = True) -> InlineKeyboardMarkup:
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
    kb.add(
        InlineKeyboardButton("🔍 Search Link/Code", callback_data="adm:search"),
        InlineKeyboardButton("🎨 UI Settings", callback_data="adm:ui_settings"),
    )
    
    maint_label = "🟢 Maintenance: ON" if is_maintenance else "🔴 Maintenance: OFF"
    kb.add(
        InlineKeyboardButton(maint_label, callback_data="adm:toggle_maintenance"),
        InlineKeyboardButton("🎁 Generate Gift Code", callback_data="adm:gen_gift_code"),
    )
    
    ref_label = "🟢 Referral: ON" if is_referral else "🔴 Referral: OFF"
    kb.add(
        InlineKeyboardButton(ref_label, callback_data="adm:toggle_referral"),
        InlineKeyboardButton("⚙️ Referral Settings", callback_data="adm:referral_settings"),
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
        
    kb.add(
        InlineKeyboardButton("✉️ Send Message", callback_data=f"admuser:msg:{user_id}"),
        InlineKeyboardButton("🗑️ Delete User", callback_data=f"admuser:delete:{user_id}")
    )
    kb.add(InlineKeyboardButton("🔙 Back to Search", callback_data="adm:users"))
    return kb


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ADMIN UI SETTINGS                                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

def admin_ui_button_list_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    buttons_to_edit = [
        ("menu_buy", "Main Menu: BUY"),
        ("menu_credits", "Main Menu: Add Credits"),
        ("menu_balance", "Main Menu: Balance"),
        ("menu_profile", "Main Menu: Profile"),
        ("menu_referral", "Main Menu: Refer/Earn"),
        ("menu_orders", "Main Menu: Orders"),
        ("menu_giftcode", "Main Menu: Gift Code"),
        ("menu_support", "Main Menu: Support"),
        ("join_channel", "Join Channel: Link"),
        ("check_join", "Join Channel: I've Joined"),
        ("prod_buy", "Product detail: Purchase"),
        ("prod_confirm", "Product confirm: Confirm"),
        ("prod_cancel", "Product confirm: Cancel"),
    ]
    for key, label in buttons_to_edit:
        kb.add(InlineKeyboardButton(f"🎨 {label}", callback_data=f"admui:edit:{key}"))
        
    from database import get_all_products
    products = get_all_products()
    for p in products:
        kb.add(InlineKeyboardButton(f"🎨 Product List: {p['name']}", callback_data=f"admui:edit:prod_btn_{p['_id']}"))
        
    kb.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="adm:panel"))
    return kb


def admin_ui_edit_kb(button_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    if not button_key.startswith("prod_btn_"):
        kb.add(InlineKeyboardButton("✏️ Edit Text", callback_data=f"admui:settext:{button_key}"))
    kb.add(InlineKeyboardButton("🎨 Edit Color Style", callback_data=f"admui:style:{button_key}"))
    kb.add(InlineKeyboardButton("✨ Edit Custom Emoji ID", callback_data=f"admui:setemoji:{button_key}"))
    kb.add(InlineKeyboardButton("🗑️ Remove Emoji", callback_data=f"admui:rmemoji:{button_key}"))
    kb.add(InlineKeyboardButton("🔙 Back to UI List", callback_data="adm:ui_settings"))
    return kb


def admin_ui_style_kb(button_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🟦 Primary (Blue)", callback_data=f"admui:setstyle:{button_key}:primary"),
        InlineKeyboardButton("🟩 Success (Green)", callback_data=f"admui:setstyle:{button_key}:success"),
        InlineKeyboardButton("🟥 Danger (Red)", callback_data=f"admui:setstyle:{button_key}:danger"),
        InlineKeyboardButton("⬛ Default (Clear)", callback_data=f"admui:setstyle:{button_key}:none"),
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"admui:edit:{button_key}"))
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


def referral_settings_kb(ref_config: dict, is_conversion_on: bool = True) -> InlineKeyboardMarkup:
    """Keyboard for editing referral conversion settings."""
    kb = InlineKeyboardMarkup(row_width=1)
    
    conv_label = "🟢 Credit Conversion: ON" if is_conversion_on else "🔴 Credit Conversion: OFF"
    kb.add(
        InlineKeyboardButton(conv_label, callback_data="adm:toggle_conversion"),
    )
    kb.add(
        InlineKeyboardButton(
            f"🔢 Points per Credit: {ref_config['points_per_credit']}",
            callback_data="admset:referral_points_per_credit",
        ),
        InlineKeyboardButton(
            f"🎯 Max Free Credits: {ref_config['max_free_credits']}",
            callback_data="admset:referral_max_free_credits",
        ),
    )
    kb.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="adm:panel"))
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


def admin_product_actions_kb(product_id: str, is_active: bool, is_numerical: bool = False, requires_qr: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    toggle_label = "🔴 Disable" if is_active else "🟢 Enable"
    toggle_cb = f"admprod:toggle:{product_id}"
    qr_label = "🔴 QR Upload: OFF" if not requires_qr else "🟢 QR Upload: ON"
    
    kb.add(
        InlineKeyboardButton("📝 Edit Name", callback_data=f"admprod:edit_name:{product_id}"),
        InlineKeyboardButton("📝 Edit Desc", callback_data=f"admprod:edit_desc:{product_id}"),
    )
    
    # Stock and switch toggle
    if is_numerical:
        kb.add(
            InlineKeyboardButton("💰 Edit Cost", callback_data=f"admprod:edit_cost:{product_id}"),
            InlineKeyboardButton("✏️ Set Stock Limit", callback_data=f"admprod:set_num_stock:{product_id}"),
        )
        kb.add(InlineKeyboardButton("🔁 Switch to Links", callback_data=f"admprod:toggle_numerical:{product_id}"))
    else:
        kb.add(
            InlineKeyboardButton("💰 Edit Cost", callback_data=f"admprod:edit_cost:{product_id}"),
            InlineKeyboardButton("📦 Add Stock", callback_data=f"admprod:addstock:{product_id}"),
        )
        kb.add(InlineKeyboardButton("🔁 Switch to Numerical", callback_data=f"admprod:toggle_numerical:{product_id}"))
        
    kb.add(
        InlineKeyboardButton(toggle_label, callback_data=toggle_cb),
        InlineKeyboardButton("🗑 Delete", callback_data=f"admprod:delete:{product_id}"),
    )
    kb.add(InlineKeyboardButton(qr_label, callback_data=f"admprod:toggle_qr:{product_id}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="adm:manage_products"))
    return kb

def admin_stock_type_kb() -> InlineKeyboardMarkup:
    """Keyboard for selecting stock type during product creation."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔗 Links / Coupons", callback_data="admprod:stock_type:links"),
        InlineKeyboardButton("🔢 Numerical Service", callback_data="admprod:stock_type:numerical"),
        InlineKeyboardButton("🔙 Cancel", callback_data="adm:panel")
    )
    return kb
