# main.py
import os
import sys
import discord
import asyncio
from bs4 import BeautifulSoup
import aiohttp
import random
import glob
import pytz
from discord.ext import commands
from datetime import datetime, timedelta
from keep_alive import keep_alive  # serwer do podtrzymania na Render

# ─── Konfiguracja i walidacja env ──────────────────────────────────────────────
import os
import sys

# pobieramy token i ID kanału bez użycia .env
TOKEN = "".join(os.environ.get("DISCORD_TOKEN", "").split())  # usuwa spacje i nowe linie
CHANNEL_ID_RAW = os.environ.get("CHANNEL_ID", "").strip()
try:
    CHANNEL_ID = int(CHANNEL_ID_RAW) if CHANNEL_ID_RAW else None
except ValueError:
    CHANNEL_ID = None

HEART_CHANNEL_ID_RAW = os.environ.get("HEART_CHANNEL_ID", "").strip()
try:
    HEART_CHANNEL_ID = int(HEART_CHANNEL_ID_RAW) if HEART_CHANNEL_ID_RAW else None
except ValueError:
    HEART_CHANNEL_ID = None

ANKIETA_CHANNEL_ID_RAW = os.environ.get("ANKIETA_CHANNEL_ID", "").strip()
try:
    ANKIETA_CHANNEL_ID = int(ANKIETA_CHANNEL_ID_RAW) if ANKIETA_CHANNEL_ID_RAW else None
except ValueError:
    ANKIETA_CHANNEL_ID = None

# debug – sprawdzenie tokena
print(f"DEBUG TOKEN: '{TOKEN}' | length: {len(TOKEN)}")
print(f"DEBUG CHANNEL_ID: '{CHANNEL_ID_RAW}'")

# pobierz ID kanału na serca (może być inny niż główny)


# walidacja tokena
if not TOKEN:
    print("❌ Brak DISCORD_TOKEN w zmiennych środowiskowych (Render Environment Variables).")
    sys.exit(1)

# walidacja ID kanału
try:
    CHANNEL_ID = int(CHANNEL_ID_RAW) if CHANNEL_ID_RAW else None
except ValueError:
    CHANNEL_ID = None

if CHANNEL_ID is None:
    print("❌ Brak lub niepoprawny CHANNEL_ID w zmiennych środowiskowych.")
    sys.exit(1)

# ─── Ładowanie tekstów podrywu ──────────────────────────
def load_pickup_lines(file_path="Podryw.txt") -> list[str]:
    if not os.path.exists(file_path):
        print(f"⚠️ Plik {file_path} nie istnieje! Używam pustej listy.")
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    print(f"✅ Załadowano {len(lines)} tekstów podrywu z {file_path}")
    return lines

pickup_lines = load_pickup_lines()

# ─── Ankieta  ───────────────────────────────────────────────────────────────────────
async def send_ankieta(target_channel=None):
    if not target_channel:
        target_channel = bot.get_channel(ANKIETA_CHANNEL_ID)
    if not target_channel:
        print("❌ Nie znaleziono kanału do ankiet")
        return

    folder = "Ankieta"
    files = glob.glob(os.path.join(folder, "*.txt"))
    if not files:
        await target_channel.send("⚠️ Brak plików z ankietami w folderze `Ankieta`!")
        return

    file = random.choice(files)
    with open(file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) < 2:
        await target_channel.send("⚠️ Plik ankiety musi mieć pytanie i co najmniej jedną opcję!")
        return

    pytanie = lines[0]
    opcje = lines[1:]

    description = ""
    emojis = []
    for opt in opcje:
        if " " not in opt:
            continue
        emoji, name = opt.split(" ", 1)
        emojis.append(emoji)
        description += f"{emoji} {name}\n"

    embed = discord.Embed(title=f"📊 {pytanie}", description=description, color=0x7289da)
    msg = await target_channel.send(embed=embed)

    for emoji in emojis:
        await msg.add_reaction(emoji)
        
# ─── Bot ───────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True  # <── WAŻNE: pozwala wykrywać reakcje emoji
bot = commands.Bot(command_prefix="!", intents=intents)

# przechowuje 20 ostatnich linków wysłanych memów (by nie duplikować)
seen_memes: list[str] = []
# przechowuje 20 ostatnich wysłanych obrazków z folderu images
seen_images: list[str] = []
# przechowuje ostatnie odpowiedzi na ❤️ (by nie powtarzać za często)
recent_responses: list[str] = []


