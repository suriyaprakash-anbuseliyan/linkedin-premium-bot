"""
config.py
─────────
Central configuration for the LinkedIn Premium Store Bot.
Loads environment variables via python-dotenv and exposes them
as module-level constants so every other module can simply
``from config import …``.
"""

import os
import sys
import logging
from dotenv import load_dotenv
import socket

# Force IPv4 because Oracle IPv6 is sometimes unreachable
def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return socket._original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

if not hasattr(socket, '_original_getaddrinfo'):
    socket._original_getaddrinfo = socket.getaddrinfo
    socket.getaddrinfo = _getaddrinfo_ipv4
# ── Load .env ────────────────────────────────────────────────────────────
load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

# ── Required variables ───────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
MONGO_URI: str = os.getenv("MONGO_URI", "")

if not BOT_TOKEN:
    logger.critical("BOT_TOKEN is missing from environment variables.")
    sys.exit(1)

if not MONGO_URI:
    logger.critical("MONGO_URI is missing from environment variables.")
    sys.exit(1)

# ── Admin ────────────────────────────────────────────────────────────────
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "6073741045"))

# ── Mandatory-join channel/group ─────────────────────────────────────────
REQUIRED_CHANNEL_USERNAME: str = os.getenv("REQUIRED_CHANNEL_USERNAME", "")
REQUIRED_CHANNEL_LINK: str = os.getenv("REQUIRED_CHANNEL_LINK", "")

# ── Payment details ─────────────────────────────────────────────────────
UPI_ID: str = os.getenv("UPI_ID", "crackott@ybl")
UPI_NAME: str = os.getenv("UPI_NAME", "SURIYAPRAKASH")
BINANCE_UID: str = os.getenv("BINANCE_UID", "1097309535")

RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")

BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")

# ── Bot username (used for referral links) ───────────────────────────────
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "linkedinpremiumstore_bot")

# ── Credit packages  (credits → price in INR for UPI / USDT for Binance) ─
CREDIT_PACKAGES: dict[int, dict] = {
    2:  {"inr": 106,  "usdt": 1.0},
    4:  {"inr": 212,  "usdt": 2.0},
    6:  {"inr": 318,  "usdt": 3.0},
    8:  {"inr": 424,  "usdt": 4.0},
    10: {"inr": 530,  "usdt": 5.0},
    12: {"inr": 636,  "usdt": 6.0},
    14: {"inr": 742,  "usdt": 7.0},
    16: {"inr": 848,  "usdt": 8.0},
    18: {"inr": 954,  "usdt": 9.0},
    20: {"inr": 1060, "usdt": 10.0},
}

# ── Referral settings ───────────────────────────────────────────────────
REFERRALS_PER_CREDIT: int = 3          # every N referrals → +1 credit
MAX_FREE_REFERRAL_CREDITS: int = 10    # cap on free credits from referrals

# ── Database name ────────────────────────────────────────────────────────
DB_NAME: str = os.getenv("DB_NAME", "linkedin_premium_bot")
