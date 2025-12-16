# utils/db.py
import aiosqlite
import os

# Chemin de la base de données
DB_PATH = os.getenv("DATABASE_URL", "royal_bot.db")

async def init_db():
    """Initialise toutes les tables nécessaires au démarrage du bot."""
    async with aiosqlite.connect(DB_PATH) as db:

        # ========== MODÉRATION ==========
        await db.execute("""
            CREATE TABLE IF NOT EXISTS moderation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                mod_id TEXT NOT NULL,
                action TEXT NOT NULL,      -- 'ban', 'mute', 'warn'
                reason TEXT NOT NULL,
                duration TEXT,             -- NULL pour 'warn'
                timestamp INTEGER NOT NULL,
                active INTEGER DEFAULT 1
            )
        """)

        # ========== AVIS SUR LE STAFF ==========
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

        # ========== CONFIGURATION AVIS ==========
        await db.execute("""
            CREATE TABLE IF NOT EXISTS avis_config (
                guild_id TEXT PRIMARY KEY,
                staff_role_id TEXT,
                avis_channel_id TEXT
            )
        """)

        # ========== CONFIGURATION WELCOME ==========
        await db.execute("""
            CREATE TABLE IF NOT EXISTS welcome_config (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT,
                role_id TEXT
            )
        """)

        # ========== TICKETS ==========
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_categories (
                guild_id TEXT NOT NULL,
                name TEXT NOT NULL,
                PRIMARY KEY (guild_id, name)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_config (
                guild_id TEXT PRIMARY KEY,
                ping_role_id TEXT
            )
        """)

        # Appliquer les changements
        await db.commit()