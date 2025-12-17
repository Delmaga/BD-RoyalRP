import discord
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv
from utils.db import init_db

# ✅ Import de la classe (sans instancier)
from cogs.ticket import CloseTicketButton

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN manquant")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ✅ Enregistrer la CLASSE (pas une instance)
bot.add_view(CloseTicketButton)  # ← PAS de ()

@bot.event
async def on_ready():
    bot.session = aiohttp.ClientSession()
    await init_db()
    # ... chargement des cogs ...
    print(f"✅ Royal Bot connecté : {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)