# cogs/securite.py (extrait amélioré)

import discord
from discord.ext import commands
import aiosqlite
import re
from datetime import datetime, timedelta

user_message_history = {}

# === BEAUTY UTILS ===
def format_timestamp(dt: datetime = None):
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d/%m %H:%M:%S")

def safe_content(content: str, max_len=150):
    content = content.replace("`", "'")
    if len(content) > max_len:
        return content[:max_len] + "…"
    return content

# === ANTI-LIEN AMÉLIORÉ ===
def contains_forbidden_content(message: discord.Message) -> bool:
    # 1. Texte brut
    text = message.content.lower()
    if re.search(r'https?://|www\.|discord\.(gg|com/invite)', text):
        return True

    # 2. Extensions de fichiers
    dangerous_ext = ('.gif', '.exe', '.bat', '.dll', '.zip', '.rar', '.mp4', '.webm', '.mov')
    if any(ext in text for ext in dangerous_ext):
        return True

    # 3. Embeds (souvent utilisés pour contourner)
    for embed in message.embeds:
        if embed.url or embed.image or embed.video:
            return True

    # 4. Pièces jointes non autorisées
    for attach in message.attachments:
        if not attach.filename.lower().endswith(('.txt', '.png', '.jpg', '.jpeg')):
            return True

    return False

