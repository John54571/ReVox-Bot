"""Discord Bot that reads your chat messages aloud using VoiceStudio (local) for real-time TTS.

Can be run standalone (`python bot.py`) or via the web panel (`python panel.py`).
"""
import asyncio
import io
import itertools
import logging
import math
import os
import re
import time
from collections import deque
from dataclasses import asdict, dataclass, field

import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv

log = logging.getLogger("revox")
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def sanitize_tts_text(raw_text: str, max_chars: int = 400) -> str:
    """Clean and normalize text before sending to VoiceStudio so it sounds natural."""
    if not raw_text:
        return ""
    # Replace code blocks ```...``` with "code block"
    t = re.sub(r"```[\s\S]*?```", " code block ", raw_text)
    # Replace URLs with "link" to avoid character-by-character spelling
    t = re.sub(r"https?://\S+", " link ", t)
    # Replace channel or role mentions
    t = re.sub(r"<#\d+>", " channel ", t)
    t = re.sub(r"<@&\d+>", " role ", t)
    t = re.sub(r"\|\|(.*?)\|\|", r"\1", t)
    # Normalize whitespaces and repeated line breaks
    t = " ".join(t.split())
    return t[:max_chars].strip()


def load_config() -> dict:
    """Read .env on every reload so panel updates take effect upon bot restarts."""
    load_dotenv(ENV_PATH, override=True)
    return {
        "token": os.getenv("DISCORD_TOKEN", "").strip(),
        "vs_url": os.getenv("VOICESTUDIO_URL", "http://127.0.0.1:3900").rstrip("/"),
        "vs_key": os.getenv("VOICESTUDIO_API_KEY", ""),
        "voice": os.getenv("VOICESTUDIO_VOICE", "default"),
        "max_chars": int(os.getenv("MAX_CHARS", "400")),
        "autostart": os.getenv("AUTOSTART", "0") == "1",
    }


def vs_headers(cfg: dict) -> dict:
    return {"Authorization": f"Bearer {cfg['vs_key']}"} if cfg["vs_key"] else {}


async def fetch_voices(session: aiohttp.ClientSession, cfg: dict) -> list[dict]:
    """Fetch saved voice profiles from VoiceStudio (excluding OpenAI aliases)."""
    async with session.get(f"{cfg['vs_url']}/v1/audio/voices", headers=vs_headers(cfg)) as r:
        r.raise_for_status()
        voices = (await r.json())["voices"]
    return [
        {"voice_id": v["voice_id"], "name": v["name"], "language": v.get("language")}
        for v in voices if v.get("type") == "profile"
    ]


_ids = itertools.count(1)


@dataclass
class Item:
    text: str
    author: str
    source: str  # "chat" | "/say" | "panel"
    id: int = field(default_factory=lambda: next(_ids))
    ts: float = field(default_factory=time.time)


class GuildState:
    def __init__(self, guild: discord.Guild, text_channel_id: int, voice: str):
        self.guild = guild
        self.text_channel_id = text_channel_id
        self.voice = voice
        self.items: deque[Item] = deque()
        self.wake = asyncio.Event()
        self.now: Item | None = None
        self.phase: str | None = None  # "generating" | "speaking"
        self.worker: asyncio.Task | None = None

    def push(self, item: Item):
        self.items.append(item)
        self.wake.set()


