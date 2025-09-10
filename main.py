import discord
from discord.ext import commands
import os

# 🔑 Pobieramy token (upewnij się, że masz zmienną DISCORD_TOKEN ustawioną w Render / .env)
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # potrzebne, żeby bot czytał wiadomości

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user} (ID: {bot.user.id})")

bot.run(TOKEN)
