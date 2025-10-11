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
import json

MEMORY_FILE = "memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Błąd w memory.json – resetuję dane.")
    return {"seen_memes": [], "seen_images": [], "recent_love_responses": [], "recent_hot_responses": []}

def save_memory():
    data = {
        "seen_memes": seen_memes,
        "seen_images_love": seen_images_love,
        "seen_images_hot": seen_images_hot,
        "recent_love_responses": recent_love_responses,
        "recent_hot_responses": recent_hot_responses,
    }
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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

# ─── Pamięć ────────────────────────────────────────
memory = load_memory()
memory["seen_images_love"] = list(dict.fromkeys(memory.get("seen_images_love", [])))
memory["seen_images_hot"] = list(dict.fromkeys(memory.get("seen_images_hot", [])))
memory["recent_love_responses"] = list(dict.fromkeys(memory.get("recent_love_responses", [])))
memory["recent_hot_responses"] = list(dict.fromkeys(memory.get("recent_hot_responses", [])))

recent_love_responses: list[str] = memory.get("recent_love_responses", [])
recent_hot_responses: list[str] = memory.get("recent_hot_responses", [])

# runtimeowe listy pobrane z pliku pamięci
seen_images_love: list[str] = memory.get("seen_images_love", [])
seen_images_hot: list[str] = memory.get("seen_images_hot", [])

# 🔒 blokada zapisu (żeby uniknąć kolizji)
save_lock = asyncio.Lock()

# ─── Funkcja zapisu pamięci ───────────────────────
async def save_memory():
    async with save_lock:
        try:
            with open("memory.json", "w", encoding="utf-8") as f:
                json.dump({
                    "recent_love_responses": recent_love_responses,
                    "recent_hot_responses": recent_hot_responses,
                    "seen_images_love": seen_images_love,
                    "seen_images_hot": seen_images_hot,
                }, f, ensure_ascii=False, indent=2)
            print("💾 Pamięć zapisana pomyślnie.")
        except Exception as e:
            print("❌ Błąd przy zapisie pamięci:", e)

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

# ─── Ładowanie tekstów podrywu ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def load_pickup_lines(file_path="Podryw.txt") -> list[str]:
    if not os.path.exists(file_path):
        print(f"⚠️ Plik {file_path} nie istnieje! Używam pustej listy.")
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    print(f"✅ Załadowano {len(lines)} tekstów podrywu z {file_path}")
    return lines

pickup_lines = load_pickup_lines()

import asyncio
import os
import random
import glob
import discord

async def send_ankieta(target_channel=None, only_two=False): 
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
    file_name = os.path.basename(file).replace(".txt", "")

    with open(file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) < 3:
        await target_channel.send(f"⚠️ Plik `{file_name}` musi mieć pytanie i co najmniej dwie opcje!")
        return

    pytanie = lines[0]
    opcje = lines[1:]

    if only_two and len(opcje) > 2:
        opcje = random.sample(opcje, 2)

    description = ""
    emojis = []
    opcje_dict = {}
    for opt in opcje:
        if " " not in opt:
            continue
        emoji, name = opt.split(" ", 1)
        emojis.append(emoji)
        opcje_dict[emoji] = name
        description += f"{emoji} {name}\n"

    embed = discord.Embed(title=f"📊 {pytanie}", description=description, color=0x7289da)
    embed.set_footer(text=f"⏳ Głosowanie trwa 23h | Plik: {file_name}")
    msg = await target_channel.send(embed=embed)

    for emoji in emojis:
        await msg.add_reaction(emoji)

    print(f"✅ Ankieta '{file_name}' rozpoczęta! Czekam 24h na głosy...")
    await asyncio.sleep(82800)  # zmień na 86400 w wersji produkcyjnej

    msg = await target_channel.fetch_message(msg.id)

    wyniki = []
    max_votes = -1
    zwyciezca = None

    for reaction in msg.reactions:
        if str(reaction.emoji) in emojis:
            count = reaction.count - 1
            wyniki.append(f"{reaction.emoji} — {count} głosów")
            if count > max_votes:
                max_votes = count
                zwyciezca = str(reaction.emoji)

    if not wyniki:
        await target_channel.send(f"⚠️ Nikt nie zagłosował w ankiecie `{file_name}` 😅")
        return

    result_text = "\n".join(wyniki)

    result_embed = discord.Embed(
        title=f"📊 Wyniki ankiety: {pytanie}",
        description=result_text,
        color=0x57F287
    )
    result_embed.set_footer(text=f"📄 Źródło: {file_name}.txt")

    if zwyciezca:
        result_embed.add_field(
            name="🏆 Zwycięzca",
            value=f"{zwyciezca} {opcje_dict[zwyciezca]} — **{max_votes} głosów**",
            inline=False
        )

    await target_channel.send(embed=result_embed)
    print(f"🏁 Ankieta '{file_name}' zakończona! Zwycięzca: {opcje_dict.get(zwyciezca, '?')} ({max_votes} głosów)")

