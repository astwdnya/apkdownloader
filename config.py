"""
Configuration loader for the Telegram APK Bot (Uptodown version).
Reads environment variables from .env file (or system environment).
"""
import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# --- Telegram (Telethon) ---
# api_id and api_hash from https://my.telegram.org → API Development Tools
API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "").strip()

# Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Session file name (Telethon will create <name>.session)
SESSION_NAME = os.getenv("SESSION_NAME", "apk_bot").strip()

# --- Access control ---
_allowed_raw = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS = set()
if _allowed_raw:
    for part in _allowed_raw.split(","):
        part = part.strip()
        if part.isdigit():
            ALLOWED_USER_IDS.add(int(part))

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Uptodown settings ---
# Use the English site by default. Change to 'es', 'de', 'fr', etc. if you prefer.
UPTODOWN_LANG = os.getenv("UPTODOWN_LANG", "en").strip().lower()

# Max number of versions to show in inline buttons
MAX_VERSIONS = int(os.getenv("MAX_VERSIONS", "8"))


def is_configured() -> bool:
    """Quick check that all required env vars are present."""
    return bool(API_ID and API_HASH and BOT_TOKEN)
