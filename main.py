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
from keep_alive import keep_alive
import json

# ─── JSONBin Konfiguracja ─────────────────────────────
JSONBIN_API = "https://api.jsonbin.io/v3/b"
JSONBIN_KEY = os.environ.get("JSONBIN_KEY")
BIN_ID = os.environ.get("JSONBIN_BIN_ID")

HEADERS = {
    "X-Master-Key": JSONBIN_KEY,
    "Content-Type": "application/json"
}

async def create_bin_if_needed():
    global BIN_ID
    if not JSONBIN_KEY:
        print("⚠️ Brak JSONBIN_KEY — pamięć nie będzie działać.")
        return None
    if BIN_ID:
        return BIN_ID
    async with aiohttp.ClientSession() as session:
        async with session.post(
            JSONBIN_API,
            headers=HEADERS,
            json={
                "seen_images_love": [],
                "seen_images_hot": [],
                "recent_love_responses": [],
                "recent_hot_responses": []
            }
        ) as r:
            data = await r.json()
            bin_id = data["metadata"]["id"]
            print(f"✅ Utworzono nowy BIN w JSONBin.io: {bin_id}")
            BIN_ID = bin_id
            return bin_id

async def load_memory_jsonbin():
    global BIN_ID
    if not BIN_ID:
        BIN_ID = await create_bin_if_needed()
    if not BIN_ID:
        return {
            "seen_images_love": [],
            "seen_images_hot": [],
            "recent_love_responses": [],
            "recent_hot_responses": []
        }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{JSONBIN_API}/{BIN_ID}/latest", headers=HEADERS) as r:
            if r.status == 200:
                data = await r.json()
                record = data.get("record", {})
                for key in ["seen_images_love", "seen_images_hot", "recent_love_responses", "recent_hot_responses"]:
                    record.setdefault(key, [])
                return record
            else:
                print(f"⚠️ Błąd przy pobieraniu pamięci ({r.status})")
                return {
                    "seen_images_love": [],
                    "seen_images_hot": [],
                    "recent_love_responses": [],
                    "recent_hot_responses": []
                }

async def save_memory_jsonbin(memory_data):
    global BIN_ID
    if not BIN_ID:
        BIN_ID = await create_bin_if_needed()
    if not BIN_ID:
        return
    async with aiohttp.ClientSession() as session:
        async with session.put(f"{JSONBIN_API}/{BIN_ID}", headers=HEADERS, json=memory_data) as r:
            if r.status == 200:
                print("💾 Pamięć zapisana w JSONBin.io")
            else:
                print(f"❌ Błąd przy zapisie do JSONBin: {r.status}")

# ─── Bot ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)
# ─── Komenda do wyświetlania obrazów z pamięci ─────────────────────────────
from discord.ui import View, Button

class MemoryPages(View):
    def __init__(self, ctx, images, title, per_page=20):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.images = images
        self.title = title
        self.per_page = per_page
        self.current = 0
        self.message = None

    async def send(self):
        embed = self.get_embed()
        self.message = await self.ctx.send(embed=embed, view=self)

    def get_embed(self):
        start = self.current * self.per_page
        end = start + self.per_page
        page_images = self.images[start:end]
        desc = "\n".join(page_images) if page_images else "Brak obrazów na tej stronie."
        embed = discord.Embed(
            title=f"📂 {self.title} — strona {self.current+1}/{max(1, (len(self.images)-1)//self.per_page +1)}",
            description=desc,
            color=0x7289da
        )
        return embed

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.gray)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        if self.current > 0:
            self.current -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        max_page = (len(self.images)-1)//self.per_page
        if self.current < max_page:
            self.current += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()


@bot.command(name="pamiec_obrazy")
async def show_images_memory(ctx):
    global memory

    love_images = memory.get("seen_images_love", [])
    hot_images = memory.get("seen_images_hot", [])

    if not love_images and not hot_images:
        await ctx.send("🗂️ Bot jeszcze nie wykorzystał żadnych obrazów.")
        return

    # Tworzymy osobną paginację dla ❤️ i 🔥
    if love_images:
        view_love = MemoryPages(ctx, love_images, "Obrazy ❤️ (love)")
        await view_love.send()
    if hot_images:
        view_hot = MemoryPages(ctx, hot_images, "Obrazy 🔥 (hot)")
        await view_hot.send()

