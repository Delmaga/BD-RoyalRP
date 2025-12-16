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

# ⚠️ NE PAS créer la session ici
# bot.session = aiohttp.ClientSession()  ← ❌ SUPPRIME CETTE LIGNE

@bot.event
async def on_ready():
    # ✅ Créer la session ICI, dans un contexte async
    if not hasattr(bot, 'session') or bot.session.closed:
        bot.session = aiohttp.ClientSession()

    print("🔄 Initialisation de la base de données...")
    await init_db()
    print("✅ Base de données prête.")

    print("📥 Chargement des cogs...")
    cogs_loaded = 0
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                cogs_loaded += 1
                print(f"   ✅ cogs.{filename[:-3]}")
            except Exception as e:
                print(f"   ❌ cogs.{filename[:-3]} → {e}")

    print(f"📊 {cogs_loaded} cog(s) chargé(s).")
    await bot.tree.sync()
    print(f"\n🎉 Royal Bot connecté : {bot.user}")

@bot.event
async def on_disconnect():
    if hasattr(bot, 'session') and not bot.session.closed:
        await bot.session.close()

if __name__ == "__main__":
    bot.run(TOKEN)