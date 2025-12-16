import discord
from discord.ext import commands
import re

class SayModal(discord.ui.Modal):
    def __init__(self, title: str, initial_content: str = ""):
        super().__init__(title=title)
        self.message_input = discord.ui.TextInput(
            label="Message à envoyer",
            style=discord.TextStyle.paragraph,
            placeholder="Tapez ici...\nUtilisez **gras**, *italique*, `code`, etc.",
            default=initial_content,  # ← Le message actuel est pré-rempli
            required=True,
            max_length=2000
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        # À redéfinir dans les sous-classes si besoin
        pass

class SaySendModal(SayModal):
    def __init__(self):
        super().__init__(title="📢 Envoyer un message")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.channel.send(self.message_input.value)
        await interaction.response.send_message("`✅ Message envoyé.`", ephemeral=True)

class SayEditModal(SayModal):
    def __init__(self, message_to_edit: discord.Message):
        self.message_to_edit = message_to_edit
        super().__init__(
            title="✏️ Modifier un message",
            initial_content=message_to_edit.content
        )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.message_to_edit.edit(content=self.message_input.value)
            await interaction.response.send_message("`✅ Message mis à jour.`", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"`❌ Erreur : {e}`", ephemeral=True)

class SayCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="say", description="Envoyer un message via interface")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SaySendModal())

    @discord.app_commands.command(name="sayedit", description="Modifier un message envoyé par /say")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    async def sayedit(self, interaction: discord.Interaction, lien: str):
        # Extraire l'ID du message
        match = re.search(r'/(\d+)$', lien)
        if not match:
            await interaction.response.send_message("`❌ Lien de message invalide.`", ephemeral=True)
            return

        message_id = int(match.group(1))
        try:
            message = await interaction.channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.response.send_message("`❌ Message introuvable.`", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message("`❌ Je ne peux pas accéder à ce message.`", ephemeral=True)
            return

        # Vérifier que le message vient du bot
        if message.author.id != self.bot.user.id:
            await interaction.response.send_message("`⚠️ Ce message n’a pas été envoyé par /say.`", ephemeral=True)
            return

        # Ouvrir la modale avec le contenu existant
        modal = SayEditModal(message)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(SayCommands(bot))