# ──────────────────────────────── ankieta DRINK ─────────────────────────────────────────────────────────────────────────────────────
async def send_drink_ankieta():
    """Wysyła ankietę z pliku Ankieta/drink.txt"""
    target_channel = bot.get_channel(ANKIETA_CHANNEL_ID)
    if not target_channel:
        print("❌ Nie znaleziono kanału do ankiet")
        return

    file = os.path.join("Ankieta", "drink.txt")
    if not os.path.exists(file):
        await target_channel.send("⚠️ Brak pliku `drink.txt` w folderze `Ankieta`!")
        return

    with open(file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) < 3:
        await target_channel.send("⚠️ Plik `drink.txt` musi mieć pytanie i co najmniej dwie opcje!")
        return

    pytanie = lines[0]
    opcje = lines[1:]

    description = ""
    emojis = []
    opcje_dict = {}
    for opt in opcje:
        if " " not in opt:
            continue
        emoji, name = opt.split(" ", 1)
        emojis.append(emoji)
        opcje_dict[emoji] = name
        description += f"{emoji} {name}\n"

    embed = discord.Embed(title=f"📊 {pytanie}", description=description, color=0x7289da)
    embed.set_footer(text=f"⏳ Głosowanie trwa 23h | Plik: drink.txt")
    msg = await target_channel.send(embed=embed)

    for emoji in emojis:
        await msg.add_reaction(emoji)

    print(f"✅ Ankieta 'drink.txt' rozpoczęta! Czekam 23h na głosy...")
    await asyncio.sleep(82800)  # 23h

    msg = await target_channel.fetch_message(msg.id)
    wyniki = []
    max_votes = -1
    zwyciezca = None

    for reaction in msg.reactions:
        if str(reaction.emoji) in emojis:
            count = reaction.count - 1  # odlicz głos bota
            wyniki.append(f"{reaction.emoji} — {count} głosów")
            if count > max_votes:
                max_votes = count
                zwyciezca = str(reaction.emoji)

    if not wyniki:
        await target_channel.send("⚠️ Nikt nie zagłosował w ankiecie `drink.txt` 😅")
        return

    result_text = "\n".join(wyniki)
    result_embed = discord.Embed(
        title=f"📊 Wyniki ankiety: {pytanie}",
        description=result_text,
        color=0x57F287
    )
    result_embed.set_footer(text="📄 Źródło: drink.txt")

    if zwyciezca:
        result_embed.add_field(
            name="🏆 Zwycięzca",
            value=f"{zwyciezca} {opcje_dict[zwyciezca]} — **{max_votes} głosów**",
            inline=False
        )

    await target_channel.send(embed=result_embed)
    print(f"🏁 Ankieta 'drink.txt' zakończona! Zwycięzca: {opcje_dict.get(zwyciezca, '?')} ({max_votes} głosów)")


# ─── Bot ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True  # <── WAŻNE: pozwala wykrywać reakcje emoji
bot = commands.Bot(command_prefix="!", intents=intents)


# ─── Pobieranie stron ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def fetch(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
            if r.status != 200:
                return None
            return await r.text()
    except Exception:
        return None

# ─── Scrapery ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
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
        # usuń duplikaty i ogranicz długość
            seen_memes[:] = list(dict.fromkeys(seen_memes))[-100:]
            save_memory()

    return memes

# ─── Losowe komentarze ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
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
    return random.choice(meme_comments) if random.random() < 0.4 else ""

def load_lines(file_path: str) -> list[str]:
    if not os.path.exists(file_path):
        print(f"⚠️ Plik {file_path} nie istnieje! Używam pustej listy.")
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

# Oddzielne listy tekstów
pickup_lines_love = load_lines("Podryw.txt")
pickup_lines_hot = load_lines("kuszace.txt")

