import discord
from discord.ext import commands
import re

class SayModal(discord.ui.Modal, title="📢 Envoyer un message"):
    def __init__(self):
        super().__init__()
        self.message_input = discord.ui.TextInput(
            label="Message à envoyer",
            style=discord.TextStyle.paragraph,
            placeholder="Tapez ici...\nUtilisez **gras**, *italique*, `code`, etc.",
            required=True,
            max_length=2000
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.channel.send(self.message_input.value)
        await interaction.response.send_message("`✅ Message envoyé.`", ephemeral=True)

class SayEdit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="say", description="Envoyer un message via interface")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SayModal())

    @discord.app_commands.command(name="sayedit", description="Modifier un message envoyé par /say")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    async def sayedit(self, interaction: discord.Interaction, lien: str, *, nouveau_message: str):
        match = re.search(r'/(\d+)$', lien)
        if not match:
            await interaction.response.send_message("`❌ Lien de message invalide.`", ephemeral=True)
            return

        message_id = int(match.group(1))
        try:
            message = await interaction.channel.fetch_message(message_id)
        except:
            await interaction.response.send_message("`❌ Message introuvable.`", ephemeral=True)
            return

        if message.author.id != self.bot.user.id:
            await interaction.response.send_message("`⚠️ Ce message n'a pas été envoyé par /say.`", ephemeral=True)
            return

        await message.edit(content=nouveau_message)
        await interaction.response.send_message("`✅ Message mis à jour.`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SayEdit(bot))