import asyncio
import collections
import logging
import urllib.parse
import random

import discord
import yt_dlp
from discord.ext import commands

log = logging.getLogger("rankbot")

# ─── yt-dlp / FFmpeg config ───────────────────────────────────────────────────
_YTDLP_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

_FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

INTRO_PATHS = [
    "assets/Pukkiradio.wav",
#    "assets/Pukkiradio2.wav",
#    "assets/Pukkiradio3.wav",
]

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _is_url(text: str) -> bool:
    return urllib.parse.urlparse(text).scheme in ("http", "https")


async def _ytdlp_extract(query: str, *, search: bool = False) -> dict | None:
    opts = dict(_YTDLP_OPTS)
    if search:
        opts["default_search"] = "ytsearch1"

    def _extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if not info:
                return None
            if "entries" in info:
                info = info["entries"][0] if info["entries"] else None
            return info

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _extract)
    if not info:
        return None
    return {
        "title":       info.get("title", "Unknown"),
        "url":         info["url"],
        "webpage_url": info.get("webpage_url", query),
        "duration":    info.get("duration", 0),
    }


async def _resolve_query(query: str) -> list[dict]:
    info = await _ytdlp_extract(query, search=not _is_url(query))
    if not info:
        raise ValueError("No results found.")
    return [info]


