import os
import discord
import asyncio

TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()

async def main():
    if not TOKEN:
        print("❌ Brak DISCORD_TOKEN w zmiennych środowiskowych.")
        return

    try:
        client = discord.Client()
        await client.login(TOKEN)
        print("✅ Token jest poprawny i zaakceptowany przez Discord!")
        await client.close()
    except discord.LoginFailure:
        print("❌ Token jest nieprawidłowy! (401 Unauthorized)")
    except Exception as e:
        print(f"⚠️ Wystąpił inny błąd: {e}")

asyncio.run(main())
