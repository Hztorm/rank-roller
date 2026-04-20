import logging
import random

import discord
import matplotlib.pyplot as plt
from discord.ext import commands
from io import BytesIO

from ranks import ranks, RANK_BY_NAME, _RANK_NAMES, _RANK_WEIGHTS

log = logging.getLogger("rankbot")

# ─── Cooldowns (seconds) ──────────────────────────────────────────────────────
COOLDOWNS = {
    "help":        5,
    "rank":        5,
    "history":     5,
    "rankgraph":  10,
    "leaderboard": 5,
}


# ─── Game logic ───────────────────────────────────────────────────────────────
def roll_rank() -> dict:
    """O(1) weighted roll using precomputed weights."""
    name = random.choices(_RANK_NAMES, weights=_RANK_WEIGHTS, k=1)[0]
    return RANK_BY_NAME[name]


# ─── Role cache ───────────────────────────────────────────────────────────────
_role_cache: dict = {}  # guild_id → {role_name: Role}


def get_role(guild: discord.Guild, name: str) -> discord.Role | None:
    cache = _role_cache.setdefault(guild.id, {})
    if name not in cache:
        role = discord.utils.get(guild.roles, name=name)
        if role:
            cache[name] = role
    return cache.get(name)


def invalidate_role_cache(guild_id: int) -> None:
    _role_cache.pop(guild_id, None)


