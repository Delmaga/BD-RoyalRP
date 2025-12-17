# cogs/bypass.py
import discord
from discord.ext import commands

class BypassCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="bypass_add", description="Donner l'accès à un salon à un membre")
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    async def bypass_add(self, interaction: discord.Interaction, membre: discord.Member, salon: discord.TextChannel):
        # Vérifier que le membre n'a pas déjà accès
        perms = salon.permissions_for(membre)
        if perms.read_messages:
            await interaction.response.send_message(f"`⚠️ {membre} a déjà accès à {salon.mention}.`", ephemeral=False)
            return

        # Donner l'accès
        try:
            await salon.set_permissions(membre, read_messages=True, send_messages=True)
            await interaction.response.send_message(f"`✅ Accès accordé : {membre} → {salon.mention}`", ephemeral=False)
        except discord.Forbidden:
            await interaction.response.send_message("`❌ Je n'ai pas la permission de modifier ce salon.`", ephemeral=False)

    @discord.app_commands.command(name="bypass_del", description="Retirer l'accès à un salon à un membre")
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    async def bypass_del(self, interaction: discord.Interaction, membre: discord.Member, salon: discord.TextChannel):
        # Vérifier qu’il y a bien une permission personnalisée
        overwrites = salon.overwrites_for(membre)
        if overwrites.read_messages is not True:
            await interaction.response.send_message(f"`⚠️ {membre} n'a pas d'accès personnalisé à {salon.mention}.`", ephemeral=False)
            return

        # Retirer l’accès (reset la permission)
        try:
            await salon.set_permissions(membre, overwrite=None)  # supprime la règle personnalisée
            await interaction.response.send_message(f"`✅ Accès retiré : {membre} ← {salon.mention}`", ephemeral=False)
        except discord.Forbidden:
            await interaction.response.send_message("`❌ Je n'ai pas la permission de modifier ce salon.`", ephemeral=False)

async def setup(bot):
    await bot.add_cog(BypassCog(bot))