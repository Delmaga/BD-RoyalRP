# cogs/securite.py
import discord
from discord.ext import commands
import aiosqlite
import re
from datetime import datetime, timedelta

user_message_history = {}

class SecurityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_join_times = {}

    async def get_security_config(self, guild_id):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT anti_spam, anti_links, logs_spam, logs_links, logs_messages, logs_vocal, logs_suspect, logs_admin FROM security_config WHERE guild_id = ?",
                (str(guild_id),)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "anti_spam": bool(row[0]),
                    "anti_links": bool(row[1]),
                    "logs_spam": row[2],
                    "logs_links": row[3],
                    "logs_messages": row[4],
                    "logs_vocal": row[5],
                    "logs_suspect": row[6],
                    "logs_admin": row[7]
                }
            return {
                "anti_spam": False, "anti_links": False,
                "logs_spam": None, "logs_links": None, "logs_messages": None,
                "logs_vocal": None, "logs_suspect": None, "logs_admin": None
            }

    async def log_to_channel(self, guild, channel_id, content):
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                await channel.send(content)

    # ========== ANTI-SPAM + ANTI-LIENS ==========
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        config = await self.get_security_config(message.guild.id)

        # --- Anti-spam ---
        if config["anti_spam"]:
            now = datetime.now()
            user_id = message.author.id
            if user_id not in user_message_history:
                user_message_history[user_id] = []
            user_message_history[user_id].append((now, message.content))

            # Nettoyage auto
            user_message_history[user_id] = [
                (ts, msg) for ts, msg in user_message_history[user_id]
                if now - ts < timedelta(seconds=5)
            ]

            if len(user_message_history[user_id]) >= 4:
                await message.delete()
                await self.log_to_channel(
                    message.guild,
                    config["logs_spam"],
                    f"`🚨 SPAM — {now.strftime('%d/%m %H:%M')}`\n"
                    f"**Utilisateur :** {message.author.mention}\n"
                    f"**Salon :** {message.channel.mention}\n"
                    f"**Messages :**\n" + "\n".join([m for _, m in user_message_history[user_id][:4]])
                )
                return

        # --- Anti-liens ---
        if config["anti_links"]:
            if re.search(r'https?://|discord\.(gg|com/invite)|www\.|\.gif|\.png|\.jpg|\.jpeg', message.content, re.IGNORECASE):
                await message.delete()
                await self.log_to_channel(
                    message.guild,
                    config["logs_links"],
                    f"`🔗 LIEN BLOQUÉ — {now.strftime('%d/%m %H:%M')}`\n"
                    f"**Utilisateur :** {message.author.mention}\n"
                    f"**Salon :** {message.channel.mention}\n"
                    f"**Contenu :** `{message.content}`"
                )
                return

        # --- Logs messages ---
        if config["logs_messages"]:
            now = datetime.now()
            await self.log_to_channel(
                message.guild,
                config["logs_messages"],
                f"`💬 {now.strftime('%d/%m %H:%M')}` — {message.author} dans {message.channel.mention} :\n> {message.content}"
            )

    # ========== VOCAL ==========
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        config = await self.get_security_config(member.guild.id)
        if not config["logs_vocal"]:
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
            join_time = self.voice_join_times.pop(member.id, None)
            if join_time:
                delta = now - join_time
                mins, secs = divmod(int(delta.total_seconds()), 60)
                await self.log_to_channel(
                    member.guild,
                    config["logs_vocal"],
                    f"`🎧 {now.strftime('%d/%m %H:%M')}` — {member} a quitté **{before.channel.name}** (durée : {mins}m {secs}s)"
                )

    # ========== COMPTE SUSPECT ==========
    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.get_security_config(member.guild.id)
        if not config["logs_suspect"]:
            return

        if (datetime.now() - member.created_at).days < 7:
            await self.log_to_channel(
                member.guild,
                config["logs_suspect"],
                f"`⚠️ COMPTE SUSPECT — {datetime.now().strftime('%d/%m %H:%M')}`\n"
                f"**{member}** (ID: `{member.id}`)\n"
                f"**Créé il y a :** {(datetime.now() - member.created_at).days} jours"
            )

    # ========== LOGS ADMIN VIA AUDIT LOG ==========
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        if entry.user == self.bot.user:
            return

        config = await self.get_security_config(entry.guild.id)
        if not config["logs_admin"]:
            return

        now = datetime.now().strftime("%d/%m %H:%M")
        content = ""

        # Salon / Catégorie
        if entry.action in (discord.AuditLogAction.channel_create, discord.AuditLogAction.channel_delete):
            target = getattr(entry, 'target', None)
            name = getattr(target, 'name', 'Inconnu')
            action_str = "CRÉÉ" if entry.action == discord.AuditLogAction.channel_create else "SUPPRIMÉ"
            content = f"`📁 SALON {action_str}`\n**{entry.user}** a {action_str.lower()} **#{name}**"

        elif entry.action == discord.AuditLogAction.channel_update:
            changes = entry.changes
            if hasattr(changes, 'name'):
                before = getattr(changes.before, 'name', '???')
                after = getattr(changes.after, 'name', '???')
                content = f"`✏️ SALON RENOMMÉ`\n**{entry.user}** : **#{before} → #{after}**"

        # Rôle
        elif entry.action in (discord.AuditLogAction.role_create, discord.AuditLogAction.role_delete):
            target = getattr(entry, 'target', None)
            name = getattr(target, 'name', 'Inconnu')
            action_str = "CRÉÉ" if entry.action == discord.AuditLogAction.role_create else "SUPPRIMÉ"
            content = f"`🏷️ RÔLE {action_str}`\n**{entry.user}** a {action_str.lower()} **@{name}**"

        elif entry.action == discord.AuditLogAction.role_update:
            changes = entry.changes
            if hasattr(changes, 'name'):
                before = getattr(changes.before, 'name', '???')
                after = getattr(changes.after, 'name', '???')
                content = f"`✏️ RÔLE RENOMMÉ`\n**{entry.user}** : **@{before} → @{after}**"

        # Pseudo utilisateur
        elif entry.action == discord.AuditLogAction.member_update:
            if hasattr(entry.changes, 'nick'):
                before = entry.changes.nick.before or "Aucun"
                after = entry.changes.nick.after or "Aucun"
                content = f"`👤 PSEUDO MODIFIÉ`\n**{entry.target}** : **{before} → {after}** (par {entry.user})"

        # Nom du serveur
        elif entry.action == discord.AuditLogAction.guild_update:
            if hasattr(entry.changes, 'name'):
                before = entry.changes.name.before
                after = entry.changes.name.after
                content = f"`🌐 SERVEUR RENOMMÉ`\n**{before} → {after}** (par {entry.user})"

        if content:
            await self.log_to_channel(entry.guild, config["logs_admin"], f"`{now}`\n{content}")

    # ========== COMMANDES ADMIN ==========
    @discord.app_commands.command(name="anti_spam", description="Activer/désactiver l'anti-spam")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def anti_spam(self, interaction: discord.Interaction, activer: bool):
        await self.set_flag(interaction, "anti_spam", activer)

    @discord.app_commands.command(name="anti_lien", description="Activer/désactiver l'anti-liens")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def anti_lien(self, interaction: discord.Interaction, activer: bool):
        await self.set_flag(interaction, "anti_links", activer)

    # Logs
    @discord.app_commands.command(name="logs_spam", description="Salon des logs de spam")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_spam(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_spam", salon)

    @discord.app_commands.command(name="logs_liens", description="Salon des logs de liens")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_liens(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_links", salon)

    @discord.app_commands.command(name="logs_message", description="Salon des logs de messages")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_message(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_messages", salon)

    @discord.app_commands.command(name="logs_vocal", description="Salon des logs vocaux")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_vocal(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_vocal", salon)

    @discord.app_commands.command(name="logs_suspect", description="Salon des comptes suspects")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_suspect(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_suspect", salon)

    @discord.app_commands.command(name="logs_admin", description="Salon des logs d'administration (salons, rôles, etc.)")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_admin(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_admin", salon)

    # Utilitaires
    async def set_flag(self, interaction, column, value):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(f"""
                INSERT INTO security_config (guild_id, {column})
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET {column} = excluded.{column}
            """, (str(interaction.guild.id), int(value)))
            await db.commit()
        await interaction.response.send_message(f"`✅ {column.replace('_', ' ').title()} = {value}`", ephemeral=False)

    async def set_log_channel(self, interaction, column, salon):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(f"""
                INSERT INTO security_config (guild_id, {column})
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET {column} = excluded.{column}
            """, (str(interaction.guild.id), str(salon.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ {column.replace('_', ' ').title()} → {salon.mention}`", ephemeral=False)

async def setup(bot):
    await bot.add_cog(SecurityCog(bot))