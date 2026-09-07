#!/usr/bin/env python3
"""
🎬 Video Downloader Telegram Bot
Supports: YouTube, Instagram, TikTok, Twitter/X, Facebook, and 1000+ sites via yt-dlp
"""

import os
import re
import glob
import logging
import telebot
import yt_dlp
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────
TOKEN     = os.getenv("BOT_TOKEN")
ADMIN_ID  = os.getenv("ADMIN_ID", "")       # optional
DL_DIR    = Path("downloads")
MAX_SIZE  = 50 * 1024 * 1024                 # 50 MB Telegram limit
LOG_FILE  = "bot.log"

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Init ─────────────────────────────────────────────────────────────────────
if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN not set in .env")

DL_DIR.mkdir(exist_ok=True)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ── Supported sites list ──────────────────────────────────────────────────────
SUPPORTED = (
    "YouTube", "Instagram", "TikTok", "Twitter/X", "Facebook",
    "Dailymotion", "Vimeo", "Reddit", "LinkedIn", "Pinterest",
    "Twitch", "Bilibili", "SoundCloud", "and 1000+ more sites via yt-dlp"
)

URL_RE = re.compile(r"https?://[^\s]+")

# ── yt-dlp options ─────────────────────────────────────────────────────────────
def ydl_opts(uid: int) -> dict:
    user_dir = DL_DIR / str(uid)
    user_dir.mkdir(exist_ok=True)
    return {
        "outtmpl"          : str(user_dir / "%(title).60s.%(ext)s"),
        "format"           : "bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best[filesize<45M]/best",
        "merge_output_format": "mp4",
        "quiet"            : True,
        "no_warnings"      : True,
        "noplaylist"       : True,
        "socket_timeout"   : 30,
        "retries"          : 3,
        "postprocessors"   : [{
            "key"              : "FFmpegVideoConvertor",
            "preferedformat"   : "mp4",
        }],
    }

# ── Helpers ──────────────────────────────────────────────────────────────────
def clean_user_dir(uid: int):
    """Remove old downloads for this user."""
    user_dir = DL_DIR / str(uid)
    for f in user_dir.glob("*"):
        try:
            f.unlink()
        except Exception:
            pass

def get_video_info(url: str) -> dict | None:
    """Fetch video metadata without downloading."""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.warning(f"Info extract failed: {e}")
        return None

def human_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"

# ── /start ────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    text = (
        "🎬 <b>Video Downloader Bot</b>\n\n"
        "📥 Just send me a video URL and I'll download it for you!\n\n"
        "<b>✅ Supported platforms:</b>\n"
        + "\n".join(f"  • {s}" for s in SUPPORTED)
        + "\n\n"
        "📋 <b>Commands:</b>\n"
        "  /start  – Show this message\n"
        "  /help   – How to use\n"
        "  /about  – Bot info\n\n"
        "💡 <i>Just paste any video link and press Send!</i>"
    )
    bot.reply_to(msg, text)

# ── /help ─────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["help"])
def cmd_help(msg):
    text = (
        "📖 <b>How to use:</b>\n\n"
        "1️⃣ Copy a video URL (YouTube, Instagram, TikTok, etc.)\n"
        "2️⃣ Paste it here and send\n"
        "3️⃣ Wait a moment ⏳\n"
        "4️⃣ Receive your video! 🎉\n\n"
        "⚠️ <b>Notes:</b>\n"
        "  • Max file size: <b>50 MB</b>\n"
        "  • Private/age-restricted content may not work\n"
        "  • Instagram Reels, Stories, Posts ✅\n"
        "  • YouTube Shorts ✅\n"
        "  • Twitter/X Videos ✅\n"
        "  • TikTok (no watermark) ✅\n\n"
        "🔗 <i>Send me a link to get started!</i>"
    )
    bot.reply_to(msg, text)

# ── /about ────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["about"])
def cmd_about(msg):
    text = (
        "ℹ️ <b>About this bot</b>\n\n"
        "🤖 Powered by <code>yt-dlp</code>\n"
        "📦 Version: <b>1.0.0</b>\n"
        "🌐 Supports <b>1000+</b> websites\n\n"
        "Built with ❤️ using Python + yt-dlp"
    )
    bot.reply_to(msg, text)

