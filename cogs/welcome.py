# cogs/welcome.py
import discord
from discord.ext import commands
import aiosqlite

class WelcomeConfigModal(discord.ui.Modal, title="🛠️ Configuration du message de bienvenue"):
    def __init__(self, guild_id: str):
        super().__init__()
        self.guild_id = guild_id

        # Récupérer les valeurs actuelles depuis la base (optionnel, mais utile)
        # → On ne le fait pas ici pour éviter async dans __init__
        # → On utilise des valeurs par défaut simples

        self.channel_input = discord.ui.TextInput(
            label="ID du salon de bienvenue",
            placeholder="Ex: 123456789012345678",
            max_length=30
        )
        self.title_input = discord.ui.TextInput(
            label="Titre",
            default="Bienvenue !",
            max_length=100
        )
        self.description_input = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            default="Bienvenue sur le serveur, {user} !",
            max_length=500,
            placeholder="Utilisez {user} pour mentionner le nouveau membre"
        )
        self.add_item(self.channel_input)
        self.add_item(self.title_input)
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel_id = self.channel_input.value.strip()
        title = self.title_input.value
        description = self.description_input.value

        # Valider que c'est un ID numérique
        if not channel_id.isdigit():
            await interaction.response.send_message("`❌ L'ID du salon doit être un nombre.`", ephemeral=True)
            return

        # Vérifier que le salon existe
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("`❌ Salon introuvable. Vérifiez l'ID.`", ephemeral=True)
            return

        # Sauvegarder
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO welcome_config (guild_id, channel_id, title, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    title = excluded.title,
                    description = excluded.description
            """, (self.guild_id, channel_id, title, description))
            await db.commit()

        await interaction.response.send_message(f"`✅ Bienvenue configuré dans {channel.mention}.`", ephemeral=True)

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT channel_id, role_id, title, description FROM welcome_config WHERE guild_id = ?",
                (str(guild.id),)
            )
            row = await cursor.fetchone()

        if not row or not row[0]:
            return  # Pas configuré

        channel_id, role_id, title, description = row

        # Envoyer le message
        channel = guild.get_channel(int(channel_id))
        if channel:
            content = description.replace("{user}", member.mention)
            embed = discord.Embed(title=title, description=content, color=0x5865F2)
            embed.set_thumbnail(url=member.display_avatar.url)
            try:
                await channel.send(embed=embed)
            except:
                pass

        # Donner le rôle
        if role_id:
            role = guild.get_role(int(role_id))
            if role and role < guild.me.top_role:
                try:
                    await member.add_roles(role)
                except:
                    pass

    @discord.app_commands.command(name="welcome", description="Configurer le salon, titre et description du message de bienvenue")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def welcome(self, interaction: discord.Interaction):
        modal = WelcomeConfigModal(str(interaction.guild.id))
        await interaction.response.send_modal(modal)

    @discord.app_commands.command(name="welcome_role", description="Définir le rôle à donner aux nouveaux membres")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def welcome_role(self, interaction: discord.Interaction, role: discord.Role):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO welcome_config (guild_id, role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id
            """, (str(interaction.guild.id), str(role.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ Rôle de bienvenue défini : {role.name}`", ephemeral=True)

    @discord.app_commands.command(name="welcome_test", description="Tester le message de bienvenue")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def welcome_test(self, interaction: discord.Interaction):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT channel_id, title, description FROM welcome_config WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            row = await cursor.fetchone()

        if not row or not row[0]:
            await interaction.response.send_message("`❌ Le salon de bienvenue n'est pas configuré. Utilisez /welcome.`", ephemeral=True)
            return

        channel_id, title, description = row
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("`❌ Salon de bienvenue supprimé ou inaccessible.`", ephemeral=True)
            return

        content = description.replace("{user}", interaction.user.mention)
        embed = discord.Embed(title=title, description=content, color=0x5865F2)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await channel.send(embed=embed)
        await interaction.response.send_message("`✅ Test envoyé avec succès.`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))