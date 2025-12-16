# main.py
import os
import discord
from discord.ext import commands

# Essaye d'abord de charger depuis .env (uniquement en local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # En production, dotenv n'est pas installé → pas grave
    pass

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise RuntimeError("❌ La variable d'environnement DISCORD_TOKEN est manquante.")

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