# Ostatnie odpowiedzi (dla unikania powtórzeń)
recent_love_responses: list[str] = []
recent_hot_responses: list[str] = []

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

    # ─── Komenda "ankieta" ─────────────────────────────
    if content == "ankieta":
        await send_ankieta()
        await message.add_reaction("✅")
        await bot.process_commands(message)
        return

    # ─── Komenda "drink" ─────────────────────────────
    if "inkluzif" in content:
        await send_drink_ankieta()
        await message.add_reaction("🍸")
        await bot.process_commands(message)
        return

    # ─── Reakcja ❤️ ─────────────────────────────
    HEART_EMOJIS = [
        "<3", "❤", "❤️", "♥️", "♥",
        "🤍", "💙", "🩵", "💚", "💛", "💜",
        "🖤", "🤎", "🧡", "💗", "🩶", "🩷", "💖",
    ]

    if any(heart in content for heart in HEART_EMOJIS):
        target_channel = bot.get_channel(HEART_CHANNEL_ID) or message.channel
        folder = "images"

        # losowy tekst z pliku Podryw.txt
        if not pickup_lines_love:
            response_text = "❤️ ...ale brak tekstów w pliku Podryw.txt!"
        else:
            available = [r for r in pickup_lines_love if r not in recent_love_responses] or pickup_lines_love
            response_text = random.choice(available)
            recent_love_responses.append(response_text)
            recent_love_responses[:] = list(dict.fromkeys(recent_love_responses))[-100:]
            save_memory()

        # losowy obrazek
        img = None
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            available_images = [f for f in files if f not in seen_images_love] or files
            img = random.choice(available_images)
            seen_images_love.append(img)
            seen_images_love[:] = list(dict.fromkeys(seen_images_love))[-500:]
            save_memory()

        if img:
            await target_channel.send(response_text, file=discord.File(os.path.join(folder, img)))
        else:
            await target_channel.send(response_text)

        await bot.process_commands(message)
        return

    # ─── Reakcja 🔥 ─────────────────────────────
    if "🔥" in content or "gorąco" in content or "goraco" in content:
        target_channel = bot.get_channel(HEART_CHANNEL_ID) or message.channel
        folder = "hot"

        if not pickup_lines_hot:
            response_text = "🔥 ...ale brak tekstów w pliku kuszace.txt!"
        else:
            available = [r for r in pickup_lines_hot if r not in recent_hot_responses] or pickup_lines_hot
            response_text = random.choice(available)
            recent_hot_responses.append(response_text)
            recent_hot_responses[:] = list(dict.fromkeys(recent_hot_responses))[-70:]
            save_memory()

        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if files:
                img_path = os.path.join(folder, random.choice(files))
                seen_images_hot.append(os.path.basename(img_path))
                seen_images_hot[:] = list(dict.fromkeys(seen_images_hot))[-500:]
                save_memory()
                await target_channel.send(response_text, file=discord.File(img_path))
                await bot.process_commands(message)
                return

                await target_channel.send(f"{response_text} (ale brak obrazków w folderze!)")
                await bot.process_commands(message)
                return

   # ─── Reakcje pamięci ─────────────────────────────
if "pokażpamięć" in content or "pokaż pamięć" in content or "pokazpamiec" in content or "pokaz pamiec" in content:
    memy = len(memory.get("seen_memes", []))
    obrazy_love = len(memory.get("seen_images_love", []))
    obrazy_hot = len(memory.get("seen_images_hot", []))
    teksty_podryw = len(memory.get("recent_love_responses", []))
    teksty_hot = len(memory.get("recent_hot_responses", []))

    msg = (
        f"📊 **Stan pamięci bota:**\n"
        f"🧠 Memy: {memy}\n"
        f"❤️ Obrazy (love): {obrazy_love}\n"
        f"🔥 Obrazy (hot): {obrazy_hot}\n"
        f"💬 Teksty podrywu: {teksty_podryw}\n"
        f"🔥 Teksty hot: {teksty_hot}"
            )
        await message.channel.send(msg)
        return


if "resetpamięć" in content or "reset pamięć" in content or "resetpamiec" in content or "reset pamiec" in content:
    confirm_msg = await message.channel.send(
        "⚠️ **Uwaga!** Ta operacja usunie wszystkie zapamiętane memy, obrazy i teksty.\n"
        "Kliknij ✅ aby potwierdzić lub ❌ aby anulować."
    )
    await confirm_msg.add_reaction("✅")
    await confirm_msg.add_reaction("❌")

    def check(reaction, user):
        return (
            user == message.author
            and str(reaction.emoji) in ["✅", "❌"]
            and reaction.message.id == confirm_msg.id
        )

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=30.0, check=check)
        if str(reaction.emoji) == "✅":
            memory["seen_memes"].clear()
            memory["seen_images_love"].clear()
            memory["seen_images_hot"].clear()
            memory["recent_love_responses"].clear()
            memory["recent_hot_responses"].clear()

            # wyczyść też bieżące listy w pamięci runtime
            seen_memes.clear()
            seen_images_love.clear()
            seen_images_hot.clear()
            recent_love_responses.clear()
            recent_hot_responses.clear()

            await save_memory()
            await message.channel.send("🧹 Pamięć została **zresetowana**.")
        else:
            await message.channel.send("❌ Reset pamięci **anulowany**.")
    except asyncio.TimeoutError:
        await message.channel.send("⌛ Czas na potwierdzenie minął. Reset anulowany.")
    return
    
    
    # ─── Inne teksty ─────────────────────────────
    if content.replace("?", "") == "sztefyn, co będziesz robił w weekend":
        folder = "photo"
        if os.path.exists(folder) and os.listdir(folder):
            img = random.choice(os.listdir(folder))
            await message.channel.send(
                "A co ja mogę robić w weekend? Będę... oglądał Wasze dramy <3 ",
                file=discord.File(os.path.join(folder, img))
            )
        else:
            await message.channel.send(
                "A co ja mogę robić w weekend? Będę... oglądał Wasze dramy <3 (ale brak obrazków w folderze!)"
            )
        await bot.process_commands(message)
        return
        

    # ─── NAJWAŻNIEJSZE ─────────────────────────────
    # Zawsze przepuszczaj pozostałe wiadomości do komend
    await bot.process_commands(message)
    save_memory()
    

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

