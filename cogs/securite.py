# cogs/securite.py
import discord
from discord.ext import commands
import aiosqlite
import re
from datetime import datetime, timedelta

user_message_history = {}

def safe_truncate(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    text = str(text).replace("`", "'").replace("\n", " ")
    return (text[:max_len] + "…") if len(text) > max_len else text

def is_forbidden_content(message: discord.Message) -> bool:
    if re.search(r'https?://|www\.|discord\.(gg|com/invite)', message.content, re.IGNORECASE):
        return True
    for att in message.attachments:
        if not att.filename.lower().endswith(('.txt', '.png', '.jpg', '.jpeg')):
            return True
    if message.embeds:
        return True
    if re.search(r'\.(gif|mp4|webm|mov|avi|mkv|exe|bat|dll|zip|rar)', message.content, re.IGNORECASE):
        return True
    return False

class SecurityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_join_times = {}

    async def get_config(self, guild_id):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute("""
                SELECT anti_spam, anti_links, logs_spam, logs_links,
                       logs_messages, logs_vocal, logs_suspect, logs_admin
                FROM security_config WHERE guild_id = ?
            """, (guild_id,))
            row = await cursor.fetchone()
            if row:
                return {k: v for k, v in zip([
                    "anti_spam", "anti_links", "logs_spam", "logs_links",
                    "logs_messages", "logs_vocal", "logs_suspect", "logs_admin"
                ], row)}
            return {k: None for k in ["anti_spam", "anti_links", "logs_spam", "logs_links",
                                      "logs_messages", "logs_vocal", "logs_suspect", "logs_admin"]}

    async def send_log(self, guild, channel_id, content):
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                await channel.send(content)

    def build_vocal_log(self, member, join_time, leave_time, channel_name):
        duration = ""
        if join_time and leave_time:
            delta = leave_time - join_time
            mins, secs = divmod(int(delta.total_seconds()), 60)
            duration = f"\n⏱️ Durée : {mins}m {secs}s"
        return (
            f"{member.mention}\n\n"
            f"Arrivé : {join_time.strftime('%d/%m %H:%M:%S')}\n"
            f"Parti : {leave_time.strftime('%d/%m %H:%M:%S')}\n"
            f"Salon : 🎙️ {channel_name}"
            f"{duration}"
        )

    def build_message_log(self, author, content, channel, timestamp):
        return (
            f"{author.mention}\n\n"
            f"Message :\n"
            f"`{safe_truncate(content)}`\n\n"
            f"📅 {timestamp.strftime('%d/%m %H:%M:%S')} • {channel.mention}"
        )

    def build_spam_log(self, author, messages, channel, timestamp):
        msgs = "\n".join(f"`{safe_truncate(m)}`" for _, m in messages[:4])
        return (
            f"{author.mention}\n\n"
            f"🚨 SPAM DÉTECTÉ\n"
            f"Messages envoyés : {len(messages)} en 5s\n\n"
            f"{msgs}\n\n"
            f"📅 {timestamp.strftime('%d/%m %H:%M:%S')} • {channel.mention}"
        )

    def build_link_log(self, author, content, channel, timestamp):
        return (
            f"{author.mention}\n\n"
            f"🔗 LIEN BLOQUÉ\n"
            f"Contenu non autorisé :\n\n"
            f"`{safe_truncate(content or '[Contenu caché]')}`\n\n"
            f"📅 {timestamp.strftime('%d/%m %H:%M:%S')} • {channel.mention}"
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        config = await self.get_config(str(message.guild.id))
        now = datetime.now()

        if config["anti_spam"]:
            uid = message.author.id
            if uid not in user_message_history:
                user_message_history[uid] = []
            user_message_history[uid].append((now, message.content))
            user_message_history[uid] = [(ts, c) for ts, c in user_message_history[uid] if now - ts < timedelta(seconds=5)]
            if len(user_message_history[uid]) >= 4:
                await message.delete()
                await self.send_log(message.guild, config["logs_spam"], self.build_spam_log(message.author, user_message_history[uid], message.channel, now))
                return

        if config["anti_links"] and is_forbidden_content(message):
            await message.delete()
            await self.send_log(message.guild, config["logs_links"], self.build_link_log(message.author, message.content, message.channel, now))
            return

        if config["logs_messages"]:
            await self.send_log(message.guild, config["logs_messages"], self.build_message_log(message.author, message.content, message.channel, now))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        config = await self.get_config(str(member.guild.id))
        if not config["logs_vocal"]:
            return

        now = datetime.now()
        if after.channel and after.channel != before.channel:
            self.voice_join_times[member.id] = now
        if before.channel and before.channel != after.channel:
            join_time = self.voice_join_times.pop(member.id, None)
            if join_time:
                await self.send_log(member.guild, config["logs_vocal"], self.build_vocal_log(member, join_time, now, before.channel.name))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.get_config(str(member.guild.id))
        if not config["logs_suspect"]:
            return
        if (datetime.now() - member.created_at).days < 7:
            await self.send_log(
                member.guild,
                config["logs_suspect"],
                f"{member.mention}\n\n⚠️ COMPTE SUSPECT\nCréé il y a {(datetime.now() - member.created_at).days} jours\n\n📅 {datetime.now().strftime('%d/%m %H:%M:%S')}"
            )

    @discord.app_commands.command(name="anti_spam")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def anti_spam(self, interaction: discord.Interaction, activer: bool):
        await self.set_flag(interaction, "anti_spam", activer)

    @discord.app_commands.command(name="anti_lien")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def anti_lien(self, interaction: discord.Interaction, activer: bool):
        await self.set_flag(interaction, "anti_links", activer)

    @discord.app_commands.command(name="logs_spam")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_spam(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_spam", salon)

    @discord.app_commands.command(name="logs_liens")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_liens(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_links", salon)

    @discord.app_commands.command(name="logs_message")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_message(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_messages", salon)

    @discord.app_commands.command(name="logs_vocal")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_vocal(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_vocal", salon)

    @discord.app_commands.command(name="logs_suspect")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_suspect(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_suspect", salon)

    @discord.app_commands.command(name="logs_admin")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def logs_admin(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await self.set_log_channel(interaction, "logs_admin", salon)

    async def set_flag(self, interaction, column, value):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(f"INSERT INTO security_config (guild_id, {column}) VALUES (?, ?) ON CONFLICT DO UPDATE SET {column} = excluded.{column}", (str(interaction.guild.id), int(value)))
            await db.commit()
        await interaction.response.send_message(f"`✅ {column.replace('_', ' ').title()} = {value}`", ephemeral=False)

    async def set_log_channel(self, interaction, column, salon):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(f"INSERT INTO security_config (guild_id, {column}) VALUES (?, ?) ON CONFLICT DO UPDATE SET {column} = excluded.{column}", (str(interaction.guild.id), str(salon.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ {column.replace('_', ' ').title()} → {salon.mention}`", ephemeral=False)

async def setup(bot):
    await bot.add_cog(SecurityCog(bot))