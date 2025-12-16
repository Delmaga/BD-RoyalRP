import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from utils.db import init_db

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await init_db()
    await bot.tree.sync()
    print(f"✅ Royal Bot connecté : {bot.user}")

# Charger les cogs
for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        bot.load_extension(f"cogs.{filename[:-3]}")

bot.run(os.getenv("DISCORD_TOKEN"))