import os
import discord
from discord.ext import commands
import traceback
from dotenv import load_dotenv
from utils.db import init_db

# Charger les variables d'environnement
load_dotenv()

# Intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
intents.presences = True  # Pour détecter bots online/offline

# Créer le bot
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print("🔄 Initialisation de la base de données...")
    await init_db()
    print("✅ Base de données prête.")

    print("📥 Chargement des cogs...")
    cogs_loaded = 0
    cogs_failed = []

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                cogs_loaded += 1
                print(f"   ✅ {cog_name}")
            except Exception as e:
                cogs_failed.append(cog_name)
                print(f"   ❌ {cog_name} → {e}")
    
    print(f"📊 {cogs_loaded} cog(s) chargé(s).")
    if cogs_failed:
        print(f"⚠️  {len(cogs_failed)} cog(s) non chargé(s) : {', '.join(cogs_failed)}")

    print("📡 Synchronisation des commandes slash...")
    try:
        await bot.tree.sync()
        print("✅ Commandes slash synchronisées.")
    except Exception as e:
        print(f"❌ Erreur de synchronisation : {e}")

    print(f"\n🎉 Royal Bot est connecté en tant que {bot.user} !")
    print(f"✅ Prêt à modérer, accueillir, et impressionner.\n")

# Démarrer le bot
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("❌ ERREUR : Le token DISCORD_TOKEN n'est pas défini dans les variables d'environnement.")
    
    bot.run(token)