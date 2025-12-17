# cogs/securite.py
import discord
from discord.ext import commands, tasks
import aiosqlite
import re
from datetime import datetime, timedelta
import asyncio

# Stockage temporaire du spam (effacé après 10 sec)
user_message_history = {}

class SecurityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.clear_spam_history.start()

    def cog_unload(self):
        self.clear_spam_history.cancel()

    @tasks.loop(seconds=10)
    async def clear_spam_history(self):
        """Nettoie l'historique du spam toutes les 10 sec."""
        now = datetime.now()
        to_remove = []
        for user_id, messages in user_message_history.items():
            # Garder seulement les messages des 5 dernières secondes
            user_message_history[user_id] = [
                (ts, msg) for ts, msg in messages if now - ts < timedelta(seconds=5)
            ]
            if not user_message_history[user_id]:
                to_remove.append(user_id)
        for uid in to_remove:
            del user_message_history[uid]

    # ---------- UTILITAIRES ----------
    async def get_security_config(self, guild_id):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT * FROM security_config WHERE guild_id = ?", (str(guild_id),)
            )
            row = await cursor.fetchone()
            if row:
                return dict(zip([
                    "guild_id", "anti_spam", "anti_links", "logs_spam", "logs_links",
                    "logs_messages", "logs_vocal", "logs_moderation", "logs_suspect", "hardened"
                ], row))
            else:
                return None

    async def log_to_channel(self, guild, channel_id, content):
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if channel:
            await channel.send(content)

    # ---------- ÉVÉNEMENTS DE SÉCURITÉ ----------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        config = await self.get_security_config(message.guild.id)
        if not config:
            return

        # --- Anti-spam ---
        if config["anti_spam"]:
            now = datetime.now()
            user_id = message.author.id
            if user_id not in user_message_history:
                user_message_history[user_id] = []
            user_message_history[user_id].append((now, message.content))

            # Si + de 4 messages en 5 sec → spam
            if len(user_message_history[user_id]) >= 4:
                await message.delete()
                await self.log_to_channel(
                    message.guild,
                    config["logs_spam"],
                    f"`🚨 SPAM DÉTECTÉ`\n"
                    f"**Utilisateur :** {message.author.mention} (`{message.author}`)\n"
                    f"**Salon :** {message.channel.mention}\n"
                    f"**Messages :**\n{chr(10).join([m for _, m in user_message_right[:4]])}"
                )
                # Optionnel : mute automatique
                # await self.mute_user_temporarily(message.author, message.guild, duration=600)

        # --- Anti-liens ---
        if config["anti_links"]:
            # Regex pour détecter tout lien (http, discord.gg, etc.)
            if re.search(r'https?://|discord\.(gg|com/invite)|www\.', message.content, re.IGNORECASE):
                await message.delete()
                await self.log_to_channel(
                    message.guild,
                    config["logs_links"],
                    f"`🔗 LIEN BLOQUÉ`\n"
                    f"**Utilisateur :** {message.author.mention}\n"
                    f"**Salon :** {message.channel.mention}\n"
                    f"**Lien :** `{message.content}`"
                )

        # --- Logs messages ---
        if config["logs_messages"]:
            reply_to = ""
            if message.reference:
                try:
                    replied = await message.channel.fetch_message(message.reference.message_id)
                    reply_to = f" → répond à {replied.author.mention}"
                except:
                    pass
            await self.log_to_channel(
                message.guild,
                config["logs_messages"],
                f"`💬 {datetime.now().strftime('%d/%m %H:%M')}`\n"
                f"**{message.author}**{reply_to} dans {message.channel.mention} :\n"
                f"> {message.content}"
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        config = await self.get_security_config(member.guild.id)
        if not config or not config["logs_vocal"]:
            return

        channel = member.guild.get_channel(int(config["logs_vocal"]))
        if not channel:
            return

        now = datetime.now()
        if before.channel != after.channel:
            if after.channel:  # Entrée
                self.voice_join_times[member.id] = now
                await channel.send(
                    f"`🎧 {now.strftime('%d/%m %H:%M')}` — {member.mention} a rejoint **{after.channel.name}**"
                )
            if before.channel:  # Sortie
                join_time = self.voice_join_times.get(member.id)
                duration = "inconnue"
                if join_time:
                    delta = now - join_time
                    minutes, seconds = divmod(int(delta.total_seconds()), 60)
                    duration = f"{minutes}m {seconds}s"
                    del self.voice_join_times[member.id]
                await channel.send(
                    f"`🎧 {now.strftime('%d/%m %H:%M')}` — {member.mention} a quitté **{before.channel.name}** (temps : {duration})"
                )

    # Variables pour le vocal
    voice_join_times = {}

    # ---------- COMMANDES ADMIN ----------
    @discord.app_commands.command(name="securite", description="Configurer le système de sécurité")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def securite(self, interaction: discord.Interaction, action: str, value: str = None, salon: discord.TextChannel = None):
        actions = [
            "spam", "liens", "logs_spam", "logs_liens", "logs_message",
            "logs_vocal", "logs_moderation", "logs_suspect", "harden"
        ]
        if action not in actions:
            await interaction.response.send_message(
                f"`❌ Action invalide. Choisissez parmi : {', '.join(actions)}`", ephemeral=False
            )
            return

        async with aiosqlite.connect("royal_bot.db") as db:
            # Initialiser si pas existant
            await db.execute("""
                INSERT INTO security_config (guild_id)
                VALUES (?) ON CONFLICT DO NOTHING
            """, (str(interaction.guild.id),))

            if "logs" in action:
                if not salon:
                    await interaction.response.send_message("`❌ Vous devez spécifier un salon.`", ephemeral=False)
                    return
                await db.execute(
                    f"UPDATE security_config SET {action} = ? WHERE guild_id = ?",
                    (str(salon.id), str(interaction.guild.id))
                )
                await interaction.response.send_message(f"`✅ Logs {action} définis sur {salon.mention}`", ephemeral=False)
            else:
                bool_val = value.lower() in ("true", "1", "on")
                await db.execute(
                    f"UPDATE security_config SET {action} = ? WHERE guild_id = ?",
                    (int(bool_val), str(interaction.guild.id))
                )
                await interaction.response.send_message(f"`✅ {action} = {bool_val}`", ephemeral=False)

            await db.commit()

    # ---------- DÉTECTION COMPTE SUSPECT ----------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.get_security_config(member.guild.id)
        if not config or not config["logs_suspect"]:
            return

        # Si le compte a moins de 5 jours
        account_age = datetime.now() - member.created_at
        if account_age.days < 5:
            await self.log_to_channel(
                member.guild,
                config["logs_suspect"],
                f"`⚠️ COMPTE SUSPECT`\n"
                f"**{member.mention}** (`{member}`)\n"
                f"**Créé il y a :** {account_age.days} jours\n"
                f"**ID :** `{member.id}`"
            )

# ========== TABLE DE CONFIG (à ajouter dans db.py) ==========
# Voir ci-dessous

async def setup(bot):
    await bot.add_cog(SecurityCog(bot))