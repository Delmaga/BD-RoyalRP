# cogs/securite.py (extrait anti-lien)

import discord
from discord.ext import commands
import aiosqlite
import re

def contains_forbidden_content(message: discord.Message) -> bool:
    """Détecte tout contenu non autorisé (liens, médias, etc.)."""
    # 1. Texte avec liens
    if re.search(r'https?://|www\.|discord\.(gg|com/invite)', message.content, re.IGNORECASE):
        return True
    # 2. Embeds (liens cachés)
    if message.embeds:
        return True
    # 3. Fichiers non autorisés
    for att in message.attachments:
        if not att.filename.lower().endswith(('.txt', '.png', '.jpg', '.jpeg')):
            return True
    # 4. GIF/vidéos dans le texte
    if re.search(r'\.(gif|mp4|webm|mov|avi|mkv|exe|bat|dll)', message.content, re.IGNORECASE):
        return True
    return False

class SecurityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_config(self, guild_id: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute("""
                SELECT anti_links_global, anti_links_salon, logs_links
                FROM security_config WHERE guild_id = ?
            """, (guild_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "anti_links_global": bool(row[0]),
                    "anti_links_salon": row[1],
                    "logs_links": row[2]
                }
            return {"anti_links_global": False, "anti_links_salon": None, "logs_links": None}

    async def log_link(self, guild, channel_id, author, content, salon):
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                await channel.send(
                    f"{author.mention}\n\n"
                    f"🔗 LIEN BLOQUÉ\n"
                    f"Contenu non autorisé :\n\n"
                    f"`{content or '[Embed/Pièce jointe]'}`\n\n"
                    f"📅 {datetime.now().strftime('%d/%m %H:%M:%S')} • {salon.mention}"
                )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        config = await self.get_config(str(message.guild.id))
        should_block = False

        # Global
        if config["anti_links_global"]:
            should_block = True
        # Par salon
        elif config["anti_links_salon"] and str(message.channel.id) == config["anti_links_salon"]:
            should_block = True

        if should_block and contains_forbidden_content(message):
            await message.delete()
            await self.log_link(
                message.guild,
                config["logs_links"],
                message.author,
                message.content,
                message.channel
            )

    # --- COMMANDES ---
    @discord.app_commands.command(name="anti_lien", description="Activer/désactiver l'anti-liens sur tout le serveur")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def anti_lien(self, interaction: discord.Interaction, activer: bool):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "INSERT INTO security_config (guild_id, anti_links_global) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET anti_links_global = excluded.anti_links_global",
                (str(interaction.guild.id), int(activer))
            )
            await db.commit()
        await interaction.response.send_message(f"`✅ Anti-liens global = {activer}`", ephemeral=False)

    @discord.app_commands.command(name="anti_lien_salon", description="Activer/désactiver l'anti-liens dans un salon spécifique")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def anti_lien_salon(self, interaction: discord.Interaction, salon: discord.TextChannel, activer: bool):
        async with aiosqlite.connect("royal_bot.db") as db:
            if activer:
                value = str(salon.id)
            else:
                value = None
            await db.execute(
                "INSERT INTO security_config (guild_id, anti_links_salon) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET anti_links_salon = excluded.anti_links_salon",
                (str(interaction.guild.id), value)
            )
            await db.commit()
        status = "activé" if activer else "désactivé"
        await interaction.response.send_message(f"`✅ Anti-liens {status} dans {salon.mention}`", ephemeral=False)

    @discord.app_commands.command(name="logs_liens", description="Définir le salon des logs de liens")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_liens(self, interaction: discord.Interaction, salon: discord.TextChannel):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "INSERT INTO security_config (guild_id, logs_links) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET logs_links = excluded.logs_links",
                (str(interaction.guild.id), str(salon.id))
            )
            await db.commit()
        await interaction.response.send_message(f"`✅ Logs liens → {salon.mention}`", ephemeral=False)