# main.py
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise RuntimeError("❌ Le token DISCORD_TOKEN n'est pas défini dans les variables d'environnement.")

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