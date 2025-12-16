# main.py
import discord
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv
from utils.db import init_db

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN manquant")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    # ✅ Créer la session HTTP ici
    if not hasattr(bot, 'session'):
        bot.session = aiohttp.ClientSession()

    print("🔄 Initialisation DB...")
    await init_db()
    print("✅ DB prête.")

    print("📥 Chargement des cogs...")
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"   ✅ {filename}")
            except Exception as e:
                print(f"   ❌ {filename} → {e}")

    await bot.tree.sync()
    print(f"\n🎉 Royal Bot connecté : {bot.user}")

@bot.event
async def on_disconnect():
    if hasattr(bot, 'session') and not bot.session.closed:
        await bot.session.close()

if __name__ == "__main__":
    bot.run(TOKEN)