# ─── Ładowanie tekstów ─────────────────────────────
def load_lines(file_path: str) -> list[str]:
    if not os.path.exists(file_path):
        print(f"⚠️ Plik {file_path} nie istnieje! Używam pustej listy.")
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

pickup_lines_love = load_lines("Podryw.txt")
pickup_lines_hot = load_lines("kuszace.txt")

meme_comments = [
    "XD","🔥🔥🔥","idealny na dziś","no i sztos","😂😂😂","aż się popłakałem",
    "ten mem to złoto","classic","to chyba o mnie","💀💀💀"
]
def get_random_comment():
    return random.choice(meme_comments) if random.random() < 0.4 else ""

# ─── Funkcje pobierania memów ───────────────────────
headers = {"User-Agent": "Mozilla/5.0"}

async def fetch(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                return None
            return await r.text()
    except Exception:
        return None

# Pełne scrapery memów
async def get_meme_from_jeja():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://jeja.pl/")
        if not html: return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "jeja.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_besty():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://besty.pl/")
        if not html: return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "besty.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_memypl():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://memy.pl/")
        if not html: return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "memy.pl" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_9gag():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://9gag.com/")
        if not html: return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "9cache.com" in i]
        return random.choice(imgs) if imgs else None

async def get_meme_from_demotywatory():
    async with aiohttp.ClientSession(headers=headers) as s:
        html = await fetch(s, "https://demotywatory.pl/")
        if not html: return None
        soup = BeautifulSoup(html, "html.parser")
        imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img")]
        imgs = [i for i in imgs if i and "demotywatory.pl" in i]
        return random.choice(imgs) if imgs else None

# Dodaj wszystkie pozostałe scrapery jak wcześniej...
MEME_FUNCS = [
    get_meme_from_jeja,
    get_meme_from_besty,
    get_meme_from_memypl,
    get_meme_from_9gag,
    get_meme_from_demotywatory,
    # get_meme_from_strefabeki, get_meme_from_chamsko, etc...
]

async def get_random_memes(count: int = 2):
    memes: list[str] = []
    funcs = MEME_FUNCS.copy()
    random.shuffle(funcs)
    for func in funcs:
        try:
            meme = await func()
            if meme and meme not in memes:
                memes.append(meme)
            if len(memes) >= count:
                break
        except Exception as e:
            print(f"Błąd podczas pobierania mema z {func.__name__}: {e}")
    return memes

# ─── Funkcje ankiet ─────────────────────────────
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
        if " " not in opt: continue
        emoji, name = opt.split(" ", 1)
        emojis.append(emoji)
        opcje_dict[emoji] = name
        description += f"{emoji} {name}\n"
    embed = discord.Embed(title=f"📊 {pytanie}", description=description, color=0x7289da)
    embed.set_footer(text=f"⏳ Głosowanie trwa 23h | Plik: {file_name}")
    msg = await target_channel.send(embed=embed)
    for emoji in emojis:
        await msg.add_reaction(emoji)
    await asyncio.sleep(82800)  # 23h
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

# ─── Harmonogram ─────────────────────────────
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
        targets = [(11, 0), (21, 37), (14,31)]
        next_time = None
        for hour, minute in targets:
            t = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
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
        targets = [(15, 0)]
        next_time = None
        for hour, minute in targets:
            t = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if t > now:
                next_time = t
                break
        if not next_time:
            next_time = tz.localize(datetime(now.year, now.month, now.day, targets[0][0], targets[0][1])) + timedelta(days=1)
        wait_seconds = max(1, int((next_time - now).total_seconds()))
        print(f"⏳ Czekam {wait_seconds/3600:.2f}h do ankiety")
        await asyncio.sleep(wait_seconds)
        await send_ankieta()

