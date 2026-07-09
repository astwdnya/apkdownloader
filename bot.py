"""
bot.py (Telethon + Uptodown)
============================
Telegram bot built on Telethon (MTProto) that downloads APKs from
uptodown.com — no Google account, no AAS token, no auth required.

Supported inputs:
  * https://play.google.com/store/apps/details?id=com.whatsapp
        -> bot extracts the app name from Play Store page title,
           searches Uptodown, shows result list
  * https://whatsapp-messenger.en.uptodown.com/android
        -> bot fetches the app directly
  * bare package name like  com.whatsapp
        -> bot searches Uptodown for the package name
  * /search <query>
        -> explicit search on Uptodown

Flow:
  1. User sends any of the above.
  2. Bot shows a list of matching apps (inline glass buttons).
  3. User taps an app -> bot fetches app info + available versions.
  4. Bot shows version buttons (latest + older versions).
  5. User taps a version -> bot downloads the APK and sends it back.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
from typing import Any, Dict, List, Optional

import requests
from telethon import TelegramClient, events
from telethon.tl.custom import Button

from config import (
    ALLOWED_USER_IDS,
    API_HASH,
    API_ID,
    BOT_TOKEN,
    LOG_LEVEL,
    MAX_VERSIONS,
    SESSION_NAME,
    is_configured,
)
from uptodown_downloader import UptodownDownloader

# --------------------------------------------------------------------------- #
#  Logging
# --------------------------------------------------------------------------- #
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Telethon client
# --------------------------------------------------------------------------- #
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# --------------------------------------------------------------------------- #
#  In-memory session store
#  Structure: { user_id: { "search": { idx: app }, "<session_id>": app_info } }
# --------------------------------------------------------------------------- #
_user_sessions: Dict[int, Dict[str, Any]] = {}


def _make_session_id(slug: str, version_count: int) -> str:
    """Build a session key (kept short for Telegram callback_data limit)."""
    # callback_data max is 64 bytes; "dl|" + session + "|" + version_id
    # so session can be up to ~50 bytes
    raw = slug[:50]
    return raw


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


def detect_play_store_url(text: str) -> Optional[str]:
    """Return the package name if text is a Play Store URL, else None."""
    m = re.search(
        r"play\.google\.com/store/apps/details\?(?:[^#\s]*&)?id=([a-zA-Z0-9_.]+)",
        text or "",
    )
    return m.group(1) if m else None


def detect_uptodown_url(text: str) -> Optional[str]:
    """Return the Uptodown URL if text contains one, else None."""
    m = re.search(
        r"https?://([^.]+)\.[a-z]{2}\.uptodown\.com/android[^\s]*",
        text or "",
    )
    return m.group(0) if m else None


def detect_bare_package(text: str) -> Optional[str]:
    """Return the package name if text is a bare Java package name."""
    text = (text or "").strip()
    if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z0-9_]+)+", text):
        return text
    return None


def fetch_play_store_app_name(package: str) -> str:
    """Fetch the Play Store page and extract the app title.
    No authentication needed — just an HTTP GET."""
    url = f"https://play.google.com/store/apps/details?id={package}&hl=en"
    try:
        r = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36"
                ),
            },
        )
        if r.status_code != 200:
            return package
        # The <title> tag usually contains "AppName - Apps on Google Play"
        m = re.search(r"<title>([^<]+)</title>", r.text)
        if m:
            title = m.group(1).split(" - ")[0].split(" – ")[0].strip()
            if title and "Apps on Google Play" not in title:
                return title
        # Fallback: og:title meta
        m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', r.text)
        if m:
            return m.group(1).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_play_store_app_name failed: %s", exc)
    return package


def md_escape(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"([_*`\[])", r"\\\1", text)


# --------------------------------------------------------------------------- #
#  Inline keyboards (the "glass buttons")
# --------------------------------------------------------------------------- #
def build_search_buttons(apps: List[Dict[str, Any]], user_id: int) -> List[List[Button]]:
    """Build the inline keyboard for Uptodown search results."""
    search_dict: Dict[str, Dict[str, Any]] = {}
    rows: List[List[Button]] = []
    for i, app in enumerate(apps[:10]):
        key = str(i)
        search_dict[key] = app
        title = app.get("title", "unknown")[:40]
        dev = (app.get("developer") or "")[:20]
        label = f"📱 {title}" + (f"  —  {dev}" if dev else "")
        rows.append([Button.inline(label, data=f"srch|{key}".encode())])
    _user_sessions.setdefault(user_id, {})["search"] = search_dict
    return rows


def build_version_buttons(app_info: Dict[str, Any], user_id: int) -> List[List[Button]]:
    """Build inline keyboard with one button per available version."""
    slug = app_info["slug"]
    session_id = _make_session_id(slug, len(app_info.get("versions", [])))
    _user_sessions.setdefault(user_id, {})[session_id] = app_info

    rows: List[List[Button]] = []

    versions = app_info.get("versions", [])[:MAX_VERSIONS]
    for v in versions:
        vname = v.get("version_name") or "v.?"
        size = v.get("size") or ""
        date = v.get("date") or ""
        is_latest = v.get("is_latest", False)
        badge = "🆕 " if is_latest else "📅 "
        label_parts = [f"{badge}{vname}"]
        if size:
            label_parts.append(size)
        if date:
            label_parts.append(date)
        label = "  •  ".join(label_parts)
        # Truncate label to fit Telegram's 64-byte UTF-8 limit on button text
        label = label[:200]
        callback = f"dl|{session_id}|{v['version_id']}"
        callback = callback.encode("utf-8")[:64].decode("utf-8", errors="ignore")
        rows.append([Button.inline(label, data=callback.encode())])

    # Info row
    info_text = (
        f"ℹ️ این APK یونیورسال است و روی تمام معماری‌ها "
        f"(arm64-v8a, armeabi-v7a, x86_64, x86) کار می‌کند"
    )
    rows.append([Button.inline("📦 APK یونیورسال (همه معماری‌ها)", data=b"info|noop")])

    # Back-to-search button
    rows.append([Button.inline("🔍 جستجوی دوباره", data=b"back|search")])

    return rows


# --------------------------------------------------------------------------- #
#  Core flow: process a Uptodown app
# --------------------------------------------------------------------------- #
async def process_app(event, app_url_or_slug: str, user_id: int) -> None:
    """Fetch app info from Uptodown and reply with version buttons."""
    status = await event.respond("⏳ در حال دریافت اطلاعات برنامه از Uptodown...")

    loop = asyncio.get_event_loop()
    app_info = await loop.run_in_executor(
        None, lambda: UptodownDownloader.get_instance().get_app_info(app_url_or_slug)
    )

    if not app_info or not app_info.get("versions"):
        await status.edit(
            "❌ برنامه پیدا نشد یا هیچ نسخه‌ای در دسترس نیست.\n"
            "لطفاً آدرس Uptodown یا نام برنامه را بررسی کنید."
        )
        return

    text = (
        f"📱 **{app_info['title']}**\n"
        + (f"👤 توسعه‌دهنده: {md_escape(app_info['developer'])}\n" if app_info.get("developer") else "")
        + f"🔗 {app_info.get('url', '')}\n\n"
        f"👇 برای دانلود، نسخه مورد نظر را انتخاب کنید:"
    )
    buttons = build_version_buttons(app_info, user_id)
    await status.edit(text, buttons=buttons, link_preview=False)


# --------------------------------------------------------------------------- #
#  Search flow
# --------------------------------------------------------------------------- #
async def do_search(event, query: str, user_id: int) -> None:
    status = await event.respond(f"🔍 در حال جستجو در Uptodown برای «{query}»...")

    loop = asyncio.get_event_loop()
    apps = await loop.run_in_executor(
        None, lambda: UptodownDownloader.get_instance().search(query)
    )

    if not apps:
        await status.edit(
            "❌ برنامه‌ای پیدا نشد. لطفاً نام دقیق‌تر یا انگلیسی نام برنامه را امتحان کنید."
        )
        return

    buttons = build_search_buttons(apps, user_id)
    await status.edit(
        f"🔍 **نتایج جستجو برای «{query}»:**\n\n"
        f"برای مشاهده نسخه‌ها روی برنامه ضربه بزنید:",
        buttons=buttons,
        link_preview=False,
    )


# --------------------------------------------------------------------------- #
#  Command handlers
# --------------------------------------------------------------------------- #
@client.on(events.NewMessage(pattern=r"^/start"))
async def start_handler(event: events.NewMessage.Event) -> None:
    if not is_authorized(event.sender_id):
        await event.respond("⛔️ شما اجازه استفاده از این ربات را ندارید.")
        return

    text = (
        "👋 **به ربات دانلود APK از Uptodown خوش آمدید!**\n\n"
        "🔍 **قابلیت‌ها:**\n"
        "• یک لینک گوگل‌پلی بفرستید تا ربات آن را در Uptodown پیدا کند\n"
        "• یک لینک مستقیم Uptodown بفرستید\n"
        "• یک نام پکیج (مثل `com.whatsapp`) بفرستید\n"
        "• با `/search <نام برنامه>` جستجو کنید\n"
        "• روی دکمه‌های شیشه‌ای ضربه بزنید تا نسخه مورد نظر را دانلود کنید\n\n"
        "📲 **معماری‌های پشتیبانی شده:**\n"
        "  APK یونیورسال — روی arm64-v8a, armeabi-v7a, x86_64, x86 کار می‌کند\n\n"
        "💡 **مثال:**\n"
        "  `https://play.google.com/store/apps/details?id=com.whatsapp`\n"
        "  `https://whatsapp-messenger.en.uptodown.com/android`\n"
        "  `com.whatsapp`\n"
        "  `/search whatsapp`"
    )
    await event.respond(text, link_preview=False)


@client.on(events.NewMessage(pattern=r"^/help"))
async def help_handler(event: events.NewMessage.Event) -> None:
    await start_handler(event)


@client.on(events.NewMessage(pattern=r"^/search(?:\s+(.+))?"))
async def search_command(event: events.NewMessage.Event) -> None:
    if not is_authorized(event.sender_id):
        return

    match = event.pattern_match
    query = (match.group(1) or "").strip()
    if not query:
        await event.respond(
            "❌ لطفاً نام برنامه را وارد کنید.\n"
            "مثال: `/search whatsapp`",
            link_preview=False,
        )
        return

    await do_search(event, query, event.sender_id)


# --------------------------------------------------------------------------- #
#  Plain message handler
# --------------------------------------------------------------------------- #
@client.on(events.NewMessage(
    func=lambda e: e.is_private and bool(e.text) and not e.text.startswith("/")
))
async def message_handler(event: events.NewMessage.Event) -> None:
    if not is_authorized(event.sender_id):
        return

    text = event.text or ""
    user_id = event.sender_id

    # 1) Uptodown URL -> fetch app directly
    uptodown_url = detect_uptodown_url(text)
    if uptodown_url:
        await process_app(event, uptodown_url, user_id)
        return

    # 2) Play Store URL -> extract package, fetch app name from Play Store,
    #    then search Uptodown with the app name
    package = detect_play_store_url(text)
    if package:
        status = await event.respond(
            "🔍 لینک گوگل‌پلی شناسایی شد. در حال جستجو در Uptodown..."
        )
        # Get the human-readable app name from the Play Store page title
        loop = asyncio.get_event_loop()
        app_name = await loop.run_in_executor(
            None, lambda: fetch_play_store_app_name(package)
        )
        await status.delete()
        # Search Uptodown by app name (more reliable than by package name)
        await do_search(event, app_name, user_id)
        return

    # 3) Bare package name (like com.whatsapp) -> search Uptodown
    bare_pkg = detect_bare_package(text)
    if bare_pkg:
        # Try searching by package name first; if no results, also try
        # the last segment (e.g. "whatsapp" from "com.whatsapp")
        await do_search(event, bare_pkg, user_id)
        return

    # 4) Otherwise, treat the message as a free-text search query
    await do_search(event, text.strip(), user_id)


# --------------------------------------------------------------------------- #
#  Callback handler (button presses)
# --------------------------------------------------------------------------- #
@client.on(events.CallbackQuery)
async def callback_handler(event: events.CallbackQuery.Event) -> None:
    if not is_authorized(event.sender_id):
        await event.answer("⛔️ شما اجازه استفاده ندارید.", alert=True)
        return

    try:
        data = event.data.decode("utf-8", errors="ignore")
    except Exception:
        data = str(event.data)

    user_id = event.sender_id

    # --- Search result tap ---
    if data.startswith("srch|"):
        idx = data.split("|", 1)[1]
        app = _user_sessions.get(user_id, {}).get("search", {}).get(idx)
        if not app:
            await event.answer("جستجو منقضی شده. دوباره جستجو کنید.", alert=True)
            return
        await event.answer()
        await process_app(event, app["url"], user_id)
        return

    # --- Back to search ---
    if data.startswith("back|"):
        await event.answer()
        await event.edit(
            "🔍 لطفاً نام برنامه یا لینک مورد نظر را بفرستید:",
            link_preview=False,
        )
        return

    # --- Info-only button ---
    if data.startswith("info|"):
        await event.answer(
            "ℹ️ این APK یونیورسال است و روی تمام معماری‌ها کار می‌کند.",
            alert=False,
        )
        return

    # --- Download request ---
    if data.startswith("dl|"):
        await handle_download(event, user_id, data)
        return

    await event.answer("داده نامعتبر است.", alert=True)


async def handle_download(event: events.CallbackQuery.Event, user_id: int, data: str) -> None:
    """Parse callback data, download the chosen APK, send it to the user."""
    parts = data.split("|")
    if len(parts) < 3:
        await event.answer("داده دکمه نامعتبر است.", alert=True)
        return

    _, session_id, version_id = parts[0], parts[1], parts[2]
    app_info = _user_sessions.get(user_id, {}).get(session_id)
    if not app_info:
        await event.answer(
            "اطلاعات برنامه منقضی شده. لطفاً دوباره جستجو کنید.",
            alert=True,
        )
        return

    slug = app_info["slug"]
    # Find the version details
    version = next(
        (v for v in app_info.get("versions", []) if v["version_id"] == version_id),
        None,
    )
    version_name = version.get("version_name", "?") if version else "?"

    await event.answer("در حال دانلود...")

    status = await event.respond(
        f"⬇️ در حال دانلود APK...\n"
        f"📦 برنامه: `{app_info['title']}`\n"
        f"🔢 نسخه: `{version_name}`\n"
        f"⏳ ممکن است چند دقیقه طول بکشد..."
    )

    loop = asyncio.get_event_loop()
    apk_data = await loop.run_in_executor(
        None,
        lambda: UptodownDownloader.get_instance().download_apk(slug, version_id),
    )

    if not apk_data:
        await status.edit(
            "❌ دانلود ناموفق بود. ممکن است این نسخه دیگر در دسترس نباشد. "
            "لطفاً نسخه دیگری را امتحان کنید."
        )
        return

    # Build a friendly filename
    safe_title = re.sub(r"[^\w\.\-]", "_", app_info["title"])[:60] or "app"
    safe_version = re.sub(r"[^\w\.\-]", "_", version_name)[:30] or "version"
    filename = f"{safe_title}_{safe_version}.apk"

    bio = io.BytesIO(apk_data)
    bio.name = filename

    size_mb = len(apk_data) / (1024 * 1024)
    caption = (
        f"✅ **{app_info['title']}**\n"
        f"🔢 نسخه: `{version_name}`\n"
        f"📦 حجم: `{size_mb:.1f} MB`\n"
        f"📲 معماری: یونیورسال (همه)\n"
        f"🔗 منبع: Uptodown"
    )

    try:
        await event.client.send_file(
            entity=event.chat_id,
            file=bio,
            caption=caption,
            parse_mode="md",
            force_document=True,
        )
        await status.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send APK: %s", exc)
        await status.edit(
            f"❌ ارسال فایل ناموفق بود: {exc}\n"
            "ممکن است حجم فایل از حد مجاز تلگرام بیشتر باشد."
        )


# --------------------------------------------------------------------------- #
#  Bootstrap
# --------------------------------------------------------------------------- #
def main() -> None:
    if not is_configured():
        logger.error(
            "Configuration missing. Set API_ID, API_HASH, BOT_TOKEN in .env"
        )
        return

    logger.info("Starting Telethon bot (Uptodown backend)...")
    client.start(bot_token=BOT_TOKEN)
    logger.info("Bot is running. Press Ctrl+C to stop.")
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
