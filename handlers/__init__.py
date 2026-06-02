"""
handlers/__init__.py
────────────────────
Register all handler groups with the bot instance.
Import order matters: general handlers first, then specific ones.
"""

from handlers.start import register as register_start
from handlers.menu import register as register_menu
from handlers.products import register as register_products
from handlers.credits import register as register_credits
from handlers.profile import register as register_profile
from handlers.referral import register as register_referral
from handlers.orders import register as register_orders
from handlers.support import register as register_support
from handlers.admin import register as register_admin
from handlers.gift_codes import register as register_gift_codes
from handlers.states_handler import register as register_states


def register_all_handlers(bot) -> None:
    """Attach every handler group to *bot*."""
    register_start(bot)
    register_menu(bot)
    register_products(bot)
    register_credits(bot)
    register_profile(bot)
    register_referral(bot)
    register_orders(bot)
    register_support(bot)
    register_admin(bot)
    register_gift_codes(bot)
    # States handler MUST be last – it acts as a catch-all for text
    register_states(bot)
