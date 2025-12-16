# cogs/moderation_ui.py
import discord
from discord.ext import commands
import aiosqlite
import time
import re

class ModoModal(discord.ui.Modal, title="🛡️ Sanctionner un membre"):
    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

        # Action : ban, mute, warn
        self.action_input = discord.ui.TextInput(
            label="Action",
            placeholder="Tapez : ban, mute, ou warn",
            default="ban",
            max_length=5
        )
        # Durée : seulement pour ban/mute
        self.duration_input = discord.ui.TextInput(
            label="Durée (ex: 30m, 2h, 1d)",
            placeholder="Laisser vide si 'warn'",
            required=False,
            max_length=10
        )
        # Raison : toujours requise
        self.reason_input = discord.ui.TextInput(
            label="Raison",
            style=discord.TextStyle.paragraph,
            placeholder="Ex: Spam, insultes, etc.",
            required=True,
            max_length=300
        )
        self.add_item(self.action_input)
        self.add_item(self.duration_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        action = self.action_input.value.strip().lower()
        duration_str = self.duration_input.value.strip()
        reason = self.reason_input.value

        # Validation de l'action
        if action not in ("ban", "mute", "warn"):
            await interaction.response.send_message("`❌ Action invalide. Utilisez : ban, mute, ou warn.`", ephemeral=True)
            return

        # Pour 'warn', pas de durée
        if action == "warn":
            # Log en DB
            async with aiosqlite.connect("royal_bot.db") as db:
                await db.execute("""
                    INSERT INTO moderation (user_id, mod_id, action, reason, timestamp)
                    VALUES (?, ?, 'warn', ?, ?)
                """, (str(self.target.id), str(interaction.user.id), reason, int(time.time())))
                await db.commit()

            await interaction.response.send_message(f"`⚠️ {self.target} a reçu un avertissement : {reason}`", ephemeral=True)
            return

        # Pour 'ban' ou 'mute' : durée obligatoire
        if not duration_str:
            await interaction.response.send_message("`❌ La durée est requise pour ban/mute.`", ephemeral=True)
            return

        # Valider le format de la durée
        match = re.fullmatch(r'(\d+)([smhd])', duration_str.lower())
        if not match:
            await interaction.response.send_message("`❌ Format durée invalide. Ex: 30m, 2h, 1d.`", ephemeral=True)
            return

        # Appliquer la sanction
        if action == "ban":
            try:
                await interaction.guild.ban(self.target, reason=reason)
                msg = f"`✅ {self.target} banni ({duration_str}) : {reason}`"
            except Exception as e:
                await interaction.response.send_message(f"`❌ Échec du ban : {e}`", ephemeral=True)
                return
        elif action == "mute":
            msg = f"`🔇 {self.target} muté ({duration_str}) : {reason}`"
            # (À compléter avec rôle "Muted" si implémenté)

        # Log en DB
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO moderation (user_id, mod_id, action, reason, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(self.target.id), str(interaction.user.id), action, reason, duration_str, int(time.time())))
            await db.commit()

        await interaction.response.send_message(msg, ephemeral=True)

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="modo", description="Sanctionner un membre via interface unique")
    @discord.app_commands.checks.has_permissions(kick_members=True)
    async def modo(self, interaction: discord.Interaction, membre: discord.Member):
        if membre == interaction.user:
            await interaction.response.send_message("`❌ Vous ne pouvez pas vous sanctionner.`", ephemeral=True)
            return
        if membre.top_role >= interaction.user.top_role:
            await interaction.response.send_message("`❌ Permission insuffisante.`", ephemeral=True)
            return

        modal = ModoModal(membre)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))