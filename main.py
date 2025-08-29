# main.py
import os
import sys
import discord
import asyncio
import aiohttp
import random
import re
import pytz
from discord.ext import commands
from datetime import datetime, timedelta
from dotenv import load_dotenv
from keep_alive import keep_alive  # serwer do podtrzymania na Render

# ─── Konfiguracja i walidacja env ──────────────────────────────────────────────
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")

if not TOKEN:
    print("❌ Brak DISCORD_TOKEN w zmiennych środowiskowych (.env / Render → Environment).")
    sys.exit(1)

try:
    CHANNEL_ID = int(CHANNEL_ID_RAW) if CHANNEL_ID_RAW is not None else None
except ValueError:
    CHANNEL_ID = None

if CHANNEL_ID is None:
    print("❌ Brak lub niepoprawny CHANNEL_ID w zmiennych środowiskowych.")
    sys.exit(1)

# ─── Bot ───────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# przechowuje 20 ostatnich linków wysłanych memów (by nie duplikować)
seen_memes: list[str] = []

# ─── Pobieranie stron ─────────────────────────────────────────────────────────
async def fetch(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
            if r.status != 200:
                return None
            return await r.text()
    except Exception:
        return None

# ─── Scrapery ─────────────────────────────────────────────────────────────────
async def get_meme_from_jeja():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://jeja.pl/")
        if not html:
            return None
        imgs = re.findall(r'<img src="(https://i\.jeja\.pl/[^"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_besty():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://besty.pl/")
        if not html:
            return None
        imgs = re.findall(r'<img src="(https://img\.besty\.pl/[^"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_wykop():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://wykop.pl/hity")
        if not html:
            return None
        imgs = re.findall(r'<img src="(https://[^"]+\.jpg)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_memypl():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://memy.pl/")
        if not html:
            return None
        imgs = re.findall(r'<img src="(https://memy\.pl/memes/[^"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_9gag():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://9gag.com/")
        if not html:
            return None
        imgs = re.findall(r'<img src="(https://img-9gag-fun\.9cache\.com/photo/[^"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_demotywatory():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://demotywatory.pl/")
        if not html:
            return None
        imgs = re.findall(r'<img src="(https://img\.demotywatory\.pl/uploads/[^"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_kwejk():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://kwejk.pl/")
        if not html:
            return None
        imgs = re.findall(r'<img src="(https://i1\.kwejk\.pl/k/[^"]+)"', html)
        return random.choice(imgs) if imgs else None

# ─── Fallback API ─────────────────────────────────────────────────────────────
async def get_meme_from_api():
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get("https://meme-api.com/gimme") as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return data.get("url")
        except Exception:
            return None

# ─── Losowanie memów (z pamięcią 20 ostatnich) ───────────────────────────────
async def get_random_memes(count: int = 2):
    memes: list[str] = []
    funcs = [
        get_meme_from_jeja,
        get_meme_from_besty,
        get_meme_from_wykop,
        get_meme_from_memypl,
        get_meme_from_9gag,
        get_meme_from_demotywatory,
        get_meme_from_kwejk,
    ]

    attempts = 0
    while len(memes) < count and attempts < 15:
        func = random.choice(funcs)
        meme = await func()
        attempts += 1

        if not meme:
            meme = await get_meme_from_api()

        if meme and meme not in seen_memes and meme not in memes:
            memes.append(meme)
            seen_memes.append(meme)
            if len(seen_memes) > 20:
                seen_memes.pop(0)

    return memes

# ─── Wysyłanie memów ──────────────────────────────────────────────────────────
async def send_memes():
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"❌ Nie znaleziono kanału o ID {CHANNEL_ID}. Upewnij się, że bot jest na serwerze i widzi kanał.")
        return

    memes = await get_random_memes(2)
    if memes:
        for m in memes:
            await channel.send(m)
    else:
        await channel.send("⚠️ Nie udało się znaleźć memów!")

# ─── Komendy ──────────────────────────────────────────────────────────────────
@bot.command(name="memy")
async def memy(ctx: commands.Context):
    memes = await get_random_memes(2)
    if memes:
        for m in memes:
            await ctx.send(m)
    else:
        await ctx.send("⚠️ Nie udało się znaleźć memów!")

# ─── Reakcja na ❤️ + losowe zdjęcie z folderu images ──────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if message.content.strip() == "❤️":
        folder = "images"
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if files:
                img = random.choice(files)
                await message.channel.send("Sztefyn też 사랑해요", file=discord.File(os.path.join(folder, img)))
                return
        # gdy nie ma obrazków – wyślij sam tekst
        await message.channel.send("Sztefyn też 사랑해요")
        return

    # bardzo ważne – pozwala działać komendom po nadpisaniu on_message
    await bot.process_commands(message)

# ─── Harmonogram ──────────────────────────────────────────────────────────────
async def schedule_memes():
    tz = pytz.timezone("Europe/Warsaw")
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now(tz)
        targets = [(11, 0), (21, 37)]
        next_time = None

        for hour, minute in targets:
            t = tz.localize(datetime(now.year, now.month, now.day, hour, minute))
            if t > now:
                next_time = t
                break

        if not next_time:
            next_time = tz.localize(datetime(now.year, now.month, now.day, 11, 0)) + timedelta(days=1)

        wait_seconds = max(1, int((next_time - now).total_seconds()))
        print(f"⏳ Czekam {wait_seconds/3600:.2f}h do wysyłki")
        await asyncio.sleep(wait_seconds)
        await send_memes()

# ─── Start ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user} (ID: {bot.user.id})")

async def main():
    keep_alive()  # odpala serwer Flask, żeby Render nie usypiał usługi
    async with bot:
        asyncio.create_task(schedule_memes())
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
