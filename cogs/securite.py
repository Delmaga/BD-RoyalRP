# cogs/securite.py
import discord
from discord.ext import commands
import aiosqlite
import re
from datetime import datetime, timedelta

# Stockage temporaire du spam (RAM)
user_message_history = {}

# === UTILITAIRES DE FORMATAGE ===
def format_time(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d/%m %H:%M:%S")

def safe_truncate(text: str, max_len: int = 180) -> str:
    text = str(text).replace("`", "'").replace("\n", " ")
    return (text[:max_len] + "…") if len(text) > max_len else text

# === DÉTECTION DE CONTENU NON AUTORISÉ ===
def is_forbidden_content(message: discord.Message) -> bool:
    # 1. Texte contenant des liens ou mots clés dangereux
    content = message.content.lower()
    if re.search(r'https?://|www\.|discord\.(gg|com/invite)|\.exe|\.bat|\.dll|\.zip|\.rar', content):
        return True

    # 2. Extensions média non autorisées (GIF, vidéos, etc.)
    if re.search(r'\.(gif|mp4|webm|mov|avi|mkv|flv|swf)', content):
        return True

    # 3. Embeds (souvent utilisés pour contourner)
    if message.embeds:
        return True

    # 4. Pièces jointes non texte/image
    for att in message.attachments:
        if not att.filename.lower().endswith(('.txt', '.png', '.jpg', '.jpeg')):
            return True

    return False

# === COG PRINCIPAL ===
class SecurityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_join_times = {}  # {user_id: datetime}

    async def get_config(self, guild_id: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute("""
                SELECT anti_spam, anti_links, logs_spam, logs_links,
                       logs_messages, logs_vocal, logs_suspect, logs_admin
                FROM security_config WHERE guild_id = ?
            """, (guild_id,))
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
            return {k: None for k in ["anti_spam", "anti_links", "logs_spam", "logs_links",
                                      "logs_messages", "logs_vocal", "logs_suspect", "logs_admin"]}

    async def send_log(self, guild: discord.Guild, channel_id: str, content: str):
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                try:
                    await channel.send(content)
                except:
                    pass

    # ---------- ÉCOUTE DES MESSAGES ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = await self.get_config(str(message.guild.id))

        # --- ANTI-SPAM ---
        if config["anti_spam"]:
            now = datetime.now()
            uid = message.author.id
            if uid not in user_message_history:
                user_message_history[uid] = []
            user_message_history[uid].append((now, message.content))
            # Garder les messages des 5 dernières secondes
            user_message_history[uid] = [
                (ts, c) for ts, c in user_message_history[uid]
                if now - ts < timedelta(seconds=5)
            ]
            if len(user_message_history[uid]) >= 4:
                await message.delete()
                log_msg = (
                    f"`🚨 SPAM — {format_time()}`\n"
                    f"**{message.author}** a envoyé **{len(user_message_history[uid])} messages** en 5s\n"
                    f"**Salon :** {message.channel.mention}\n"
                    f"**Contenu :**\n" +
                    "\n".join(f"> `{safe_truncate(c)}`" for _, c in user_message_history[uid][:4])
                )
                await self.send_log(message.guild, config["logs_spam"], log_msg)
                return

        # --- ANTI-LIEN (CORRIGÉ) ---
        if config["anti_links"] and is_forbidden_content(message):
            await message.delete()
            log_msg = (
                f"`🔗 LIEN BLOQUÉ — {format_time()}`\n"
                f"**{message.author}** a tenté d’envoyer du contenu non autorisé\n"
                f"**Salon :** {message.channel.mention}\n"
                f"**Contenu :**\n> `{safe_truncate(message.content or '[Embed/Pièce jointe]')}`"
            )
            await self.send_log(message.guild, config["logs_links"], log_msg)
            return

        # --- LOGS MESSAGES ---
        if config["logs_messages"]:
            reply_to = ""
            if message.reference:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    reply_to = f" ↝ **répond à** {ref_msg.author}"
                except:
                    pass
            log_msg = (
                f"`💬 {format_time()}`\n"
                f"**{message.author}**{reply_to}\n"
                f"**Salon :** {message.channel.mention}\n"
                f"**Contenu :**\n> `{safe_truncate(message.content)}`"
            )
            await self.send_log(message.guild, config["logs_messages"], log_msg)

    # ---------- ÉCOUTE DU VOCAL ----------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        config = await self.get_config(str(member.guild.id))
        if not config["logs_vocal"]:
            return

        now = datetime.now()
        # Entrée
        if after.channel and after.channel != before.channel:
            self.voice_join_times[member.id] = now
            await self.send_log(
                member.guild,
                config["logs_vocal"],
                f"`🎧 {format_time()}` — **{member}** a rejoint **{after.channel.name}**"
            )
        # Sortie
        if before.channel and before.channel != after.channel:
            start = self.voice_join_times.pop(member.id, None)
            duration = ""
            if start:
                delta = now - start
                mins, secs = divmod(int(delta.total_seconds()), 60)
                duration = f" (**⏱️ {mins}m {secs}s**)"
            await self.send_log(
                member.guild,
                config["logs_vocal"],
                f"`🎧 {format_time()}` — **{member}** a quitté **{before.channel.name}**{duration}"
            )

    # ---------- DÉTECTION COMPTE SUSPECT ----------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = await self.get_config(str(member.guild.id))
        if not config["logs_suspect"]:
            return

        if (datetime.now() - member.created_at).days < 7:
            await self.send_log(
                member.guild,
                config["logs_suspect"],
                f"`⚠️ COMPTE SUSPECT — {format_time()}`\n"
                f"**{member}** (ID: `{member.id}`)\n"
                f"**Créé il y a :** {(datetime.now() - member.created_at).days} jours"
            )

    # ---------- LOGS ADMIN VIA AUDIT LOG ----------
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        if entry.user == self.bot.user:
            return

        config = await self.get_config(str(entry.guild.id))
        if not config["logs_admin"]:
            return

        now = format_time()
        log_content = ""

        # Salon
        if entry.action == discord.AuditLogAction.channel_create:
            log_content = f"`📁 SALON CRÉÉ`\n**{entry.user}** → **#{entry.target.name}**"
        elif entry.action == discord.AuditLogAction.channel_delete:
            name = getattr(entry.target, 'name', 'Inconnu')
            log_content = f"`🗑️ SALON SUPPRIMÉ`\n**{entry.user}** → **#{name}**"
        elif entry.action == discord.AuditLogAction.channel_update:
            if hasattr(entry.changes, 'name'):
                log_content = f"`✏️ SALON RENOMMÉ`\n**{entry.user}** : `#{entry.changes.before.name}` → `#{entry.changes.after.name}`"

        # Rôle
        elif entry.action == discord.AuditLogAction.role_create:
            log_content = f"`🏷️ RÔLE CRÉÉ`\n**{entry.user}** → **@{entry.target.name}**"
        elif entry.action == discord.AuditLogAction.role_delete:
            name = getattr(entry.target, 'name', 'Inconnu')
            log_content = f"`🗑️ RÔLE SUPPRIMÉ`\n**{entry.user}** → **@{name}**"
        elif entry.action == discord.AuditLogAction.role_update:
            if hasattr(entry.changes, 'name'):
                log_content = f"`✏️ RÔLE RENOMMÉ`\n**{entry.user}** : `@{entry.changes.before.name}` → `@{entry.changes.after.name}`"

        # Pseudo
        elif entry.action == discord.AuditLogAction.member_update:
            if hasattr(entry.changes, 'nick'):
                before = entry.changes.nick.before or "`Aucun`"
                after = entry.changes.nick.after or "`Aucun`"
                log_content = f"`👤 PSEUDO MODIFIÉ`\n**{entry.target}** : {before} → {after} (par **{entry.user}**)"

        # Serveur
        elif entry.action == discord.AuditLogAction.guild_update:
            if hasattr(entry.changes, 'name'):
                log_content = f"`🌐 SERVEUR RENOMMÉ`\n`{entry.changes.before.name}` → `{entry.changes.after.name}` (par **{entry.user}**)"

        if log_content:
            await self.send_log(entry.guild, config["logs_admin"], f"`{now}`\n{log_content}")

    # ---------- COMMANDES ADMIN ----------
    @discord.app_commands.command(name="anti_spam", description="Activer/désactiver l'anti-spam")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def anti_spam(self, interaction: discord.Interaction, activer: bool):
        await self.set_flag(interaction, "anti_spam", activer)

    @discord.app_commands.command(name="anti_lien", description="Activer/désactiver l'anti-liens")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def anti_lien(self, interaction: discord.Interaction, activer: bool):
        await self.set_flag(interaction, "anti_links", activer)

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

    @discord.app_commands.command(name="logs_admin", description="Salon des logs d'administration")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_admin(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_admin", salon)

    # Utilitaires de sauvegarde
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

# ========== FONCTION DE SETUP OBLIGATOIRE ==========
async def setup(bot):
    await bot.add_cog(SecurityCog(bot))