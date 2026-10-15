"""ReVox Web Control Panel (Host UI)

Runs a minimalist local web server at http://127.0.0.1:5050 providing:
- One-click Start / Stop control for the Discord bot.
- Real-time monitoring of voice channels and message queues.
- Automatic availability check for VoiceStudio (:3900).
- Local TTS audio preview player (direct playback in the browser).
- Live console logs via Server-Sent Events (SSE) with severity filters and auto-scroll.
- Hot configuration updates without manual file editing.
"""
import asyncio
import datetime
import io
import itertools
import json
import logging
import os
import sys
import webbrowser
from collections import deque
from pathlib import Path

import aiohttp
from aiohttp import web

from bot import TTSBot, fetch_voices, load_config, vs_headers

# Basic logging setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("revox.panel")

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
ENV_PATH = BASE_DIR / ".env"
PORT = int(os.getenv("PORT", "5050"))

_log_id = itertools.count(1)


class BroadcastLogHandler(logging.Handler):
    """Intercepts log records into a circular buffer and broadcasts them to SSE clients."""

    def __init__(self, capacity: int = 300):
        super().__init__()
        self.buffer = deque(maxlen=capacity)
        self.subscribers: set[asyncio.Queue] = set()

    def emit(self, record: logging.LogRecord):
        try:
            entry = {
                "id": next(_log_id),
                "time": datetime.datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
            self.buffer.append(entry)
            for q in list(self.subscribers):
                try:
                    q.put_nowait(entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)


log_handler = BroadcastLogHandler()
logging.getLogger().addHandler(log_handler)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("revox").setLevel(logging.INFO)


class BotManager:
    """Manages the lifecycle of the TTSBot instance."""

    def __init__(self):
        self.status = "stopped"  # "stopped" | "starting" | "running" | "stopping" | "error"
        self.bot: TTSBot | None = None
        self.task: asyncio.Task | None = None
        self.last_error: str | None = None
        self.cfg = load_config()

    async def start(self) -> tuple[bool, str]:
        if self.status in ("running", "starting"):
            return False, "Bot is already running or starting."

        self.cfg = load_config()
        if not self.cfg["token"]:
            self.status = "error"
            self.last_error = "Discord bot token is missing in configuration."
            return False, self.last_error

        self.status = "starting"
        self.last_error = None
        log.info("Starting ReVox bot with configured token...")

        try:
            self.bot = TTSBot(self.cfg)
            self.task = asyncio.create_task(self._run_bot())
            # Wait up to 10s for bot to become ready or fail
            for _ in range(40):
                await asyncio.sleep(0.25)
                if self.bot and self.bot.is_ready():
                    self.status = "running"
                    log.info("Bot is online and connected to Discord Gateway.")
                    return True, "Bot started successfully."
                if self.status == "error":
                    return False, self.last_error or "Unknown error while starting the bot."
            self.status = "running"
            return True, "Bot connected (syncing application commands)."
        except Exception as e:
            self.status = "error"
            self.last_error = str(e)
            log.error("Failed to start bot: %s", e)
            return False, str(e)

    async def _run_bot(self):
        try:
            await self.bot.start(self.cfg["token"])
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.status = "error"
            self.last_error = str(e)
            log.error("Discord bot runtime exception: %s", e)
        finally:
            if self.status not in ("error", "stopped"):
                self.status = "stopped"

    async def stop(self) -> tuple[bool, str]:
        if self.status == "stopped":
            return True, "Bot is already stopped."

        self.status = "stopping"
        log.info("Stopping ReVox bot...")
        if self.bot:
            try:
                await self.bot.close()
            except Exception as e:
                log.warning("Notice while closing bot: %s", e)
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await asyncio.wait_for(self.task, timeout=5.0)
            except Exception:
                pass

        self.bot = None
        self.task = None
        self.status = "stopped"
        log.info("Bot stopped.")
        return True, "Bot stopped."

    def snapshot(self) -> dict:
        if self.bot and self.bot.is_ready():
            snap = self.bot.snapshot()
            return {
                "bot_status": self.status,
                "bot_user": snap.get("user"),
                "latency_ms": snap.get("latency_ms"),
                "server_count": snap.get("server_count", 0),
                "guilds": snap.get("guilds", []),
                "stats": snap.get("stats", {}),
                "history": snap.get("history", []),
            }
        return {
            "bot_status": self.status,
            "bot_user": None,
            "latency_ms": None,
            "server_count": 0,
            "guilds": [],
            "stats": {"spoken": 0, "errors": 0, "gen_ms_total": 0},
            "history": [],
            "last_error": self.last_error,
        }


manager = BotManager()


async def check_voicestudio(cfg: dict) -> tuple[bool, list[dict]]:
    """Check VoiceStudio availability and return saved profile voices."""
    url = f"{cfg['vs_url']}/v1/audio/voices"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2.5)) as session:
            async with session.get(url, headers=vs_headers(cfg)) as r:
                if r.status == 200:
                    data = await r.json()
                    voices = [
                        {"voice_id": v["voice_id"], "name": v["name"], "language": v.get("language")}
                        for v in data.get("voices", []) if v.get("type") == "profile"
                    ]
                    return True, voices
    except Exception:
        pass
    return False, []


