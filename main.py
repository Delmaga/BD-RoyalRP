# main.py
import os
import json
import discord
from discord.ext import commands

# Charger le token depuis config.json
try:
    with open("config.json", "r") as f:
        config = json.load(f)
    TOKEN = config.get("token")
except FileNotFoundError:
    print("❌ Fichier config.json manquant.")
    exit(1)

if not TOKEN:
    print("❌ Token non défini dans config.json")
    exit(1)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents, case_insensitive=True)
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f"✅ Royal Bot connecté en tant que {bot.user}")

async def main():
    await bot.load_extension("cogs.moderation")
    await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())