# ============================================================
# @UseMasterUpdate — Facebook Video Downloader & Uploader Bot
# Built with Pyrogram | Credits: @UseMasterUpdate
# ============================================================

import os
import re
import json
import time
import random
import asyncio
import requests
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

# ──────────────────────────────────────────────
# @UseMasterUpdate — Bot Configuration
# ──────────────────────────────────────────────
API_ID    = int(os.environ.get("API_ID", 0))
API_HASH  = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

OUTPUT_FOLDER = "downloads"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

CREDIT = "@UseMasterUpdate"

# ──────────────────────────────────────────────
# Pyrogram Client — @UseMasterUpdate
# ──────────────────────────────────────────────
app = Client(
    "fb_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ──────────────────────────────────────────────
# Utilities — @UseMasterUpdate
# ──────────────────────────────────────────────
def human_size(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.2f} {unit}"
        num /= 1024
    return f"{num:.2f} TB"

def progress_bar(current: int, total: int, width: int = 10) -> str:
    if total == 0:
        return "░" * width
    filled = int(width * current / total)
    return f"[{'█' * filled}{'░' * (width - filled)}] {current / total * 100:.1f}%"

_last_edit: dict[int, float] = {}

async def safe_edit(msg: Message, text: str, min_interval: float = 2.5) -> None:
    now = time.time()
    if now - _last_edit.get(msg.id, 0) < min_interval:
        return
    _last_edit[msg.id] = now
    try:
        await msg.edit_text(text)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        pass

# ──────────────────────────────────────────────
# Facebook URL detector
# ──────────────────────────────────────────────
FB_PATTERN = re.compile(
    r"(https?://)?(www\.)?(facebook\.com|fb\.watch|fb\.com)/\S+",
    re.IGNORECASE,
)

def extract_fb_url(text: str) -> str | None:
    m = FB_PATTERN.search(text)
    return m.group(0) if m else None

# ──────────────────────────────────────────────
# EXACT extraction logic from your working script
# Ported 1:1 — @UseMasterUpdate
# ──────────────────────────────────────────────
FETCH_HEADERS = {
    # Full browser headers — same as your working script
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Dnt': '1',
    'Dpr': '1.3125',
    'Priority': 'u=0, i',
    'Sec-Ch-Prefers-Color-Scheme': 'dark',
    'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'Sec-Ch-Ua-Full-Version-List': '"Chromium";v="124.0.6367.156", "Google Chrome";v="124.0.6367.156", "Not-A.Brand";v="99.0.0.0"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Model': '""',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Ch-Ua-Platform-Version': '"15.0.0"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Viewport-Width': '1463',
}

DOWNLOAD_HEADERS = {
    # Lighter headers for downloading CDN files — @UseMasterUpdate
    'user-agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36'
}

def _extract_fb_links_sync(link: str) -> tuple[str, str, str]:
    """
    Exact port of your working downloadVideo() extraction logic.
    Returns (video_url, audio_url, video_id).
    Raises ValueError with a readable message on any failure.
    — @UseMasterUpdate
    """
    try:
        resp = requests.get(link, headers=FETCH_HEADERS, timeout=30)
    except Exception as e:
        raise ValueError(f"Failed to fetch page: {e}")

    # Resolve final URL (handles redirects like fb.watch) — same as your script
    resolved_url = resp.url.split('?')[0]
    html = resp.text

    # Extract video_id from URL segments — @UseMasterUpdate
    video_id = ''
    for seg in resolved_url.split('/'):
        if seg.isdigit():
            video_id = seg
            break

    if not video_id:
        # Fallback: try ?v= param before split
        raw_params = resp.url.split('?')
        if len(raw_params) > 1:
            for param in raw_params[1].split('&'):
                if param.startswith('v=') and param[2:].isdigit():
                    video_id = param[2:]
                    break

    if not video_id:
        raise ValueError("Could not find video ID in URL. Is this a valid Facebook video link?")

    # ── DASH stream ID extraction — exact logic from your script ──
    try:
        target_video_audio_id = (
            html.split(f'"id":"{video_id}"')[1]
                .split('"dash_prefetch_experimental":[')[1]
                .split(']')[0]
                .strip()
        )
    except IndexError:
        try:
            target_video_audio_id = (
                html.split(f'"video_id":"{video_id}"')[1]
                    .split('"dash_prefetch_experimental":[')[1]
                    .split(']')[0]
                    .strip()
            )
        except IndexError:
            raise ValueError(
                "Could not find DASH stream data.\n"
                "Possible reasons: video is private, age-restricted, or a story/reel not yet supported."
            )

    list_str = f"[{target_video_audio_id}]"
    try:
        sources = json.loads(list_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse stream source list: {e}")

    if len(sources) < 2:
        raise ValueError(f"Expected at least 2 stream sources, got {len(sources)}.")

    # ── base_url extraction — exact logic from your script ──
    try:
        video_link = (
            html.split(f'"representation_id":"{sources[0]}"')[1]
                .split('"base_url":"')[1]
                .split('"')[0]
                .replace('\\', '')
        )
    except IndexError:
        raise ValueError(f"Could not extract video stream URL for source ID: {sources[0]}")

    try:
        audio_link = (
            html.split(f'"representation_id":"{sources[1]}"')[1]
                .split('"base_url":"')[1]
                .split('"')[0]
                .replace('\\', '')
        )
    except IndexError:
        raise ValueError(f"Could not extract audio stream URL for source ID: {sources[1]}")

    return video_link, audio_link, video_id

# ──────────────────────────────────────────────
# Download a CDN file with live progress
# Uses same headers as your downloadFile() — @UseMasterUpdate
# ──────────────────────────────────────────────
async def download_with_progress(
    url: str,
    dest: str,
    status_msg: Message,
    label: str = "Downloading",
) -> bool:
    try:
        resp = requests.get(url, headers=DOWNLOAD_HEADERS, stream=True, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        await safe_edit(status_msg, f"❌ Download request failed:\n`{e}`\n\n— {CREDIT}")
        return False

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=512 * 1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                bar = progress_bar(downloaded, total)
                size_str = (
                    f"{human_size(downloaded)} / {human_size(total)}"
                    if total else human_size(downloaded)
                )
                await safe_edit(
                    status_msg,
                    f"📥 **{label}**\n{bar}\n`{size_str}`\n\n— {CREDIT}",
                )

    return True

# ──────────────────────────────────────────────
# FFmpeg helpers — @UseMasterUpdate
# ──────────────────────────────────────────────
def merge_streams(video_path: str, audio_path: str, out_path: str) -> bool:
    # Same as your script's ffmpeg call — @UseMasterUpdate
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", video_path,
        "-i", audio_path,
        "-c", "copy",
        "-y", out_path,
    ]
    try:
        subprocess.run(cmd, timeout=300, check=True)
        return True
    except Exception:
        return False

def extract_thumbnail(video_path: str, thumb_path: str) -> bool:
    # Random frame between 10%-80% of video — @UseMasterUpdate
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, timeout=30
    )
    try:
        duration = float(probe.stdout.strip() or "10")
    except ValueError:
        duration = 10.0

    seek = random.uniform(duration * 0.10, duration * 0.80)
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-ss", str(seek), "-i", video_path,
             "-vframes", "1", "-vf", "scale=320:-1", "-y", thumb_path],
            timeout=30, check=True
        )
        return os.path.exists(thumb_path)
    except Exception:
        return False