# ---------- HTTP API Handlers ----------

async def handle_index(request: web.Request) -> web.Response:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return web.Response(text="index.html not found", status=404)
    return web.FileResponse(index_path)


async def handle_logo(request: web.Request) -> web.Response:
    logo_path = WEB_DIR / "logo.png"
    if not logo_path.exists():
        return web.Response(status=404)
    return web.FileResponse(logo_path)


async def handle_get_state(request: web.Request) -> web.Response:
    cfg = load_config()
    vs_online, voices = await check_voicestudio(cfg)
    snap = manager.snapshot()
    data = {
        **snap,
        "voicestudio_online": vs_online,
        "voices": voices,
        "config": {
            "token_masked": bool(cfg["token"]),
            "vs_url": cfg["vs_url"],
            "voice": cfg["voice"],
            "max_chars": cfg["max_chars"],
            "autostart": cfg["autostart"],
        },
    }
    return web.json_response(data)


async def handle_bot_start(request: web.Request) -> web.Response:
    ok, msg = await manager.start()
    return web.json_response({"ok": ok, "message": msg, "error": None if ok else msg})


async def handle_bot_stop(request: web.Request) -> web.Response:
    ok, msg = await manager.stop()
    return web.json_response({"ok": ok, "message": msg})


async def handle_bot_say(request: web.Request) -> web.Response:
    if not manager.bot or not manager.bot.is_ready():
        return web.json_response({"ok": False, "error": "Bot is not online."})

    try:
        body = await request.json()
        guild_id = int(body.get("guild_id"))
        text = str(body.get("text", "")).strip()
        voice = body.get("voice")
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid parameters."})

    if voice:
        manager.bot.set_guild_voice(guild_id, voice)

    ok = manager.bot.enqueue(guild_id, text, author="Host Panel", source="panel")
    if not ok:
        return web.json_response({"ok": False, "error": "Could not enqueue (no active channel or empty text)."})

    return web.json_response({"ok": True})


async def handle_bot_skip(request: web.Request) -> web.Response:
    if not manager.bot:
        return web.json_response({"ok": False})
    body = await request.json()
    guild_id = int(body.get("guild_id", 0))
    clear = bool(body.get("clear", False))
    manager.bot.skip(guild_id, clear=clear)
    return web.json_response({"ok": True})


async def handle_bot_delete_queue_item(request: web.Request) -> web.Response:
    if not manager.bot:
        return web.json_response({"ok": False})
    body = await request.json()
    guild_id = int(body.get("guild_id", 0))
    item_id = int(body.get("item_id", 0))
    manager.bot.remove_item(guild_id, item_id)
    return web.json_response({"ok": True})


async def handle_bot_leave(request: web.Request) -> web.Response:
    if not manager.bot:
        return web.json_response({"ok": False})
    body = await request.json()
    guild_id = int(body.get("guild_id", 0))
    await manager.bot.leave(guild_id)
    return web.json_response({"ok": True})


async def handle_tts_preview(request: web.Request) -> web.Response:
    """Generate audio locally via VoiceStudio and return WAV bytes for preview."""
    body = await request.json()
    text = str(body.get("text", "")).strip()
    voice = str(body.get("voice") or "default")
    cfg = load_config()

    if not text:
        return web.Response(text="Empty text", status=400)

    payload = {"model": "tts-1", "input": text, "voice": voice, "response_format": "wav"}
    url = f"{cfg['vs_url']}/v1/audio/speech"

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
            async with session.post(url, json=payload, headers=vs_headers(cfg)) as r:
                if r.status != 200:
                    err = await r.text()
                    return web.Response(text=f"VoiceStudio error: {err[:200]}", status=502)
                audio_bytes = await r.read()
                return web.Response(body=audio_bytes, content_type="audio/wav")
    except Exception as e:
        return web.Response(text=f"Failed to connect to VoiceStudio: {e}", status=502)


