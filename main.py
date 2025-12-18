# main.py
import discord
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv
from utils.db import init_db
from cogs.ticket import CloseTicketButton

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN manquant")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
bot.session = None
bot.add_view(CloseTicketButton())

@bot.event
async def on_ready():
    bot.session = aiohttp.ClientSession()
    await init_db()
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
            except Exception as e:
                print(f"❌ Erreur chargement {filename}: {e}")
    await bot.tree.sync()
    print(f"✅ Royal Bot connecté : {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)