# ─── Pobieranie stron ─────────────────────────────────────────────────────────
async def fetch(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
            if r.status != 200:
                return None
            return await r.text()
    except Exception:
        return None

# ─── Scrapery ────────────────────────────────────────────────────────────────
headers = {"User-Agent": "Mozilla/5.0"}

async def get_meme_from_jeja():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://jeja.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "jeja.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_besty():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://besty.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "besty.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_memypl():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://memy.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "memy.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_9gag():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://9gag.com/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "9cache.com" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_demotywatory():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://demotywatory.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "demotywatory.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_strefabeki():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://strefabeki.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "strefabeki.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_chamsko():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://chamsko.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "chamsko.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_memland():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://memland.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "memland.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_memsekcja():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://memsekcja.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "memsekcja.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_paczaizm():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://paczaizm.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "paczaizm.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_memowo():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://memowo.pl/")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "memowo.pl" in i]
        return random.choice(imgs) if imgs else None


async def get_random_memes(count: int = 2):
    memes: list[str] = []
    funcs = [
        get_meme_from_jeja,
        get_meme_from_besty,
        get_meme_from_memypl,
        get_meme_from_9gag,
        get_meme_from_demotywatory,
        get_meme_from_strefabeki,
        get_meme_from_chamsko,
        get_meme_from_memland,
        get_meme_from_memsekcja,
        get_meme_from_paczaizm,
        get_meme_from_memowo,
    ]

    attempts = 0
    while len(memes) < count and attempts < 20:
        func = random.choice(funcs)
        meme = await func()
        attempts += 1

        if meme and meme not in seen_memes and meme not in memes:
            memes.append(meme)
            seen_memes.append(meme)
            if len(seen_memes) > 20:
                seen_memes.pop(0)

    return memes

# ─── Losowe komentarze ────────────────────────────────────────────────────────
meme_comments = [
    "XD",
    "🔥🔥🔥",
    "idealny na dziś",
    "no i sztos",
    "😂😂😂",
    "aż się popłakałem",
    "ten mem to złoto",
    "classic",
    "to chyba o mnie",
    "💀💀💀",
]

def get_random_comment():
    return random.choice(meme_comments) if random.random() < 0.7 else ""  
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    content = message.content.strip().lower()

    # ─── Komenda "memy" ─────────────────────────────
    if content == "memy":
        memes = await get_random_memes(2)
        if memes:
            for m in memes:
                await message.channel.send(m)
        else:
            await message.channel.send("⚠️ Nie udało się znaleźć memów!")
        await bot.process_commands(message)
        return

    # ─── Komenda "ankieta" ───────────────────────────
    if content == "ankieta":
        await send_ankieta()  # zawsze na ANKIETA_CHANNEL_ID
        await message.add_reaction("✅")
        await bot.process_commands(message)
        return

    # ─── Reakcja ❤️ ─────────────────────────────────
    HEART_EMOJIS = [
        "<3", "❤", "❤️", "♥️", "♥",
        "🤍", "💙", "🩵", "💚", "💛", "💜",
        "🖤", "🤎", "🧡", "💗", "🩶", "🩷",
    ]

    if any(heart in message.content.replace(" ", "") for heart in HEART_EMOJIS):
        target_channel = bot.get_channel(HEART_CHANNEL_ID) or message.channel

        folder = "images"

        # Losowa odpowiedź z Podryw.txt
        if not pickup_lines:
            response_text = "❤️ ...ale brak tekstów w pliku Podryw.txt!"
        else:
            available = [r for r in pickup_lines if r not in recent_responses] or pickup_lines
            response_text = random.choice(available)
            recent_responses.append(response_text)
            if len(recent_responses) > 40:
                recent_responses.pop(0)

        # Losowy obrazek z folderu images
        img = None
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if files:
                available_images = [f for f in files if f not in seen_images] or files
                img = random.choice(available_images)
                seen_images.append(img)
                if len(seen_images) > 180:
                    seen_images.pop(0)

        # Wysyłka wiadomości
        if img:
            await target_channel.send(response_text, file=discord.File(os.path.join(folder, img)))
        else:
            await target_channel.send(response_text)

        await message.add_reaction("❤️")
        await bot.process_commands(message)
        return

    # ─── Reakcja "gorąco 🔥" ─────────────────────────
    if content in ["gorąco?", "goraco?", "🔥"]:
        target_channel = bot.get_channel(HEART_CHANNEL_ID) or message.channel
        folder = "hot"

        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if files:
                img_path = os.path.join(folder, random.choice(files))
                await target_channel.send("Too hot 🔥", file=discord.File(img_path))
                await message.add_reaction("🔥")
                await bot.process_commands(message)
                return

        await target_channel.send("Too hot 🔥 (ale brak obrazków w folderze!)")
        await message.add_reaction("🔥")
        await bot.process_commands(message)
        return

    # ─── Reakcja "uyu" ───────────────────────────────
    if content.replace("?", "") == "sztefyn, co będziesz robił w weekend":
        folder = "photo"
        img = None

        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if files:
                img = random.choice(files)

        if img:
            await message.channel.send(
                "A co ja mogę robić w weekend? Będę... oglądał Wasze dramy <3 ",
                file=discord.File(os.path.join(folder, img))
            )
        else:
            await message.channel.send(
                "A co ja mogę robić w weekend? Będę... oglądał Wasze dramy <3  (ale brak obrazków w folderze!)"
            )

        await bot.process_commands(message)
        return

    # ─── Domyślnie przepuszczaj wszystkie inne wiadomości ─────
    await bot.process_commands(message)


# ─── Harmonogram ──────────────────────────────────────────────────────────────
async def send_memes():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Nie znaleziono kanału do wysyłki memów")
        return

    memes = await get_random_memes(3)
    if memes:
        for m in memes:
            comment = get_random_comment()
            if comment:
                await channel.send(f"{comment}\n{m}")
            else:
                await channel.send(m)
    else:
        await channel.send("⚠️ Nie udało się znaleźć memów!")
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

async def schedule_ankiety():
    tz = pytz.timezone("Europe/Warsaw")
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now(tz)
        targets = [(15, 0)]  # np. codziennie 10:00
        next_time = None

        for hour, minute in targets:
            t = tz.localize(datetime(now.year, now.month, now.day, hour, minute))
            if t > now:
                next_time = t
                break

        if not next_time:
            next_time = tz.localize(datetime(now.year, now.month, now.day, targets[0][0], targets[0][1])) + timedelta(days=1)

        wait_seconds = max(1, int((next_time - now).total_seconds()))
        print(f"⏳ Czekam {wait_seconds/3600:.2f}h do ankiety")
        await asyncio.sleep(wait_seconds)
        await send_ankieta()


# ─── Start ─────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user} (ID: {bot.user.id})")

async def main():
    keep_alive()
    async with bot:
        asyncio.create_task(schedule_memes())
        asyncio.create_task(schedule_ankiety())
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())

