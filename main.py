# main.py
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

# Récupérer le token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ Erreur : DISCORD_TOKEN non défini dans .env")
    exit(1)

# Intentions
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents, case_insensitive=True)
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f"✅ Royal Bot connecté en tant que {bot.user}")
    await bot.change_presence(activity=discord.Game(name="Protéger le serveur"))

# Charger le cog
async def main():
    async with bot:
        await bot.load_extension("cogs.moderation")
        await bot.start(TOKEN)

# Installer python-dotenv si ce n'est pas fait :
# pip install python-dotenv

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())