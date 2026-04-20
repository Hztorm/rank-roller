import asyncio
import json
import logging
import os
import tempfile

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from cogs.ranks_cog import RanksCog
from cogs.music_cog import MusicCog

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rankbot")

# ─── Config ───────────────────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

# ─── Bot setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=lambda _, m: ["!"] if m.content.startswith("!") else [],
    intents=intents,
)
bot.remove_command("help")

# ─── In-memory state ──────────────────────────────────────────────────────────
data: dict   = {}
_dirty: bool = False


def mark_dirty() -> None:
    global _dirty
    _dirty = True


# ─── Data persistence ─────────────────────────────────────────────────────────
def load_data() -> None:
    global data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    for udata in data.values():
        udata.setdefault("rank_counts", {})
        udata.setdefault("rolls", 0)
        udata.setdefault("current_rank", "None")

    log.info("Loaded %d user records from disk.", len(data))


def save_data() -> None:
    """Atomic write — a crash mid-save cannot corrupt data.json."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=BASE_DIR, delete=False, suffix=".tmp") as f:
            json.dump(data, f, indent=4)
            tmp_path = f.name
        os.replace(tmp_path, DATA_FILE)
        log.debug("Data flushed to disk (%d users).", len(data))
    except Exception:
        log.exception("Failed to save data.")
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@tasks.loop(seconds=60)
async def flush_loop() -> None:
    global _dirty
    if _dirty:
        save_data()
        _dirty = False


# ─── Events ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready() -> None:
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    flush_loop.start()
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game("!help"),
    )


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("❌ This command can only be used in a server.")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"⏳ Slow down! Try again in **{error.retry_after:.1f}s**.",
            delete_after=5,
        )
        return
    log.error("Command error in %s: %s", ctx.command, error)


# ─── Shutdown ─────────────────────────────────────────────────────────────────
async def shutdown() -> None:
    if _dirty:
        log.info("Flushing unsaved data before shutdown...")
        save_data()


# ─── Entry point ──────────────────────────────────────────────────────────────
async def main() -> None:
    load_data()
    await bot.add_cog(RanksCog(bot, data, mark_dirty))
    await bot.add_cog(MusicCog(bot))
    try:
        await bot.start(TOKEN)
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