async def handle_get_config(request: web.Request) -> web.Response:
    cfg = load_config()
    return web.json_response({
        "token": cfg["token"],
        "vs_url": cfg["vs_url"],
        "voice": cfg["voice"],
        "max_chars": cfg["max_chars"],
        "autostart": cfg["autostart"],
    })


async def handle_save_config(request: web.Request) -> web.Response:
    body = await request.json()
    token = str(body.get("token", "")).strip()
    vs_url = str(body.get("vs_url", "http://127.0.0.1:3900")).strip().rstrip("/")
    voice = str(body.get("voice", "default")).strip()
    max_chars = int(body.get("max_chars", 400))
    autostart = "1" if body.get("autostart") else "0"

    env_content = f"""# ReVox TTS Bot Configuration
DISCORD_TOKEN={token}
VOICESTUDIO_URL={vs_url}
VOICESTUDIO_VOICE={voice}
VOICESTUDIO_API_KEY=
MAX_CHARS={max_chars}
AUTOSTART={autostart}
"""
    try:
        ENV_PATH.write_text(env_content, encoding="utf-8")
        log.info("Configuration updated in .env")
        # Hot reload active bot config if running
        if manager.bot:
            manager.bot.cfg["voice"] = voice
            manager.bot.cfg["max_chars"] = max_chars
            manager.bot.cfg["vs_url"] = vs_url
            log.info("Active bot configuration hot-reloaded in memory.")
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


async def handle_clear_logs(request: web.Request) -> web.Response:
    log_handler.buffer.clear()
    return web.json_response({"ok": True})


# ---------- Server-Sent Events (SSE) Streaming ----------

async def handle_events(request: web.Request) -> web.StreamResponse:
    resp = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await resp.prepare(request)

    # Send buffered logs on initial connection
    for entry in list(log_handler.buffer):
        payload = f"event: log\ndata: {json.dumps(entry)}\n\n".encode("utf-8")
        await resp.write(payload)

    queue = asyncio.Queue(maxsize=100)
    log_handler.subscribers.add(queue)

    try:
        while True:
            try:
                entry = await asyncio.wait_for(queue.get(), timeout=12.0)
                payload = f"event: log\ndata: {json.dumps(entry)}\n\n".encode("utf-8")
                await resp.write(payload)
            except asyncio.TimeoutError:
                await resp.write(b": ping\n\n")
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        log_handler.subscribers.discard(queue)

    return resp


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/logo.png", handle_logo)
    app.router.add_get("/api/state", handle_get_state)
    app.router.add_post("/api/bot/start", handle_bot_start)
    app.router.add_post("/api/bot/stop", handle_bot_stop)
    app.router.add_post("/api/bot/say", handle_bot_say)
    app.router.add_post("/api/bot/skip", handle_bot_skip)
    app.router.add_post("/api/bot/delete_queue_item", handle_bot_delete_queue_item)
    app.router.add_post("/api/bot/leave", handle_bot_leave)
    app.router.add_post("/api/tts/preview", handle_tts_preview)
    app.router.add_get("/api/config", handle_get_config)
    app.router.add_post("/api/config", handle_save_config)
    app.router.add_post("/api/logs/clear", handle_clear_logs)
    app.router.add_get("/api/events", handle_events)
    return app


async def main():
    cfg = load_config()
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    try:
        await site.start()
    except OSError as e:
        if getattr(e, "winerror", None) == 10048 or "10048" in str(e):
            log.warning("⚠️ Port %d is already in use. Another instance of the panel is likely already running.", PORT)
            try:
                webbrowser.open(f"http://127.0.0.1:{PORT}")
            except Exception:
                pass
            return
        raise

    url = f"http://127.0.0.1:{PORT}"
    log.info("╔════════════════════════════════════════════════════════╗")
    log.info("║  🎙️  ReVox Control Panel ready at: %s        ║", url)
    log.info("╚════════════════════════════════════════════════════════╝")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    if cfg.get("autostart") and cfg.get("token"):
        log.info("Autostart enabled: starting bot automatically...")
        asyncio.create_task(manager.start())

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Shutting down panel...")
        await manager.stop()
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
