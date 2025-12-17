# cogs/securite.py
import discord
from discord.ext import commands
import aiosqlite
import re
from datetime import datetime, timedelta

# Stockage temporaire du spam
user_message_history = {}

class SecurityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_join_times = {}

    # ---------- UTILITAIRES ----------
    async def get_security_config(self, guild_id):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT enabled, logs_spam, logs_links, logs_messages, logs_vocal, logs_suspect FROM security_config WHERE guild_id = ?",
                (str(guild_id),)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "enabled": bool(row[0]),
                    "logs_spam": row[1],
                    "logs_links": row[2],
                    "logs_messages": row[3],
                    "logs_vocal": row[4],
                    "logs_suspect": row[5]
                }
            return {"enabled": False}

    async def log_to_channel(self, guild, channel_id, content):
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                await channel.send(content)

    # ---------- ÉVÉNEMENTS ----------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        config = await self.get_security_config(message.guild.id)
        if not config["enabled"]:
            return

        # --- ANTI-SPAM (4 messages en 5 sec) ---
        now = datetime.now()
        user_id = message.author.id
        if user_id not in user_message_history:
            user_message_history[user_id] = []
        user_message_history[user_id].append((now, message.content))

        # Nettoyage automatique (garder 5 sec)
        user_message_history[user_id] = [
            (ts, msg) for ts, msg in user_message_history[user_id]
            if now - ts < timedelta(seconds=5)
        ]

        if len(user_message_history[user_id]) >= 4:
            await message.delete()
            await self.log_to_channel(
                message.guild,
                config["logs_spam"],
                f"`🚨 SPAM DÉTECTÉ`\n"
                f"**Utilisateur :** {message.author.mention} (`{message.author}`)\n"
                f"**Salon :** {message.channel.mention}\n"
                f"**Messages :**\n" + "\n".join([m for _, m in user_message_history[user_id][:4]])
            )
            return

        # --- ANTI-LIENS ---
        if re.search(r'https?://|discord\.(gg|com/invite)|www\.|\.gif|\.png|\.jpg', message.content, re.IGNORECASE):
            await message.delete()
            await self.log_to_channel(
                message.guild,
                config["logs_links"],
                f"`🔗 LIEN BLOQUÉ`\n"
                f"**Utilisateur :** {message.author.mention}\n"
                f"**Salon :** {message.channel.mention}\n"
                f"**Contenu :** `{message.content}`"
            )
            return

        # --- LOGS MESSAGES ---
        await self.log_to_channel(
            message.guild,
            config["logs_messages"],
            f"`💬 {now.strftime('%d/%m %H:%M')}` — {message.author} dans {message.channel.mention} :\n> {message.content}"
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        config = await self.get_security_config(member.guild.id)
        if not config["enabled"] or not config["logs_vocal"]:
            return

        now = datetime.now()
        if after.channel and after.channel != before.channel:
            self.voice_join_times[member.id] = now
            await self.log_to_channel(
                member.guild,
                config["logs_vocal"],
                f"`🎧 {now.strftime('%d/%m %H:%M')}` — {member} a rejoint **{after.channel.name}**"
            )
        if before.channel and before.channel != after.channel:
            join_time = self.voice_join_times.get(member.id)
            if join_time:
                delta = now - join_time
                mins, secs = divmod(int(delta.total_seconds()), 60)
                await self.log_to_channel(
                    member.guild,
                    config["logs_vocal"],
                    f"`🎧 {now.strftime('%d/%m %H:%M')}` — {member} a quitté **{before.channel.name}** (durée : {mins}m {secs}s)"
                )
                del self.voice_join_times[member.id]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.get_security_config(member.guild.id)
        if not config["enabled"] or not config["logs_suspect"]:
            return

        # Compte créé il y a moins de 7 jours
        if (datetime.now() - member.created_at).days < 7:
            await self.log_to_channel(
                member.guild,
                config["logs_suspect"],
                f"`⚠️ COMPTE SUSPECT`\n"
                f"**{member}** (ID: `{member.id}`)\n"
                f"**Créé il y a :** {(datetime.now() - member.created_at).days} jours"
            )

    # ---------- COMMANDES ADMIN ----------
    @discord.app_commands.command(name="securite", description="Activer ou désactiver la sécurité complète")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def securite(self, interaction: discord.Interaction, activer: bool):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO security_config (guild_id, enabled)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET enabled = excluded.enabled
            """, (str(interaction.guild.id), int(activer)))
            await db.commit()
        status = "activée" if activer else "désactivée"
        await interaction.response.send_message(f"`✅ Sécurité {status} sur tout le serveur.`", ephemeral=False)

    # Commandes de configuration des logs (séparées)
    @discord.app_commands.command(name="logs_spam", description="Définir le salon des logs de spam")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_spam(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_spam", salon)

    @discord.app_commands.command(name="logs_liens", description="Définir le salon des logs de liens")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_liens(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_links", salon)

    @discord.app_commands.command(name="logs_message", description="Définir le salon des logs de messages")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_message(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_messages", salon)

    @discord.app_commands.command(name="logs_vocal", description="Définir le salon des logs vocaux")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_vocal(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_vocal", salon)

    @discord.app_commands.command(name="logs_suspect", description="Définir le salon des comptes suspects")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_suspect(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_suspect", salon)

    async def set_log_channel(self, interaction, column, salon):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(f"""
                INSERT INTO security_config (guild_id, {column})
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET {column} = excluded.{column}
            """, (str(interaction.guild.id), str(salon.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ Salon de logs {column} défini sur {salon.mention}`", ephemeral=False)

async def setup(bot):
    await bot.add_cog(SecurityCog(bot))