class TTSBot(discord.Client):
    def __init__(self, cfg: dict):
        intents = discord.Intents.default()
        intents.message_content = True  # Must also be enabled in Discord Developer Portal
        super().__init__(intents=intents)
        self.cfg = cfg
        self.tree = app_commands.CommandTree(self)
        self.state: dict[int, GuildState] = {}
        self.session: aiohttp.ClientSession | None = None
        self.history: deque[dict] = deque(maxlen=50)
        self.stats = {"spoken": 0, "errors": 0, "gen_ms_total": 0}
        self._register_commands()

    async def setup_hook(self):
        # Model loading may take time on cold starts, hence generous timeout.
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600))
        await self.tree.sync()

    async def close(self):
        for st in self.state.values():
            if st.worker:
                st.worker.cancel()
        self.state.clear()
        await super().close()
        if self.session:
            await self.session.close()

    # ---------- TTS ----------

    async def tts(self, text: str, voice: str) -> bytes:
        """Call VoiceStudio's OpenAI-compatible endpoint and return WAV audio bytes."""
        payload = {"model": "tts-1", "input": text, "voice": voice, "response_format": "wav"}
        url = f"{self.cfg['vs_url']}/v1/audio/speech"
        async with self.session.post(url, json=payload, headers=vs_headers(self.cfg)) as r:
            if r.status != 200:
                raise RuntimeError(f"VoiceStudio returned {r.status}: {(await r.text())[:300]}")
            return await r.read()

    async def speak_loop(self, st: GuildState):
        """Process guild queue, one message at a time."""
        while True:
            if not st.items:
                st.wake.clear()
                await st.wake.wait()
                continue
            item = st.items.popleft()
            vc = st.guild.voice_client
            if not vc or not vc.is_connected():
                continue
            st.now, st.phase = item, "generating"
            entry = {**asdict(item), "guild": st.guild.name, "voice": st.voice, "status": "cancelled"}
            try:
                t0 = time.perf_counter()
                audio = await self.tts(item.text, st.voice)
                entry["gen_ms"] = round((time.perf_counter() - t0) * 1000)

                # Re-verify bot is still connected to voice channel after TTS generation
                vc = st.guild.voice_client
                if not vc or not vc.is_connected():
                    log.warning("[%s] Bot disconnected from voice while synthesizing audio.", st.guild.name)
                    continue

                st.phase = "speaking"
                done = asyncio.Event()
                vc.play(
                    discord.FFmpegPCMAudio(io.BytesIO(audio), pipe=True),
                    after=lambda _: self.loop.call_soon_threadsafe(done.set),
                )
                await done.wait()
                entry["status"] = "ok"
                self.stats["spoken"] += 1
                self.stats["gen_ms_total"] += entry["gen_ms"]
                log.info("[%s] %s: %s (%d ms)", st.guild.name, item.author, item.text, entry["gen_ms"])
            except asyncio.CancelledError:
                raise
            except Exception as e:
                entry["status"], entry["error"] = "error", str(e)
                self.stats["errors"] += 1
                log.error("TTS failed on %s: %s", st.guild.name, e)
            finally:
                st.now = st.phase = None
                self.history.appendleft(entry)

    # ---------- Actions (called by commands and web panel) ----------

    def enqueue(self, guild_id: int, text: str, author: str, source: str) -> bool:
        st = self.state.get(guild_id)
        if not st:
            return False
        clean_text = sanitize_tts_text(text, self.cfg["max_chars"])
        if not clean_text:
            return False
        # Queue limit protection: max 30 pending messages per server
        if len(st.items) >= 30:
            st.items.popleft()  # Discard oldest to prioritize current conversation
        st.push(Item(clean_text, author, source))
        return True

    def skip(self, guild_id: int, clear: bool = False):
        st = self.state.get(guild_id)
        if st and clear:
            st.items.clear()
        guild = self.get_guild(guild_id)
        if guild and guild.voice_client:
            guild.voice_client.stop()

    def remove_item(self, guild_id: int, item_id: int):
        st = self.state.get(guild_id)
        if st:
            st.items = deque(i for i in st.items if i.id != item_id)

    async def leave(self, guild_id: int):
        st = self.state.pop(guild_id, None)
        if st and st.worker:
            st.worker.cancel()
        guild = self.get_guild(guild_id)
        if guild and guild.voice_client:
            await guild.voice_client.disconnect()
        log.info("Left voice channel in %s", guild.name if guild else guild_id)

    async def resolve_voice(self, name_or_id: str) -> dict | None:
        voices = await fetch_voices(self.session, self.cfg)
        q = name_or_id.lower()
        return next((v for v in voices if q in (v["voice_id"].lower(), v["name"].lower())), None)

    def set_guild_voice(self, guild_id: int, voice_id: str):
        st = self.state.get(guild_id)
        if st:
            st.voice = voice_id

    def snapshot(self) -> dict:
        guilds = []
        for gid, st in self.state.items():
            vc = st.guild.voice_client
            tc = st.guild.get_channel(st.text_channel_id)
            guilds.append({
                "id": str(gid),  # Stringified: Discord IDs exceed JS Number.MAX_SAFE_INTEGER
                "name": st.guild.name,
                "voice_channel": vc.channel.name if vc and vc.channel else None,
                "text_channel": tc.name if tc else None,
                "voice": st.voice,
                "phase": st.phase,
                "now": asdict(st.now) if st.now else None,
                "queue": [asdict(i) for i in st.items],
            })
        ready = self.is_ready()
        return {
            "user": str(self.user) if self.user else None,
            "avatar": self.user.display_avatar.url if self.user else None,
            "latency_ms": round(self.latency * 1000) if ready and math.isfinite(self.latency) else None,
            "server_count": len(self.guilds) if ready else 0,
            "all_guilds": [{"id": str(g.id), "name": g.name} for g in self.guilds] if ready else [],
            "guilds": guilds,
            "history": list(self.history),
            "stats": self.stats,
        }

    # ---------- Events ----------

    async def on_ready(self):
        log.info("Connected as %s — VoiceStudio at %s", self.user, self.cfg["vs_url"])

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        st = self.state.get(message.guild.id)
        if st and message.channel.id == st.text_channel_id and message.guild.voice_client:
            self.enqueue(message.guild.id, message.clean_content, message.author.display_name, "chat")

    async def on_voice_state_update(self, member, before, after):
        # If someone manually disconnects the bot, clean up guild state
        if member.id == self.user.id and before.channel and not after.channel:
            st = self.state.pop(member.guild.id, None)
            if st and st.worker:
                st.worker.cancel()
                log.info("Bot was disconnected from voice channel in %s", member.guild.name)

    # ---------- Slash commands ----------

    def _register_commands(self):
        bot = self

        async def _join_handler(inter: discord.Interaction):
            if not inter.user.voice or not inter.user.voice.channel:
                return await inter.response.send_message("Please join a voice channel first.", ephemeral=True)
            await inter.response.defer()
            channel = inter.user.voice.channel
            vc = inter.guild.voice_client
            if vc:
                await vc.move_to(channel)
            else:
                await channel.connect(self_deaf=True)

            st = bot.state.get(inter.guild.id)
            if st:
                st.text_channel_id = inter.channel.id
            else:
                st = bot.state[inter.guild.id] = GuildState(inter.guild, inter.channel.id, bot.cfg["voice"])
            if not st.worker or st.worker.done():
                st.worker = asyncio.create_task(bot.speak_loop(st))
            log.info("Joined %s / %s (reading #%s)", inter.guild.name, channel.name, inter.channel.name)
            await inter.followup.send(f"🔊 Joined **{channel.name}**. Reading chat from {inter.channel.mention}.")

        async def _leave_handler(inter: discord.Interaction):
            await bot.leave(inter.guild.id)
            await inter.response.send_message("👋 Left the voice channel.")

        async def _say_handler(inter: discord.Interaction, text: str):
            if not inter.guild.voice_client or not bot.enqueue(inter.guild.id, text, inter.user.display_name, "/say"):
                return await inter.response.send_message("Please use /join first.", ephemeral=True)
            await inter.response.send_message(f"🗣️ {text[: bot.cfg['max_chars']]}", ephemeral=True)

        async def _voice_handler(inter: discord.Interaction, name: str):
            st = bot.state.get(inter.guild.id)
            if not st:
                return await inter.response.send_message("Please use /join first.", ephemeral=True)
            match = await bot.resolve_voice(name)
            if not match:
                names = ", ".join(v["name"] for v in await fetch_voices(bot.session, bot.cfg))
                return await inter.response.send_message(f"Voice not found. Available voices: {names}", ephemeral=True)
            st.voice = match["voice_id"]
            await inter.response.send_message(f"Voice changed to **{match['name']}**.")

        async def _skip_handler(inter: discord.Interaction):
            bot.skip(inter.guild.id, clear=True)
            await inter.response.send_message("⏭️ Skipped.", ephemeral=True)

        # Primary English Slash Commands
        @self.tree.command(name="join", description="Join your current voice channel and read this text channel")
        async def join_cmd(inter: discord.Interaction):
            await _join_handler(inter)

        @self.tree.command(name="leave", description="Disconnect the bot from the voice channel")
        async def leave_cmd(inter: discord.Interaction):
            await _leave_handler(inter)

        @self.tree.command(name="say", description="Speak text aloud (useful from another channel)")
        @app_commands.describe(text="The message to speak")
        async def say_cmd(inter: discord.Interaction, text: str):
            await _say_handler(inter, text)

        @self.tree.command(name="voice", description="Change the active voice profile (ID or profile name from VoiceStudio)")
        @app_commands.describe(name="Voice profile name or ID")
        async def voice_cmd(inter: discord.Interaction, name: str):
            await _voice_handler(inter, name)

        @self.tree.command(name="skip", description="Stop current playback and clear the pending queue")
        async def skip_cmd(inter: discord.Interaction):
            await _skip_handler(inter)

        # Spanish Aliases for backwards compatibility
        @self.tree.command(name="entrar", description="El bot entra a tu canal de voz y lee este canal de texto")
        async def entrar_alias(inter: discord.Interaction):
            await _join_handler(inter)

        @self.tree.command(name="salir", description="El bot sale del canal de voz")
        async def salir_alias(inter: discord.Interaction):
            await _leave_handler(inter)

        @self.tree.command(name="decir", description="Decir un texto en el canal de voz")
        @app_commands.describe(texto="Texto a reproducir")
        async def decir_alias(inter: discord.Interaction, texto: str):
            await _say_handler(inter, texto)

        @self.tree.command(name="voz", description="Cambiar perfil de voz de VoiceStudio")
        @app_commands.describe(nombre="ID o nombre de voz")
        async def voz_alias(inter: discord.Interaction, nombre: str):
            await _voice_handler(inter, nombre)

        @self.tree.command(name="saltar", description="Cortar reproducción actual y vaciar cola")
        async def saltar_alias(inter: discord.Interaction):
            await _skip_handler(inter)


if __name__ == "__main__":
    cfg = load_config()
    if not cfg["token"]:
        raise SystemExit("Missing DISCORD_TOKEN in .env (or configure it via panel.py).")
    TTSBot(cfg).run(cfg["token"], root_logger=True)
