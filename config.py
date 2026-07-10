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
UPI_QR_PATH: str = os.getenv("UPI_QR_PATH", "assets/upi_qr.jpg")
USD_TO_INR_RATE: float = float(os.getenv("USD_TO_INR_RATE", "100.0"))
BINANCE_UID: str = os.getenv("BINANCE_UID", "1097309535")
BEP20_ADDRESS: str = os.getenv("BEP20_ADDRESS", "0xYourAddressHere")
BEP20_QR_PATH: str = os.getenv("BEP20_QR_PATH", "assets/bep20_qr.jpg")

BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")

# ── Bot username (used for referral links) ───────────────────────────────
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "linkedinpremiumstore_bot")

# ── Referral settings ───────────────────────────────────────────────────
REFERRAL_BONUS_USD: float = float(os.getenv("REFERRAL_BONUS_USD", "0.5"))
MAX_REFERRAL_BONUS_USD: float = float(os.getenv("MAX_REFERRAL_BONUS_USD", "5.0"))

# ── Database name ────────────────────────────────────────────────────────
DB_NAME: str = os.getenv("DB_NAME", "linkedin_premium_bot")
