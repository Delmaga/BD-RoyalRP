# cogs/moderation_ui.py
import discord
from discord.ext import commands
import aiosqlite
import time
import re

# ---------- MODALES ----------
class WarnModal(discord.ui.Modal, title="⚠️ Avertissement"):
    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target
        self.reason = discord.ui.TextInput(
            label="Raison",
            style=discord.TextStyle.paragraph,
            placeholder="Ex: Spam, insultes, etc.",
            required=True,
            max_length=300
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        mod = interaction.user

        # Log en DB
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO moderation (user_id, mod_id, action, reason, timestamp)
                VALUES (?, ?, 'warn', ?, ?)
            """, (str(self.target.id), str(mod.id), reason, int(time.time())))
            await db.commit()

        # Envoyer un message de confirmation (pas de sanction réelle ici — selon ta logique)
        await interaction.response.send_message(f"`⚠️ {self.target} a reçu un avertissement : {reason}`", ephemeral=True)


class BanMuteModal(discord.ui.Modal):
    def __init__(self, target: discord.Member, action: str):
        super().__init__(title=f"🛡️ {action.title()}")
        self.target = target
        self.action = action

        self.duration = discord.ui.TextInput(
            label="Durée (ex: 30m, 2h, 1d)",
            placeholder="30m → 30 minutes",
            default="1d",
            max_length=10
        )
        self.reason = discord.ui.TextInput(
            label="Raison",
            style=discord.TextStyle.paragraph,
            placeholder="Ex: Spam, tentative de raid...",
            required=True,
            max_length=300
        )
        self.add_item(self.duration)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        duration_str = self.duration.value
        reason = self.reason.value

        # Valider le format
        match = re.fullmatch(r'(\d+)([smhd])', duration_str.strip().lower())
        if not match:
            await interaction.response.send_message("`❌ Format de durée invalide. Ex: 30m, 2h, 1d.`", ephemeral=True)
            return

        amount, unit = match.groups()
        seconds = int(amount) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit]

        # Appliquer l'action
        if self.action == "ban":
            try:
                await interaction.guild.ban(self.target, reason=reason)
                msg = f"`✅ {self.target} banni pour {duration_str} : {reason}`"
            except Exception as e:
                await interaction.response.send_message(f"`❌ Échec du ban : {e}`", ephemeral=True)
                return
        elif self.action == "mute":
            # À compléter avec rôle "Muted" si tu l’implémentes
            msg = f"`🔇 {self.target} muté pour {duration_str} : {reason}`"
        else:
            await interaction.response.send_message("`⚠️ Action inconnue.`", ephemeral=True)
            return

        # Log en DB
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO moderation (user_id, mod_id, action, reason, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(self.target.id), str(interaction.user.id), self.action, reason, duration_str, int(time.time())))
            await db.commit()

        await interaction.response.send_message(msg, ephemeral=True)


# ---------- SELECT MENU ----------
class ActionSelect(discord.ui.Select):
    def __init__(self, target: discord.Member):
        self.target = target
        options = [
            discord.SelectOption(label="Bannir", value="ban", emoji="🔨"),
            discord.SelectOption(label="Muter", value="mute", emoji="🔇"),
            discord.SelectOption(label="Avertir", value="warn", emoji="⚠️"),
        ]
        super().__init__(placeholder="Choisissez une action", options=options)

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]
        if action == "warn":
            await interaction.response.send_modal(WarnModal(self.target))
        else:
            await interaction.response.send_modal(BanMuteModal(self.target, action))


class ActionView(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=60)
        self.add_item(ActionSelect(target))


# ---------- COMMANDE /modo ----------
class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="modo", description="Interface de modération avancée")
    @discord.app_commands.checks.has_permissions(kick_members=True)
    async def modo(self, interaction: discord.Interaction, membre: discord.Member):
        if membre == interaction.user:
            await interaction.response.send_message("`❌ Vous ne pouvez pas vous sanctionner.`", ephemeral=True)
            return
        if membre.top_role >= interaction.user.top_role:
            await interaction.response.send_message("`❌ Permission insuffisante.`", ephemeral=True)
            return

        view = ActionView(membre)
        embed = discord.Embed(
            title="🛡️ Modération",
            description=f"Sélectionnez une action à appliquer à {membre.mention}.",
            color=0xFF5555
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))