def get_video_metadata(video_path: str) -> tuple[int, int, int]:
    # Returns (duration_secs, width, height) — fixes 0:00 bug — @UseMasterUpdate
    dur_result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, timeout=30
    )
    try:
        duration = int(float(dur_result.stdout.strip() or "0"))
    except ValueError:
        duration = 0

    dim_result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=30
    )
    try:
        w, h = dim_result.stdout.strip().split(",")
        width, height = int(w), int(h)
    except Exception:
        width, height = 1280, 720

    return duration, width, height

# ──────────────────────────────────────────────
# Upload progress callback — @UseMasterUpdate
# ──────────────────────────────────────────────
def make_upload_cb(status_msg: Message, loop: asyncio.AbstractEventLoop):
    last = [0.0]
    def cb(current: int, total: int):
        now = time.time()
        if now - last[0] < 2.5:
            return
        last[0] = now
        bar = progress_bar(current, total)
        text = (
            f"📤 **Uploading to Telegram...**\n"
            f"{bar}\n"
            f"`{human_size(current)} / {human_size(total)}`\n\n"
            f"— {CREDIT}"
        )
        asyncio.run_coroutine_threadsafe(
            safe_edit(status_msg, text, min_interval=0), loop
        )
    return cb

# ──────────────────────────────────────────────
# Main handler — @UseMasterUpdate
# ──────────────────────────────────────────────
@app.on_message(filters.text & ~filters.command(["start", "help"]))
async def handle_fb_link(client: Client, message: Message) -> None:
    url = extract_fb_url(message.text)
    if not url:
        return

    status = await message.reply_text(
        f"🔍 **Facebook link detected!**\nStarting...\n\n— {CREDIT}"
    )

    # ── Step 1: Extract stream URLs (runs in thread, not blocking) ──
    await safe_edit(status, f"🔗 **Extracting stream URLs...**\n\n— {CREDIT}")
    try:
        video_url, audio_url, video_id = await asyncio.to_thread(
            _extract_fb_links_sync, url
        )
    except ValueError as e:
        await safe_edit(status, f"❌ **Extraction failed:**\n`{e}`\n\n— {CREDIT}")
        return

    # File paths — @UseMasterUpdate
    raw_video = os.path.join(OUTPUT_FOLDER, f"{video_id}_v.mp4")
    raw_audio = os.path.join(OUTPUT_FOLDER, f"{video_id}_a.mp4")
    merged    = os.path.join(OUTPUT_FOLDER, f"{video_id}.mp4")
    thumb     = os.path.join(OUTPUT_FOLDER, f"{video_id}.jpg")

    # ── Step 2: Download video stream ──
    ok = await download_with_progress(video_url, raw_video, status, "Downloading Video Stream")
    if not ok:
        return

    # ── Step 3: Download audio stream ──
    ok = await download_with_progress(audio_url, raw_audio, status, "Downloading Audio Stream")
    if not ok:
        try: os.remove(raw_video)
        except: pass
        return

    # ── Step 4: Merge ──
    await safe_edit(status, f"⚙️ **Merging streams with FFmpeg...**\n\n— {CREDIT}")
    ok = await asyncio.to_thread(merge_streams, raw_video, raw_audio, merged)
    for f in [raw_video, raw_audio]:
        try: os.remove(f)
        except: pass

    if not ok:
        await safe_edit(status, f"❌ **Merge failed.**\n\n— {CREDIT}")
        return

    # ── Step 5: Thumbnail (random frame) ──
    await safe_edit(status, f"🖼️ **Capturing random thumbnail...**\n\n— {CREDIT}")
    has_thumb = await asyncio.to_thread(extract_thumbnail, merged, thumb)

    # ── Step 6: Metadata (duration fix) ──
    duration, width, height = await asyncio.to_thread(get_video_metadata, merged)

    # ── Step 7: Upload ──
    await safe_edit(status, f"📤 **Starting upload...**\n\n— {CREDIT}")
    loop = asyncio.get_event_loop()

    try:
        await client.send_video(
            chat_id=message.chat.id,
            video=merged,
            thumb=thumb if has_thumb else None,
            duration=duration,          # ← correct duration, fixes 0:00 — @UseMasterUpdate
            width=width,
            height=height,
            caption=(
                f"✅ **Facebook Video**\n"
                f"🆔 `{video_id}`\n"
                f"⏱ `{duration}s`  📐 `{width}×{height}`\n\n"
                f"— {CREDIT}"
            ),
            supports_streaming=True,
            progress=make_upload_cb(status, loop),
        )
        await status.edit_text(f"✅ **Uploaded successfully!**\n\n— {CREDIT}")
    except Exception as e:
        await safe_edit(status, f"❌ **Upload error:**\n`{e}`\n\n— {CREDIT}")
    finally:
        for f in [merged, thumb]:
            try: os.remove(f)
            except: pass

# ──────────────────────────────────────────────
# Commands — @UseMasterUpdate
# ──────────────────────────────────────────────
@app.on_message(filters.command("start"))
async def cmd_start(_, message: Message):
    await message.reply_text(
        "👋 **FB Video Downloader Bot**\n\n"
        "Send any Facebook video link — I'll download and upload it here.\n\n"
        f"— {CREDIT}"
    )

@app.on_message(filters.command("help"))
async def cmd_help(_, message: Message):
    await message.reply_text(
        "📖 **Usage:** Just paste a Facebook video URL.\n\n"
        "Supports:\n"
        "• `facebook.com/watch?v=...`\n"
        "• `fb.watch/...`\n"
        "• `facebook.com/.../videos/...`\n\n"
        f"— {CREDIT}"
    )

# ──────────────────────────────────────────────
# Run — @UseMasterUpdate
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🚀 Starting | {CREDIT}")
    app.run()