# ─── Per-guild state ──────────────────────────────────────────────────────────
class GuildMusicState:
    def __init__(self) -> None:
        self.queue = collections.deque()
        self.current = None
        self.voice_client = None
        self.idle_task: asyncio.Task | None = None
        # FIX 4: flag set when a skip/stop is requested so the intro
        # callback doesn't launch the next track after we've moved on.
        self.skip_requested: bool = False

    def is_playing(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_playing()

    def is_paused(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_paused()


# ─── Cog ──────────────────────────────────────────────────────────────────────
class MusicCog(commands.Cog, name="Music"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot     = bot
        self._states: dict[int, GuildMusicState] = {}

    def _get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    def _after_track(self, guild_id: int, error: Exception | None) -> None:
        if error:
            log.error("Playback error in guild %s: %s", guild_id, error)

        state = self._get_state(guild_id)

        # if nothing left, start idle disconnect
        if not state.queue:
            # FIX 1: use run_coroutine_threadsafe instead of create_task —
            # _after_track runs in a worker thread, not the event loop thread.
            if state.idle_task and not state.idle_task.done():
                state.idle_task.cancel()

            state.idle_task = asyncio.run_coroutine_threadsafe(
                self._idle_disconnect(guild_id, state, timeout=60),
                self.bot.loop,
            )
            return

        # otherwise continue
        asyncio.run_coroutine_threadsafe(
            self._advance(guild_id, state),
            self.bot.loop
        )

    async def _advance(self, guild_id: int, state: GuildMusicState) -> None:
        # cancel idle timer if running (may be asyncio.Task or concurrent.futures.Future)
        if state.idle_task:
            state.idle_task.cancel()
        state.idle_task = None

        if not state.queue:
            state.current = None
            return

        track = state.queue.popleft()
        state.current = track
        # FIX 4: clear the skip flag for the new track
        state.skip_requested = False

        vc = state.voice_client
        if not vc or not vc.is_connected():
            return

        # --- play intro first, then track ---
        def play_track():
            source = discord.FFmpegPCMAudio(track["url"], **_FFMPEG_OPTS)
            source = discord.PCMVolumeTransformer(source, volume=0.5)

            vc.play(
                source,
                after=lambda e: self._after_track(guild_id, e),
            )

        def play_intro():
            intro_path = random.choice(INTRO_PATHS)
            intro = discord.FFmpegPCMAudio(intro_path)

            def after_intro(err):
                if err:
                    log.error("Intro playback error: %s", err)
                # FIX 4: only start the track if no skip/stop was requested
                # while the intro was playing.
                if not state.skip_requested and vc.is_connected():
                    play_track()

            vc.play(intro, after=after_intro)

        play_intro()

    async def _idle_disconnect(self, guild_id: int, state: GuildMusicState, timeout: int = 60):
        # FIX 2: changed default timeout from 1 → 60 to match call-site intent.
        await asyncio.sleep(timeout)

        # re-check state after waiting
        if state.queue:
            return

        vc = state.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            return

        if vc:
            try:
                await vc.disconnect()
            except Exception as e:
                log.error("Idle disconnect failed: %s", e)

        state.voice_client = None
        state.current = None
        state.idle_task = None

    async def _ensure_voice(self, ctx: commands.Context) -> discord.VoiceClient | None:
        state = self._get_state(ctx.guild.id)

        if ctx.author.voice is None:
            await ctx.send("❌ You must be in a voice channel first.")
            return None

        channel = ctx.author.voice.channel

        if state.voice_client is None or not state.voice_client.is_connected():
            try:
                state.voice_client = await channel.connect()
            except discord.ClientException as exc:
                await ctx.send(f"❌ Could not connect: {exc}")
                return None
        elif state.voice_client.channel != channel:
            await state.voice_client.move_to(channel)

        return state.voice_client

    @commands.command(name="play", aliases=["p"])
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def cmd_play(self, ctx: commands.Context, *, query: str) -> None:
        """Play a song or add it to the queue. Accepts YouTube URLs or search terms."""
        vc = await self._ensure_voice(ctx)
        if vc is None:
            return

        async with ctx.typing():
            try:
                tracks = await _resolve_query(query)
            except Exception as exc:
                await ctx.send(f"❌ Could not resolve query: {exc}")
                return

        state = self._get_state(ctx.guild.id)
        for t in tracks:
            state.queue.append(t)

        embed = discord.Embed(
            title="🎵 Added to Queue",
            description=f"[{tracks[0]['title']}]({tracks[0]['webpage_url']})",
            color=0x1DB954,
        )
        await ctx.send(embed=embed)

        if not state.is_playing() and not state.is_paused():
            await self._advance(ctx.guild.id, state)

    @commands.command(name="pause")
    @commands.guild_only()
    async def cmd_pause(self, ctx: commands.Context) -> None:
        """Pause the current track."""
        state = self._get_state(ctx.guild.id)
        if state.is_playing():
            state.voice_client.pause()
            await ctx.send("⏸️ Paused.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name="resume")
    @commands.guild_only()
    async def cmd_resume(self, ctx: commands.Context) -> None:
        """Resume a paused track."""
        state = self._get_state(ctx.guild.id)
        if state.is_paused():
            state.voice_client.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("Nothing is paused.")

    @commands.command(name="stop")
    @commands.guild_only()
    async def cmd_stop(self, ctx: commands.Context) -> None:
        """Stop playback, clear the queue, and disconnect."""
        state = self._get_state(ctx.guild.id)
        state.queue.clear()
        state.current = None
        # FIX 4: signal any in-progress intro to not launch the track
        state.skip_requested = True

        if state.voice_client:
            if state.voice_client.is_playing() or state.voice_client.is_paused():
                state.voice_client.stop()

            await state.voice_client.disconnect()
            state.voice_client = None

        if state.idle_task:
            state.idle_task.cancel()
            state.idle_task = None
        await ctx.send("⏹️ Stopped and disconnected.")

    @commands.command(name="skip", aliases=["s"])
    @commands.guild_only()
    async def cmd_skip(self, ctx: commands.Context) -> None:
        """Skip the current track."""
        state = self._get_state(ctx.guild.id)
        if state.is_playing() or state.is_paused():
            # FIX 4: set the flag before stopping so after_intro (if the
            # intro is mid-playback) won't launch the track we're skipping.
            state.skip_requested = True
            state.voice_client.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name="queue", aliases=["q"])
    @commands.guild_only()
    async def cmd_queue(self, ctx: commands.Context) -> None:
        """Show the current queue."""
        state = self._get_state(ctx.guild.id)

        embed = discord.Embed(title="🎶 Music Queue", color=0x1DB954)

        if state.current:
            embed.add_field(
                name="▶️ Now Playing",
                value=f"[{state.current['title']}]({state.current['webpage_url']})",
                inline=False,
            )

        if state.queue:
            lines = []
            for i, t in enumerate(list(state.queue)[:10], start=1):
                lines.append(f"`{i}.` [{t['title']}]({t['webpage_url']})")
            if len(state.queue) > 10:
                lines.append(f"…and {len(state.queue) - 10} more.")
            embed.add_field(name="Up Next", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Up Next", value="Queue is empty.", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"])
    @commands.guild_only()
    async def cmd_nowplaying(self, ctx: commands.Context) -> None:
        """Show what's currently playing."""
        state = self._get_state(ctx.guild.id)
        if not state.current:
            await ctx.send("Nothing is playing right now.")
            return

        t = state.current
        mins, secs = divmod(t.get("duration", 0), 60)
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{t['title']}]({t['webpage_url']})",
            color=0x1DB954,
        )
        if mins or secs:
            embed.add_field(name="Duration", value=f"{mins}:{secs:02d}")
        await ctx.send(embed=embed)