# ─── Cog ──────────────────────────────────────────────────────────────────────
class RanksCog(commands.Cog, name="Ranks"):
    def __init__(self, bot: commands.Bot, data: dict, mark_dirty) -> None:
        self.bot        = bot
        self.data       = data        # shared reference from bot.py
        self.mark_dirty = mark_dirty  # callback to signal unsaved changes

    def _init_user(self, user_id: str) -> None:
        if user_id not in self.data:
            self.data[user_id] = {"rolls": 0, "current_rank": "None", "rank_counts": {}}
        else:
            self.data[user_id].setdefault("rank_counts", {})
            self.data[user_id].setdefault("rolls", 0)
            self.data[user_id].setdefault("current_rank", "None")

    def _record_roll(self, user_id: str, rank: dict) -> None:
        self._init_user(user_id)
        self.data[user_id]["rolls"] += 1
        self.data[user_id]["current_rank"] = rank["name"]
        self.data[user_id]["rank_counts"][rank["name"]] = (
            self.data[user_id]["rank_counts"].get(rank["name"], 0) + 1
        )
        self.mark_dirty()

    # ── Events ────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        invalidate_role_cache(role.guild.id)

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(name="roll")
    @commands.guild_only()
    async def cmd_roll(self, ctx: commands.Context) -> None:
        rank     = roll_rank()
        user_id  = str(ctx.author.id)
        old_rank = self.data.get(user_id, {}).get("current_rank", "None")
        new_rank = rank["name"]

        self._record_roll(user_id, rank)

        member = ctx.guild.get_member(ctx.author.id)
        if member is None:
            try:
                member = await ctx.guild.fetch_member(ctx.author.id)
            except discord.HTTPException:
                log.warning("Could not fetch member %s.", ctx.author.id)
                return

        if old_rank != new_rank:
            old_role = get_role(ctx.guild, old_rank)
            if old_role and old_role in member.roles:
                await member.remove_roles(old_role)
            new_role = get_role(ctx.guild, new_rank)
            if new_role:
                await member.add_roles(new_role)

        embed = discord.Embed(
            title="🎲 Roll Result",
            description=(
                f"{ctx.author.mention} rolled **{new_rank}**!\n"
                f"Chance: 1 in {rank['odds']}\n"
                f"Previous: {old_rank} → Now: **{new_rank}**"
            ),
            color=rank["color"],
        )
        await ctx.send(embed=embed)

    @commands.command(name="help")
    @commands.guild_only()
    @commands.cooldown(1, COOLDOWNS["help"], commands.BucketType.user)
    async def cmd_help(self, ctx: commands.Context) -> None:
        embed = discord.Embed(title="📖 Bot Commands", color=0x00FF00)
        embed.add_field(name="🎲 !roll",        value="Roll a random rank.",               inline=False)
        embed.add_field(name="👁️ !rankgraph",   value="Shows graph of your roll history.", inline=False)
        embed.add_field(name="🫨 !history",     value="Shows roll history.",               inline=False)
        embed.add_field(name="📊 !rank",        value="Show your current rank and stats.", inline=False)
        embed.add_field(name="🏆 !leaderboard", value="Show top players by rank.",         inline=False)
        embed.add_field(name="─── Music ───",   value="\u200b",                            inline=False)
        embed.add_field(name="🎵 !play <query>",value="Play from YouTube URL or search.",  inline=False)
        embed.add_field(name="⏸️ !pause",       value="Pause playback.",                   inline=False)
        embed.add_field(name="▶️ !resume",      value="Resume playback.",                  inline=False)
        embed.add_field(name="⏭️ !skip",        value="Skip the current track.",           inline=False)
        embed.add_field(name="⏹️ !stop",        value="Stop and disconnect.",              inline=False)
        embed.add_field(name="🎶 !queue",       value="Show the queue.",                   inline=False)
        embed.add_field(name="🎵 !nowplaying",  value="Show the current track.",           inline=False)
        embed.add_field(name="❓ !help",        value="Show this help menu.",              inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="rankgraph")
    @commands.guild_only()
    @commands.cooldown(1, COOLDOWNS["rankgraph"], commands.BucketType.user)
    async def cmd_rankgraph(self, ctx: commands.Context) -> None:
        user_id   = str(ctx.author.id)
        user_data = self.data.get(user_id)

        if not user_data or not user_data.get("rank_counts"):
            await ctx.send("No roll history yet. Use !roll first.")
            return

        counts       = user_data["rank_counts"]
        sorted_ranks = sorted(ranks, key=lambda r: r["score"])
        names        = [r["name"] for r in sorted_ranks]
        values       = [max(counts.get(r["name"], 0), 0.9) for r in sorted_ranks]
        colors       = [f"#{r['color']:06x}" for r in sorted_ranks]

        try:
            plt.figure(figsize=(10, 5))
            plt.bar(names, values, color=colors, edgecolor="black", linewidth=1)
            plt.yscale("log")
            plt.ylim(bottom=0.9)
            plt.xticks(rotation=45, ha="right")
            plt.xlabel("Ranks")
            plt.ylabel("Times Rolled")
            plt.title(f"{ctx.author.name}'s Rank Distribution")
            plt.tight_layout()

            buffer = BytesIO()
            plt.savefig(buffer, format="png")
            buffer.seek(0)
        finally:
            plt.close()

        await ctx.send(file=discord.File(buffer, "rank_graph.png"))

    @commands.command(name="history")
    @commands.guild_only()
    @commands.cooldown(1, COOLDOWNS["history"], commands.BucketType.user)
    async def cmd_history(self, ctx: commands.Context) -> None:
        user_id   = str(ctx.author.id)
        user_data = self.data.get(user_id)

        if not user_data or not user_data.get("rank_counts"):
            await ctx.send("No roll history yet. Use !roll first.")
            return

        counts      = user_data["rank_counts"]
        total_rolls = user_data.get("rolls", 0)

        sorted_counts = sorted(
            counts.items(),
            key=lambda x: RANK_BY_NAME[x[0]]["score"] if x[0] in RANK_BY_NAME else 0,
            reverse=True,
        )

        embed = discord.Embed(
            title=f"📜 {ctx.author.name}'s Roll History",
            color=0x00FFFF,
        )
        char_count = 0
        for rank_name, amount in sorted_counts:
            pct   = (amount / total_rolls * 100) if total_rolls > 0 else 0
            value = f"{amount} times ({pct:.1f}%)"
            char_count += len(rank_name) + len(value)
            if char_count > 5000:
                embed.set_footer(text="Some ranks omitted due to Discord's embed limit.")
                break
            embed.add_field(name=rank_name, value=value, inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="leaderboard")
    @commands.guild_only()
    @commands.cooldown(1, COOLDOWNS["leaderboard"], commands.BucketType.user)
    async def cmd_leaderboard(self, ctx: commands.Context) -> None:
        if not self.data:
            await ctx.send("No data yet.")
            return

        def current_score(udata: dict) -> int:
            rank = RANK_BY_NAME.get(udata.get("current_rank", "None"))
            return rank["score"] if rank else 0

        sorted_users = sorted(
            self.data.items(),
            key=lambda x: (current_score(x[1]), -x[1].get("rolls", 0)),
            reverse=True,
        )

        embed = discord.Embed(title="🏆 Current Rank Leaderboard", color=0x00FF00)
        char_count = 0
        for i, (user_id, stats) in enumerate(sorted_users[:10], start=1):
            try:
                member    = ctx.guild.get_member(int(user_id))
                username  = member.name if member else f"User {user_id}"
                rank_name = stats.get("current_rank", "None")
                rank_obj  = RANK_BY_NAME.get(rank_name)
                odds_text = f"1 in {rank_obj['odds']}" if rank_obj else "Unknown"
                name_str  = f"{i}. {username}"
                value_str = f"Rank: {rank_name} ({odds_text}) | Rolls: {stats.get('rolls', 0)}"
                char_count += len(name_str) + len(value_str)
                if char_count > 5000:
                    embed.set_footer(text="Some entries omitted due to Discord's embed limit.")
                    break
                embed.add_field(name=name_str, value=value_str, inline=False)
            except Exception:
                log.exception("Leaderboard error for user %s.", user_id)

        await ctx.send(embed=embed)

    @commands.command(name="rank")
    @commands.guild_only()
    @commands.cooldown(1, COOLDOWNS["rank"], commands.BucketType.user)
    async def cmd_rank(self, ctx: commands.Context) -> None:
        user_id   = str(ctx.author.id)
        user_data = self.data.get(user_id)

        if not user_data:
            await ctx.send("You have no rank yet. Use !roll first.")
            return

        rank_name = user_data.get("current_rank", "None")
        rank_obj  = RANK_BY_NAME.get(rank_name)

        if not rank_obj:
            await ctx.send("Your rank data is corrupted.")
            return

        total_rolls = user_data.get("rolls", 0)
        rank_count  = user_data.get("rank_counts", {}).get(rank_name, 0)
        pct         = (rank_count / total_rolls * 100) if total_rolls > 0 else 0

        embed = discord.Embed(title="📊 Your Rank", color=rank_obj["color"])
        embed.add_field(name="Rank",               value=rank_name,                  inline=False)
        embed.add_field(name="Chance",             value=f"1 in {rank_obj['odds']}", inline=False)
        embed.add_field(name="Score",              value=rank_obj["score"],           inline=False)
        embed.add_field(name="Total Rolls",        value=total_rolls,                 inline=False)
        embed.add_field(name="Times as this rank", value=f"{rank_count} ({pct:.1f}%)", inline=False)
        await ctx.send(embed=embed)
