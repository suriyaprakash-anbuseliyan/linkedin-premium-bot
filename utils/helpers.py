"""
utils/helpers.py
────────────────
Shared helper functions: referral codes, admin checks,
channel membership verification, date formatting.
"""

import string
import random
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import telebot
from config import ADMIN_ID, REQUIRED_CHANNEL_USERNAME, logger


def generate_referral_code(length: int = 8) -> str:
    """Return a random alphanumeric referral code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def is_admin(user_id: int) -> bool:
    """Check whether a Telegram user is the bot admin."""
    return user_id == ADMIN_ID


def announce_event(bot: telebot.TeleBot, title: str, user_id: int, credits_remaining: int, status: str):
    """Send an announcement to the configured channel."""
    if not REQUIRED_CHANNEL_USERNAME:
        return
        
    from config import BOT_USERNAME
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Format matches the user's requested style
    text = (
        f"✅ <b>{title}</b>\n\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"🎫 Credit Remaining: <b>{credits_remaining}</b>\n"
        f"📝 Status: <b>{status}</b>\n"
        f"⏰ Time: {now}\n\n"
        f"🤖 Bot: @{BOT_USERNAME}"
    )
    
    try:
        # Strip `@` just in case the env var included it, then prefix it back
        clean_channel = REQUIRED_CHANNEL_USERNAME.lstrip('@')
        bot.send_message(
            chat_id=f"@{clean_channel}",
            text=text,
            parse_mode="HTML"
        )
    except Exception as exc:
        logger.warning("Failed to send announcement to channel: %s", exc)


def check_membership(bot: telebot.TeleBot, user_id: int) -> bool:
    """
    Return True if the user is a member of the required channel/group.
    If REQUIRED_CHANNEL_USERNAME is not configured, everyone passes.
    """
    if not REQUIRED_CHANNEL_USERNAME:
        return True  # no channel configured → skip check
    try:
        member = bot.get_chat_member(
            chat_id=f"@{REQUIRED_CHANNEL_USERNAME}",
            user_id=user_id,
        )
        return member.status in ("member", "administrator", "creator")
    except telebot.apihelper.ApiTelegramException as exc:
        logger.warning("Membership check failed for %s: %s", user_id, exc)
        return False


def format_datetime(dt: datetime | None) -> str:
    """Human-friendly date/time string."""
    if dt is None:
        return "N/A"
    return dt.strftime("%d %b %Y, %H:%M UTC")


def extract_all_linkedin_links(text: str) -> list[str]:
    """Extract all valid LinkedIn premium URLs from raw text."""
    # Look for http or https linkedin.com/premium/redeem links
    pattern = r'(https?://(?:www\.)?linkedin\.com/premium/redeem/[^\s]+)'
    matches = re.findall(pattern, text)
    return matches


def validate_linkedin_link(url: str) -> bool:
    """
    Validate that a URL is a genuine LinkedIn Premium referral link.
    Required format:
        https://www.linkedin.com/premium/redeem/?...&coupon=XXXXX&...
    Must:
      1. Be a linkedin.com domain
      2. Have /premium/redeem/ in the path
      3. Contain a non-empty 'coupon' query parameter
    """
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Must be https and linkedin.com
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    if not parsed.hostname.endswith("linkedin.com"):
        return False

    # Path must contain /premium/redeem/
    if "/premium/redeem" not in parsed.path:
        return False

    # Must have a non-empty coupon parameter
    params = parse_qs(parsed.query)
    coupon_values = params.get("coupon", [])
    if not coupon_values or not coupon_values[0].strip():
        return False

    return True


def get_payment_settings() -> dict:
    """
    Get current payment settings. DB values override .env defaults.
    Returns dict with keys: upi_id, upi_name, binance_uid
    """
    from database import get_setting
    from config import UPI_ID, UPI_NAME, BINANCE_UID

    return {
        "upi_id": get_setting("upi_id", UPI_ID),
        "upi_name": get_setting("upi_name", UPI_NAME),
        "binance_uid": get_setting("binance_uid", BINANCE_UID),
    }


def get_credit_packages() -> dict[int, dict]:
    """
    Get current credit packages pricing. DB values override config.py defaults.
    """
    from database import get_setting
    from config import CREDIT_PACKAGES as default_packages

    packages = {}
    for qty, defaults in default_packages.items():
        inr_val = get_setting(f"pkg_{qty}_inr", "")
        usdt_val = get_setting(f"pkg_{qty}_usdt", "")

        try:
            inr = float(inr_val) if inr_val else defaults["inr"]
            inr = int(inr) if inr == int(inr) else inr
        except ValueError:
            inr = defaults["inr"]

        try:
            usdt = float(usdt_val) if usdt_val else defaults["usdt"]
        except ValueError:
            usdt = defaults["usdt"]

        packages[qty] = {"inr": inr, "usdt": usdt}
    return packages


# ── UI CACHE & HELPERS ────────────────────────────────────────────────────────

_ui_cache = None

def get_ui_buttons() -> dict:
    """Fetch UI settings from the database and cache them."""
    global _ui_cache
    if _ui_cache is None:
        from database import get_setting
        _ui_cache = get_setting("ui_buttons", {})
    return _ui_cache

def clear_ui_cache():
    """Clear the UI cache so it fetches fresh data from DB on next request."""
    global _ui_cache
    _ui_cache = None

def btn_config(key: str, default_text: str, default_emoji: str = "", default_style: str = None) -> dict:
    """
    Returns a kwargs dictionary to unpack into InlineKeyboardButton.
    E.g. **btn_config("menu_buy", "BUY", "🛒", "success")
    """
    ui = get_ui_buttons()
    cfg = ui.get(key, {})
    
    emoji_id = cfg.get("emoji_id")
    
    # If admin set custom text, use it exactly as provided.
    if "text" in cfg:
        final_text = cfg["text"]
    else:
        # If they use a custom emoji, drop the default emoji so they don't double up.
        if emoji_id and default_emoji:
            final_text = default_text
        elif default_emoji:
            final_text = f"{default_emoji} {default_text}"
        else:
            final_text = default_text
            
    btn_kwargs = {
        "text": final_text
    }
    
    style = cfg.get("style", default_style)
    if style and style != "none":
        btn_kwargs["style"] = style
        
    if emoji_id:
        btn_kwargs["icon_custom_emoji_id"] = emoji_id
        
    return btn_kwargs
