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
    Membership check is currently disabled per user request.
    """
    return True


def format_datetime(dt: datetime | None) -> str:
    """Human-friendly date/time string."""
    if dt is None:
        return "N/A"
    return dt.strftime("%d %b %Y, %H:%M UTC")


def extract_all_links(text: str) -> list[str]:
    """Extract stock items from raw text. They can be URLs or any text strings."""
    import re
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        
        # If the line contains http/https, extract the URLs
        if "http://" in line or "https://" in line:
            pattern = r'(https?://[^\s]+)'
            matches = re.findall(pattern, line)
            if matches:
                items.extend(matches)
            else:
                items.append(line)
        else:
            # It's a regular string (like a coupon code, username/password)
            # Take the whole line as a single stock item
            items.append(line)
    return items


def validate_link(url: str) -> bool:
    """
    Validate that a stock item is valid.
    We now allow ANY non-empty string.
    """
    return bool(url.strip())


def get_referral_settings() -> dict:
    """
    Get current referral program settings from DB.
    Returns dict with keys: is_enabled, points_per_credit, max_free_credits
    """
    from database import is_referral_enabled, get_referral_config
    config = get_referral_config()
    return {
        "is_enabled": is_referral_enabled(),
        "points_per_credit": config["points_per_credit"],
        "max_free_credits": config["max_free_credits"],
    }


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