# === LOGS AMÉLIORÉS ===
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
                return {k: v for k, v in zip([
                    "anti_spam", "anti_links", "logs_spam", "logs_links",
                    "logs_messages", "logs_vocal", "logs_suspect", "logs_admin"
                ], row)}
            return {k: None for k in ["anti_spam", "anti_links", "logs_spam", "logs_links", "logs_messages", "logs_vocal", "logs_suspect", "logs_admin"]}

    async def log(self, guild, channel_id, content):
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                await channel.send(content)

    # --- LOGS MESSAGES (BEAU) ---
    def build_message_log(self, author, channel, content, reply_to=None):
        reply = f" ↝ **répond à** {reply_to}" if reply_to else ""
        return (
            f"`💬 {format_timestamp()}`\n"
            f"**{author}**{reply}\n"
            f"**Salon :** {channel.mention}\n"
            f"**Contenu :**\n> `{safe_content(content)}`"
        )

    # --- LOGS SPAM (BEAU) ---
    def build_spam_log(self, author, channel, messages):
        msgs = "\n".join(f"> `{safe_content(m)}`" for _, m in messages[:4])
        return (
            f"`🚨 SPAM — {format_timestamp()}`\n"
            f"**{author}** a envoyé **{len(messages)} messages** en 5s\n"
            f"**Salon :** {channel.mention}\n"
            f"**Messages :**\n{msgs}"
        )

    # --- LOGS LIENS (BEAU) ---
    def build_link_log(self, author, channel, content):
        return (
            f"`🔗 LIEN BLOQUÉ — {format_timestamp()}`\n"
            f"**{author}** a tenté d’envoyer du contenu non autorisé\n"
            f"**Salon :** {channel.mention}\n"
            f"**Contenu :**\n> `{safe_content(content)}`"
        )

    # --- LOGS VOCAL (BEAU) ---
    def build_vocal_log(self, member, action, channel_name, duration=None):
        base = f"`🎧 {format_timestamp()}` — **{member}** {action} **{channel_name}**"
        if duration:
            base += f" (**⏱️ {duration}**)"
        return base

    # --- ÉVÉNEMENTS ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        config = await self.get_security_config(message.guild.id)

        # ANTI-SPAM
        if config.get("anti_spam"):
            now = datetime.now()
            uid = message.author.id
            if uid not in user_message_history:
                user_message_history[uid] = []
            user_message_history[uid].append((now, message.content))
            user_message_history[uid] = [
                (ts, c) for ts, c in user_message_history[uid]
                if now - ts < timedelta(seconds=5)
            ]
            if len(user_message_history[uid]) >= 4:
                await message.delete()
                await self.log(
                    message.guild,
                    config.get("logs_spam"),
                    self.build_spam_log(message.author, message.channel, user_message_history[uid])
                )
                return

        # ANTI-LIEN (CORRIGÉ)
        if config.get("anti_links") and contains_forbidden_content(message):
            await message.delete()
            await self.log(
                message.guild,
                config.get("logs_links"),
                self.build_link_log(message.author, message.channel, message.content or "[Pièce jointe/Embed]")
            )
            return

        # LOGS MESSAGES
        if config.get("logs_messages"):
            reply_to = None
            if message.reference:
                try:
                    ref = await message.channel.fetch_message(message.reference.message_id)
                    reply_to = ref.author
                except:
                    pass
            await self.log(
                message.guild,
                config.get("logs_messages"),
                self.build_message_log(message.author, message.channel, message.content, reply_to)
            )

    # --- VOCAL ---
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        config = await self.get_security_config(member.guild.id)
        if not config.get("logs_vocal"):
            return

        now = datetime.now()
        if after.channel and after.channel != before.channel:
            self.voice_join_times[member.id] = now
            await self.log(
                member.guild,
                config.get("logs_vocal"),
                self.build_vocal_log(member, "a rejoint", after.channel.name)
            )
        if before.channel and before.channel != after.channel:
            start = self.voice_join_times.pop(member.id, None)
            duration = None
            if start:
                delta = now - start
                mins, secs = divmod(int(delta.total_seconds()), 60)
                duration = f"{mins}m {secs}s"
            await self.log(
                member.guild,
                config.get("logs_vocal"),
                self.build_vocal_log(member, "a quitté", before.channel.name, duration)
            )

    # --- AUDIT LOG (ADMIN) — AMÉLIORÉ ---
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        if entry.user == self.bot.user:
            return

        config = await self.get_security_config(entry.guild.id)
        if not config.get("logs_admin"):
            return

        now = format_timestamp()
        def send_log(title, details):
            return self.log(entry.guild, config["logs_admin"], f"`{now}`\n`{title}`\n{details}")

        # Salon
        if entry.action == discord.AuditLogAction.channel_create:
            await send_log("📁 SALON CRÉÉ", f"**{entry.user}** → **#{entry.target.name}**")
        elif entry.action == discord.AuditLogAction.channel_delete:
            await send_log("🗑️ SALON SUPPRIMÉ", f"**{entry.user}** → **#{getattr(entry.target, 'name', 'Inconnu')}**")
        elif entry.action == discord.AuditLogAction.channel_update:
            if hasattr(entry.changes, 'name'):
                await send_log("✏️ SALON RENOMMÉ", f"**{entry.user}** : `#{entry.changes.before.name}` → `#{entry.changes.after.name}`")

        # Rôle
        elif entry.action == discord.AuditLogAction.role_create:
            await send_log("🏷️ RÔLE CRÉÉ", f"**{entry.user}** → **@{entry.target.name}**")
        elif entry.action == discord.AuditLogAction.role_delete:
            await send_log("🗑️ RÔLE SUPPRIMÉ", f"**{entry.user}** → **@{getattr(entry.target, 'name', 'Inconnu')}**")
        elif entry.action == discord.AuditLogAction.role_update:
            if hasattr(entry.changes, 'name'):
                await send_log("✏️ RÔLE RENOMMÉ", f"**{entry.user}** : `@{entry.changes.before.name}` → `@{entry.changes.after.name}`")

        # Pseudo
        elif entry.action == discord.AuditLogAction.member_update:
            if hasattr(entry.changes, 'nick'):
                before = entry.changes.nick.before or "`Aucun`"
                after = entry.changes.nick.after or "`Aucun`"
                await send_log("👤 PSEUDO MODIFIÉ", f"**{entry.target}** : {before} → {after} (par **{entry.user}**)")

        # Serveur
        elif entry.action == discord.AuditLogAction.guild_update:
            if hasattr(entry.changes, 'name'):
                await send_log("🌐 SERVEUR RENOMMÉ", f"`{entry.changes.before.name}` → `{entry.changes.after.name}` (par **{entry.user}**)")

    # --- COMMANDES (inchangées, mais fonctionnelles) ---
    # (incluses dans la version précédente)