## Prerequisites

Before you start, make sure you have the following installed:

- **Python 3.10+** — [python.org/downloads](https://www.python.org/downloads/)
- **FFmpeg**

---

## Step 1

Open a terminal and run:

```bash
git clone https://https://github.com/Hztorm/rank-roller.git
cd rank-roller
```

or save the code as a zip from the top right on github

---

## Step 2 — Install Python Dependencies

```bash
pip install discord.py yt-dlp python-dotenv matplotlib
```

---

## Step 3 — Install FFmpeg

FFmpeg is required for music playback:

**Windows:**
1. Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extract the zip and copy `ffmpeg.exe` into your project folder, or add it to your system PATH.

**Mac (with Homebrew):**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install ffmpeg
```
---

## Step 4 — Create a Bot

1. [discord.com/developers/applications](https://discord.com/developers/applications) -> **New Application**.
2. **Bot** -> **Add Bot**.
3. Under **Privileged Gateway Intents**, enable:
   - **Server Members Intent**
   - **Message Content Intent**
4. **Reset Token**, save your bot-token, DONT SHARE IT.

---

## Step 5 — .env File

Create a file named `.env` in the root of your project folder:

```
DISCORD_TOKEN=bot-token
```

---

## Step 6 — Invite the Bot

1. In the Discord Developer Portal, **OAuth2** -> **URL Generator**.
2. Under **Scopes**, check `bot`.
3. Under **Bot Permissions**, check:
   - `Send Messages`
   - `Read Message History`
   - `Connect` (for voice)
   - `Speak` (for voice)
   - `Manage Roles` (for rank assignment)
4. Copy the generated URL, open it in your browser, and invite the bot to your server.

---

## Step 7 — Run the Bot

```bash
python bot.py
```

If everything is configured correctly, you'll see a log message like:

```
Logged in as YourBot#1234 (ID: 123456789)
```

The bot is now online. Try `!help` in your Discord server to see all available commands.

---

## SETUP

## Ranks.py

The bot assigns ranks based on the **ranks.py** file, the names of your ranks must match **EXACTLY** with the ones on your server for the bot to be able to assign them.

**Odds** is how likely you are to roll the rank, the higher the rarer. (**1/odds** to roll roughly)

Color is the color of the rank in the roll message.

Keep score in order from 1->...
---

## Audio Assets (Optional)

The music player plays an intro between every song, you add & change these in **/assets**
match the names of your intros in:
`cogs/music_cog.py`

```
INTRO_PATHS = [
    "assets/Pukkiradio.wav",
#    "assets/Pukkiradio2.wav",
#    "assets/Pukkiradio3.wav",
]
```
If you have many it will pick a random one.

---

## MISC

Bot status can be changed in bot.py:
´´´
@bot.event
async def on_ready() -> None:
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    flush_loop.start()
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game("!help"),
    )
´´´

## Available Commands

| Command | Description |
|---|---|
| `!roll` | Roll a random rank |
| `!rank` | Show your current rank and stats |
| `!history` | Show your full roll history |
| `!rankgraph` | Display a graph of your roll distribution |
| `!leaderboard` | Show top players by rank |
| `!play <query>` | Play a song from YouTube (URL or search) |
| `!pause` | Pause playback |
| `!resume` | Resume playback |
| `!skip` | Skip the current track |
| `!stop` | Stop playback and disconnect |
| `!queue` | Show the current music queue |
| `!nowplaying` | Show the current track |
| `!help` | Show the help menu |

---