import discord
from discord.ext import commands
import aiosqlite
import time
import re

def parse_duration(time_str: str):
    time_str = time_str.strip().lower()
    match = re.fullmatch(r'(\d+)([smhd])', time_str)
    if not match:
        return None
    amount, unit = match.groups()
    amount = int(amount)
    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return amount * multipliers[unit]

class ModoModal(discord.ui.Modal, title="🛡️ Sanctionner un membre"):
    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

        self.duration = discord.ui.TextInput(
            label="Durée (ex: 30m, 2h, 1d)",
            placeholder="30m → 30 minutes",
            default="1d",
            max_length=10
        )
        self.reason = discord.ui.TextInput(
            label="Raison",
            style=discord.TextStyle.paragraph,
            placeholder="Ex: Spam, insultes, etc.",
            required=True,
            max_length=300
        )
        self.add_item(self.duration)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        duration_str = self.duration.value
        reason = self.reason.value

        seconds = parse_duration(duration_str)
        if seconds is None:
            await interaction.response.send_message("`❌ Format de durée invalide. Utilisez 30s, 10m, 2h, 1d.`", ephemeral=True)
            return

        try:
            await interaction.guild.ban(self.target, reason=reason)
            msg = f"`✅ {self.target} banni pour {duration_str} : {reason}`"
        except Exception as e:
            await interaction.response.send_message(f"`❌ Échec du ban : {e}`", ephemeral=True)
            return

        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO moderation (user_id, mod_id, action, reason, duration, timestamp)
                VALUES (?, ?, 'ban', ?, ?, ?)
            """, (str(self.target.id), str(interaction.user.id), reason, duration_str, int(time.time())))
            await db.commit()

        await interaction.response.send_message(msg, ephemeral=True)

class ModerationSimple(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="modo", description="Bannir un membre via interface")
    @discord.app_commands.checks.has_permissions(ban_members=True)
    async def modo(self, interaction: discord.Interaction, membre: discord.Member):
        if membre == interaction.user:
            await interaction.response.send_message("`❌ Vous ne pouvez pas vous sanctionner.`", ephemeral=True)
            return
        if membre.top_role >= interaction.user.top_role:
            await interaction.response.send_message("`❌ Permission insuffisante.`", ephemeral=True)
            return

        await interaction.response.send_modal(ModoModal(membre))

async def setup(bot):
    await bot.add_cog(ModerationSimple(bot))