# ── Main handler: URL in message ──────────────────────────────────────────────
@bot.message_handler(func=lambda m: bool(URL_RE.search(m.text or "")))
def handle_url(msg):
    uid  = msg.from_user.id
    text = msg.text.strip()

    # Extract first URL from message
    url = URL_RE.search(text).group(0)
    logger.info(f"User {uid} → {url}")

    # Step 1: Fetching info
    wait_msg = bot.reply_to(msg, "🔍 <b>Fetching video info...</b>")

    info = get_video_info(url)
    if not info:
        bot.edit_message_text(
            "❌ <b>Could not fetch video.</b>\n"
            "• URL might be private or unsupported\n"
            "• Try a different link\n\n"
            "Use /help for supported sites.",
            chat_id=msg.chat.id,
            message_id=wait_msg.message_id,
        )
        return

    title    = info.get("title", "Unknown")[:80]
    duration = info.get("duration", 0)
    uploader = info.get("uploader", "Unknown")
    mins, secs = divmod(int(duration or 0), 60)

    bot.edit_message_text(
        f"📹 <b>{title}</b>\n"
        f"👤 {uploader}  |  ⏱ {mins}:{secs:02d}\n\n"
        "⬇️ <b>Downloading...</b>",
        chat_id=msg.chat.id,
        message_id=wait_msg.message_id,
    )

    # Step 2: Download
    clean_user_dir(uid)
    try:
        with yt_dlp.YoutubeDL(ydl_opts(uid)) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        err = str(e)[:300]
        bot.edit_message_text(
            f"❌ <b>Download failed:</b>\n<code>{err}</code>",
            chat_id=msg.chat.id,
            message_id=wait_msg.message_id,
        )
        return
    except Exception as e:
        logger.exception(f"Unexpected download error: {e}")
        bot.edit_message_text(
            "⚠️ <b>Unexpected error during download.</b>",
            chat_id=msg.chat.id,
            message_id=wait_msg.message_id,
        )
        return

    # Step 3: Find downloaded file
    user_dir = DL_DIR / str(uid)
    files    = sorted(user_dir.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        bot.edit_message_text(
            "❌ <b>File not found after download.</b>",
            chat_id=msg.chat.id,
            message_id=wait_msg.message_id,
        )
        return

    video_file = files[0]
    size       = video_file.stat().st_size

    # Step 4: Check size
    if size > MAX_SIZE:
        bot.edit_message_text(
            f"⚠️ <b>File too large!</b>\n"
            f"Size: <b>{human_size(size)}</b> (Limit: 50 MB)\n\n"
            "Try a shorter video or lower quality.",
            chat_id=msg.chat.id,
            message_id=wait_msg.message_id,
        )
        clean_user_dir(uid)
        return

    # Step 5: Send video
    bot.edit_message_text(
        f"📤 <b>Uploading...</b> ({human_size(size)})",
        chat_id=msg.chat.id,
        message_id=wait_msg.message_id,
    )

    try:
        with open(video_file, "rb") as vf:
            bot.send_video(
                msg.chat.id,
                vf,
                caption=f"🎬 <b>{title}</b>\n📦 {human_size(size)}",
                supports_streaming=True,
                reply_to_message_id=msg.message_id,
            )
        bot.delete_message(msg.chat.id, wait_msg.message_id)
        logger.info(f"Sent {video_file.name} ({human_size(size)}) to user {uid}")
    except Exception as e:
        logger.exception(f"Send error: {e}")
        bot.edit_message_text(
            "❌ <b>Failed to send video.</b> Please try again.",
            chat_id=msg.chat.id,
            message_id=wait_msg.message_id,
        )
    finally:
        clean_user_dir(uid)

# ── Unknown messages ──────────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: True)
def handle_unknown(msg):
    bot.reply_to(
        msg,
        "💡 Please send a <b>video URL</b> to download.\n\n"
        "Use /help for instructions.",
    )

# ── Start polling ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🤖 Bot started – polling...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
