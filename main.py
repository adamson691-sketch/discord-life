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
import os
import sys

# pobieramy token i ID kanału bez użycia .env
TOKEN = "".join(os.environ.get("DISCORD_TOKEN", "").split())  # usuwa spacje i nowe linie
CHANNEL_ID_RAW = os.environ.get("CHANNEL_ID", "").strip()

# debug – sprawdzenie tokena
print(f"DEBUG TOKEN: '{TOKEN}' | length: {len(TOKEN)}")
print(f"DEBUG CHANNEL_ID: '{CHANNEL_ID_RAW}'")

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


# ─── Bot ───────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
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

# ─── Scrapery ─────────────────────────────────────────────────────────────────
async def get_meme_from_jeja():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://jeja.pl/")
        if not html:
            return None
        imgs = re.findall(r'src="(https://i\.jeja\.pl/[^\"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_besty():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://besty.pl/")
        if not html:
            return None
        imgs = re.findall(r'src="(https://img\.besty\.pl/[^\"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_wykop():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://wykop.pl/hity")
        if not html:
            return None
        imgs = re.findall(r'src="(https://[^\"]+\.jpg)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_memypl():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://memy.pl/")
        if not html:
            return None
        imgs = re.findall(r'src="(https://memy\.pl/memes/[^\"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_9gag():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://9gag.com/")
        if not html:
            return None
        imgs = re.findall(r'src="(https://img-9gag-fun\.9cache\.com/photo/[^\"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_demotywatory():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://demotywatory.pl/")
        if not html:
            return None
        imgs = re.findall(r'src="(https://img\.demotywatory\.pl/uploads/[^\"]+)"', html)
        return random.choice(imgs) if imgs else None

async def get_meme_from_kwejk():
    async with aiohttp.ClientSession() as s:
        html = await fetch(s, "https://kwejk.pl/")
        if not html:
            return None
        imgs = re.findall(r'src="(https://i1\.kwejk\.pl/k/[^\"]+)"', html)
        return random.choice(imgs) if imgs else None

# ─── Losowanie memów (z pamięcią 20 ostatnich) ────────────────────────────────
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
        print(f"❌ Nie znaleziono kanału o ID {CHANNEL_ID}.")
        return

    memes = await get_random_memes(2)
    if memes:
        for m in memes:
            await channel.send(m)
    else:
        await channel.send("⚠️ Nie udało się znaleźć memów!")


# ─── Obsługa wiadomości ───────────────────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if message.content.strip().lower() == "memy":
        memes = await get_random_memes(6)
        if memes:
            for m in memes:
                await message.channel.send(m)
        else:
            await message.channel.send("⚠️ Nie udało się znaleźć memów!")
        await bot.process_commands(message)
        return

    # ❤️ reakcja
    if message.content.strip() in ["❤️", "<3"]:
        responses = [
            "Wiem, że jeszcze nie Walentynki, ale już teraz skradłaś/eś moje serce 💕",
            "Sztefyn mówi I LOVE, ty mówisz YOU",
            "Dostałem twoje ❤️ i już szykuję kozi garnitur na ślub",
            "Mam cię w serduszku jak memy w galerii",
            "Wysłałaś/eś ❤️, więc chyba muszę napisać do twojej mamy, że jesteś zajęta/y",
            "Hmm... fajna dupa jesteś.",
            "Jedno serduszko od Ciebie i już myślę o wspólnym kredycie hipotecznym.",
            "Serduszko od Ciebie to jak subskrypcja premium na moją uwagę – dożywotnia!",
            "Uwaga, uwaga! Serduszko zarejestrowane. Rozpoczynam procedurę zakochiwania.",
            "Jedno serduszko od Ciebie i już sprawdzam, czy w Biedronce są promocje na pierścionki zaręczynowe.",
            "Otrzymałem serduszko… uruchamiam tryb romantyczny ogórek kiszony.",
            "Jeszcze chwila i z tego serduszka wykluje się mały Sztefynek",
            "Kupiłem już matching dresy w Pepco, bo wiem, że to prawdziwa miłość.",
            "Serce przyjęte. Od jutra mówię do teściowej: mamo.",
            "Wysłałaś mi ❤️, a ja już beczę pod Twoim oknem.",
            "Dostałem serce… i zaraz przyniosę Ci bukiet świeżego siana.",
            "Wysłałaś serduszko… a ja już zapisuję nas na Kozi Program 500+.",
            "❤️ to dla mnie znak – od dziś beczę tylko dla Ciebie.",
            "Dostałem ❤️ i od razu widzę nas na Windows XP, razem na tapecie z zieloną łąką.",
            "Twoje ❤️ sprawiło, że zapuściłem kozią bródkę specjalnie dla Ciebie.",
            "Twoje serce to dla mnie VIP wejściówka na pastwisko Twojego serca.",
            "Wysłałaś/eś ❤️… a ja już wyrywam kwiatki z sąsiedniego ogródka dla Ciebie.",
            "Serduszko od Ciebie = darmowa dostawa buziaków na całe życie.",
            "Dostałem serce i już czyszczę kopytka na naszą randkę.",
            "❤️ od Ciebie to jak wygrana na loterii… ale zamiast pieniędzy mam Twoje serce!",
            "Dostałem ❤️… i już szukam w Google ‘jak zaimponować człowiekowi, będąc kozą’.",
            "❤️ od Ciebie = kozi internet 5G – łączność z sercem bez lagów.",
            "Jedno ❤️ od Ciebie i już dodaję Cię do koziej listy kontaktów pod pseudonim ‘Mój człowiek’.",
            "Wysłałaś/eś ❤️… a ja już zamawiam kubki ‘On koza, ona człowiek’.",
        ]
        folder = "images"

        available = [r for r in responses if r not in recent_responses]
        if not available:
            available = responses
        response_text = random.choice(available)
        recent_responses.append(response_text)
        if len(recent_responses) > 20:
            recent_responses.pop(0)

        img = None
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if files:
                available_images = [f for f in files if f not in seen_images] or files
                img = random.choice(available_images)
                seen_images.append(img)
                if len(seen_images) > 60:
                    seen_images.pop(0)

        # wysyłamy dokładnie jedną wiadomość z tekstem i ewentualnym obrazkiem
        if img:
            await message.channel.send(response_text, file=discord.File(os.path.join(folder, img)))
        else:
            await message.channel.send(response_text)

        await bot.process_commands(message)
        return

    # ─── Reakcja "uyu" ───────────────────────────────#
    if message.content.strip().lower() == "uyu":
        folder = "photo"
        img = None

        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if files:
                img = random.choice(files)

        if img:
            await message.channel.send(
                "Wybaczcie byłem na łące all inclusive i musiałem wypocząć, ale już jestem ❤️. "
                "Podczas wypoczynku spotkałem 'pewną ślicznotkę' to podeślę wam zdjęcie ❤️",
                file=discord.File(os.path.join(folder, img))
            )
        else:
            await message.channel.send(
                "Wybaczcie byłem na łące all inclusive i musiałem wypocząć, ale już jestem ❤️. "
                "Podczas wypoczynku spotkałem 'pewną ślicznotkę' to podeślę wam zdjęcie ❤️ (ale brak obrazków w folderze!)"
            )

        await bot.process_commands(message)
        return

    # ─── Reakcja 🔥 (gorąco? lub emoji) ───────────────
    if message.content.strip().lower() in ["gorąco?", "goraco?"] or "🔥" in message.content:
        folder = "hot"
        img = None
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if files:
                img = random.choice(files)

        if img:
            await message.channel.send("Too hot 🔥", file=discord.File(os.path.join(folder, img)))
        else:
            await message.channel.send("Too hot 🔥 (ale brak obrazków w folderze!)")

        await bot.process_commands(message)
        return

    # ─── DOMYŚLNIE przepuszczaj wszystkie inne wiadomości do komend
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


# ─── Start ─────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user} (ID: {bot.user.id})")

async def main():
    keep_alive()
    async with bot:
        asyncio.create_task(schedule_memes())
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())

