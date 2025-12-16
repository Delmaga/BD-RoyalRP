import aiosqlite
import os

# Chemin de la base de données (fonctionne sur Railway et en local)
DB_PATH = os.getenv("DATABASE_URL", "royal_bot.db")

async def init_db():
    """Crée toutes les tables nécessaires au premier démarrage."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Table : Modération (ban, mute, warn)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS moderation (
                id INTEGER PRIMARY KEY,
                user_id TEXT,
                mod_id TEXT,
                action TEXT,
                reason TEXT,
                duration TEXT,
                timestamp INTEGER,
                active INTEGER DEFAULT 1
            )
        """)

        # Table : Avis sur le staff
        await db.execute("""
            CREATE TABLE IF NOT EXISTS avis (
                id INTEGER PRIMARY KEY,
                user_id TEXT,
                staff_id TEXT,
                content TEXT,
                stars REAL,
                guild_id TEXT,
                timestamp INTEGER
            )
        """)

        # Table : Configuration du système d'avis (rôle staff par serveur)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS avis_config (
                guild_id TEXT PRIMARY KEY,
                staff_role_id TEXT
            )
        """)

        # (Optionnel) Tu peux ajouter ici d'autres tables plus tard :
        # - tickets
        # - welcome config
        # - etc.

        await db.commit()