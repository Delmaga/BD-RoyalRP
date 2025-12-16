import discord
from discord.ext import commands

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
        await interaction.response.send_message("\`✅ Message envoyé.\`", ephemeral=True)

class SayCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="say", description="Envoyer un message via interface")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SayModal())

async def setup(bot):
    await bot.add_cog(SayCommand(bot))