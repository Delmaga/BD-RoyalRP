# main.py
import discord
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv
from utils.db import init_db

# Import de la classe
from cogs.ticket import CloseTicketButton

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN manquant")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ⚠️ NE PAS faire bot.add_view ici

@bot.event
async def on_ready():
    # ✅ Créer la session HTTP
    bot.session = aiohttp.ClientSession()

    # ✅ Enregistrer la vue persistante DANS on_ready (event loop active)
    bot.add_view(CloseTicketButton())  # ← ICI, avec ()

    # Initialiser la DB
    await init_db()

    # Charger les cogs
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
            except Exception as e:
                print(f"❌ Erreur chargement {filename}: {e}")

    # Synchroniser les commandes
    await bot.tree.sync()
    print(f"✅ Royal Bot connecté : {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)