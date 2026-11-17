from __future__ import annotations

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


def is_account_block(lines: list[str]) -> bool:
    """
    Detect whether a multi-line block represents a single account/service credential
    (e.g., Mail, OTP, Profile, PIN, Password, etc.) rather than a list of distinct links.
    """
    if len(lines) <= 1:
        return False
    # If every line is a standalone URL, it is a list of links, not an account block
    if all(re.match(r"^https?://\S+$", l.strip()) for l in lines if l.strip()):
        return False
    # If every line is a single word/code with no spaces and no URLs, it's a list of codes
    if all(" " not in l.strip() and not re.search(r"https?://", l) for l in lines if l.strip()):
        return False

    account_keywords = {
        "mail", "email", "otp", "profile", "bin", "pin", "pass", "password",
        "account", "user", "username", "login", "credentials", "vaultapp"
    }
    has_kw = any(any(kw in l.lower() for kw in account_keywords) for l in lines)
    has_labels = any(re.search(r"^[A-Za-z0-9_\s]{2,20}\s*:\s*\S+", l) for l in lines)
    return has_kw or has_labels


def extract_all_links(text: str) -> list[str]:
    """
    Extract stock items from raw text. They can be URLs, accounts, or any text strings.
    
    1. If the text contains '---' (or '===') separators, each block between separators
       is treated as a SINGLE multi-line stock item.
    2. If the text has blocks separated by blank lines (\\n\\s*\\n), check if the blocks
       represent multi-line accounts. If so, each block is 1 stock item.
    3. If the entire text has no separator or blank lines, but has multiple lines
       describing an account (e.g. Mail, OTP, Profile, BIN/PIN), the whole block is 1 stock item.
    4. Otherwise (traditional single-line items like LinkedIn links, coupon codes):
       Each line is a separate item.
    """
    text = text.strip()
    if not text:
        return []

    # 1. Separator line: --- or === or ___
    if re.search(r"(?:^|\n)\s*[-=_]{3,}\s*(?:\n|$)", text):
        blocks = re.split(r"(?:^|\n)\s*[-=_]{3,}\s*(?:\n|$)", text)
        items = [b.strip() for b in blocks if b.strip()]
        if items:
            return items

    # 2. Double-newline blocks
    blocks = re.split(r"\n\s*\n+", text)
    if len(blocks) > 1:
        any_multi = any(is_account_block(b.strip().splitlines()) for b in blocks if b.strip())
        if any_multi:
            items = []
            for b in blocks:
                b = b.strip()
                if not b:
                    continue
                lines = [l.strip() for l in b.splitlines() if l.strip()]
                if is_account_block(lines):
                    items.append(b)
                else:
                    items.extend(lines)
            return items

    # 3. Single block with multiple lines
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if is_account_block(lines):
        return [text]

    # 4. Standard single-line items (URLs or single-line codes)
    items = []
    for line in lines:
        if "http://" in line or "https://" in line:
            pattern = r'(https?://[^\s]+)'
            matches = re.findall(pattern, line)
            if matches:
                items.extend(matches)
            else:
                items.append(line)
        else:
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


def calculate_bulk_price(qty: int, default_price: float, bulk_text: str) -> float:
    """
    Parse bulk discount text to find the appropriate unit price for a given quantity.
    Format examples:
    1-9 codes -> $2.00 each
    10+ -> $1.90
    """
    if not bulk_text or not bulk_text.strip():
        return default_price

    try:
        import re
        for line in bulk_text.splitlines():
            line = line.strip()
            if not line:
                continue
                
            qty_match = re.match(r'^(\d+)\s*(?:-\s*(\d+)|\+)', line)
            if not qty_match:
                continue
                
            min_q = int(qty_match.group(1))
            max_q = int(qty_match.group(2)) if qty_match.group(2) else float('inf')
            
            # Find all numbers in the line (e.g. 1.90, 2)
            numbers = re.findall(r'\d+\.\d+|\d+', line)
            if not numbers:
                continue
            
            # Assume the last number in the line is the price
            price = float(numbers[-1])
            
            if min_q <= qty <= max_q:
                return price
                
        return default_price
    except Exception as e:
        logger.error(f"Error parsing bulk price: {e}")
        return default_price
