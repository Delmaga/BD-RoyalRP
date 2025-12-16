# main.py
import discord
from discord.ext import commands
import os
import traceback
import aiohttp
from dotenv import load_dotenv
from utils.db import init_db

# Charger les variables d'environnement
load_dotenv()

# Vérifier le token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ La variable DISCORD_TOKEN est manquante dans .env")

# Intents nécessaires
intents = discord.Intents.default()
intents.members = True          # Pour /modo, /avis, welcome, etc.
intents.message_content = True  # Pour /say (optionnel mais utile)

# Créer le bot
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# Créer une session HTTP globale (pour télécharger les avatars dans /welcome)
bot.session = aiohttp.ClientSession()

@bot.event
async def on_ready():
    print("🔄 Initialisation de la base de données...")
    try:
        await init_db()
        print("✅ Base de données prête.")
    except Exception as e:
        print(f"❌ Erreur DB : {e}")
        return

    print("📥 Chargement des cogs...")
    cogs_loaded = 0
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                cogs_loaded += 1
                print(f"   ✅ {cog_name}")
            except Exception as e:
                print(f"   ❌ {cog_name} → {e}")

    print(f"📊 {cogs_loaded} cog(s) chargé(s).")

    print("📡 Synchronisation des commandes slash...")
    try:
        await bot.tree.sync()
        print("✅ Commandes synchronisées.")
    except Exception as e:
        print(f"❌ Erreur de synchronisation : {e}")

    print(f"\n🎉 Royal Bot est connecté en tant que {bot.user} !")
    print("✅ Prêt à modérer, accueillir et impressionner.\n")

@bot.event
async def on_disconnect():
    """Fermer proprement la session HTTP."""
    if not bot.session.closed:
        await bot.session.close()

# Démarrer le bot
if __name__ == "__main__":
    bot.run(TOKEN)