# ─── on_message ─────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    global memory, recent_love_responses, recent_hot_responses, seen_images_love, seen_images_hot

    if message.author == bot.user:
        return

    content = message.content.strip().lower()

    if content == "memy":
        memes = await get_random_memes(2)
        if memes:
            for m in memes:
                await message.channel.send(m)
        else:
            await message.channel.send("⚠️ Nie udało się znaleźć memów!")
        await bot.process_commands(message)
        return

    if content == "ankieta":
        await send_ankieta()
        await message.add_reaction("✅")
        await bot.process_commands(message)
        return

    HEART_EMOJIS = ["<3", "❤", "❤️", "♥️", "♥","🤍","💙","🩵","💚","💛","💜","🖤","🤎","🧡","💗","🩶","🩷","💖"]
    if any(heart in content for heart in HEART_EMOJIS):
        target_channel = bot.get_channel(HEART_CHANNEL_ID) or message.channel
        folder = "images"
        if not pickup_lines_love:
            response_text = "❤️ ...ale brak tekstów w pliku Podryw.txt!"
        else:
            available = [r for r in pickup_lines_love if r not in recent_love_responses] or pickup_lines_love
            response_text = random.choice(available)
            recent_love_responses.append(response_text)
            memory["recent_love_responses"] = recent_love_responses[-100:]
            await save_memory_jsonbin(memory)
        img = None
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            available_images = [f for f in files if f not in seen_images_love] or files
            img = random.choice(available_images)
            seen_images_love.append(img)
            memory["seen_images_love"] = seen_images_love[-500:]
            await save_memory_jsonbin(memory)
        if img:
            await target_channel.send(response_text, file=discord.File(os.path.join(folder, img)))
        else:
            await target_channel.send(response_text)
        await bot.process_commands(message)
        return

        # ─── Reakcja 🔥 ─────────────────────────────
    HOT_EMOJIS = ["🔥", "gorąco", "goraco"]
    if any(hot in content for hot in HOT_EMOJIS):
        target_channel = bot.get_channel(HEART_CHANNEL_ID) or message.channel
        folder = "hot"
        if not pickup_lines_hot:
            response_text = "🔥 ...ale brak tekstów w pliku kuszace.txt!"
        else:
            available = [r for r in pickup_lines_hot if r not in recent_hot_responses] or pickup_lines_hot
            response_text = random.choice(available)
            recent_hot_responses.append(response_text)
            memory["recent_hot_responses"] = recent_hot_responses[-70:]
            await save_memory_jsonbin(memory)
        img = None
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png",".jpg",".jpeg",".gif"))]
            available_images = [f for f in files if f not in seen_images_hot] or files
            img = random.choice(available_images)
            seen_images_hot.append(img)
            memory["seen_images_hot"] = seen_images_hot[-500:]
            await save_memory_jsonbin(memory)
        if img:
            await target_channel.send(response_text, file=discord.File(os.path.join(folder, img)))
        else:
            await target_channel.send(response_text)
        await bot.process_commands(message)
        return

    # ─── Przepuszczanie pozostałych wiadomości do komend
    await bot.process_commands(message)
# ─── Start ─────────────────────────────
async def main():
    global memory, seen_images_love, seen_images_hot, recent_love_responses, recent_hot_responses
    memory = await load_memory_jsonbin()
    memory["seen_images_love"] = list(dict.fromkeys(memory.get("seen_images_love", [])))
    memory["seen_images_hot"] = list(dict.fromkeys(memory.get("seen_images_hot", [])))
    memory["recent_love_responses"] = list(dict.fromkeys(memory.get("recent_love_responses", [])))
    memory["recent_hot_responses"] = list(dict.fromkeys(memory.get("recent_hot_responses", [])))
    seen_images_love = memory.get("seen_images_love", [])
    seen_images_hot = memory.get("seen_images_hot", [])
    recent_love_responses = memory.get("recent_love_responses", [])
    recent_hot_responses = memory.get("recent_hot_responses", [])
    keep_alive()
    async with bot:
        asyncio.create_task(schedule_memes())
        asyncio.create_task(schedule_ankiety())
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
