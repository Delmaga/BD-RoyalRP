import aiosqlite
import os

# Chemin de la base de données (fonctionne en local et sur Railway)
DB_PATH = os.getenv("DATABASE_URL", "royal_bot.db")

async def init_db():
    """Initialise toutes les tables nécessaires au démarrage du bot."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Table : Logs de modération (ban, mute, warn)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS moderation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                mod_id TEXT NOT NULL,
                action TEXT NOT NULL,      -- 'ban', 'mute', 'warn'
                reason TEXT,
                duration TEXT,             -- '30m', '2d', etc.
                timestamp INTEGER NOT NULL,
                active INTEGER DEFAULT 1
            )
        """)

        # Table : Avis sur le staff
        await db.execute("""
            CREATE TABLE IF NOT EXISTS avis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                staff_id TEXT NOT NULL,
                content TEXT NOT NULL,
                stars REAL NOT NULL,
                guild_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)

        # Table : Configuration par serveur (rôle staff + salon avis)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS avis_config (
                guild_id TEXT PRIMARY KEY,
                staff_role_id TEXT,
                avis_channel_id TEXT
            )
        """)

        await db.commit()