# main.py
import discord
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv
from utils.db import init_db

# Import pour la vue persistante
from cogs.ticket import CloseTicketButton

# Charger les variables d'environnement
load_dotenv()

# Vérifier le token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ La variable DISCORD_TOKEN est manquante dans .env")

# Intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Créer le bot
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# Créer la session HTTP (sera initialisée dans on_ready)
bot.session = None

# Enregistrer la vue persistante (seulement le bouton Close)
bot.add_view(CloseTicketButton())

@bot.event
async def on_ready():
    # Initialiser la session HTTP
    if bot.session is None or bot.session.closed:
        bot.session = aiohttp.ClientSession()

    # Initialiser la base de données
    print("🔄 Initialisation de la base de données...")
    await init_db()
    print("✅ Base de données prête.")

    # Charger les cogs
    print("📥 Chargement des cogs...")
    cogs_loaded = 0
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                cogs_loaded += 1
                print(f"   ✅ {filename}")
            except Exception as e:
                print(f"   ❌ {filename} → {e}")

    # Synchroniser les commandes slash
    print("📡 Synchronisation des commandes...")
    await bot.tree.sync()
    print(f"\n🎉 Royal Bot connecté en tant que {bot.user}")
    print("✅ Prêt à modérer, accueillir et gérer les tickets.\n")

@bot.event
async def on_disconnect():
    if bot.session and not bot.session.closed:
        await bot.session.close()

# Démarrer le bot
if __name__ == "__main__":
    bot.run(TOKEN)