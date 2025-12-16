import discord
from discord.ext import commands
import aiosqlite
import time

class AvisModal(discord.ui.Modal, title="⭐ Donner un avis sur un staff"):
    def __init__(self, staff: discord.Member, channel: discord.TextChannel):
        super().__init__()
        self.staff = staff
        self.channel = channel

        self.stars = discord.ui.TextInput(
            label="Étoiles (0.5 à 5.0)",
            placeholder="Ex: 4.5",
            max_length=3
        )
        self.comment = discord.ui.TextInput(
            label="Commentaire",
            style=discord.TextStyle.paragraph,
            placeholder="Décrivez votre expérience...",
            required=True,
            max_length=500
        )
        self.add_item(self.stars)
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        # Validation des étoiles
        try:
            stars = float(self.stars.value)
            if not (0.5 <= stars <= 5.0):
                raise ValueError
        except:
            await interaction.response.send_message("`❌ Étoiles : nombre entre 0.5 et 5.0 (ex: 4.5)`", ephemeral=True)
            return

        # Sauvegarde en base (optionnel, mais utile pour stats futures)
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "INSERT INTO avis (user_id, staff_id, content, stars, guild_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (str(interaction.user.id), str(self.staff.id), self.comment.value, stars, str(interaction.guild.id), int(time.time()))
            )
            await db.commit()

        # 🔹 Génération du message visuel dans le salon
        # Créer un embed sans couleur de bordure visible (style épuré)
        embed = discord.Embed(
            description=f"`Commentaire : \"{self.comment.value}\"`",
            color=0x2F3136  # Couleur fond Discord → donne l'impression "sans bordure"
        )

        # Auteur avec avatar (comme demandé)
        embed.set_author(
            name=str(interaction.user),
            icon_url=interaction.user.display_avatar.url
        )

        # Pied avec staff + étoiles
        full_stars = int(stars)
        has_half = stars % 1 >= 0.5
        empty_stars = 5 - full_stars - (1 if has_half else 0)
        star_line = "⭐" * full_stars + ("🌟" if has_half else "") + "☆" * empty_stars
        embed.set_footer(text=f"Staff : {self.staff} • Avis : {stars}/5 • {star_line}")

        # Envoi
        try:
            await self.channel.send(embed=embed)
            await interaction.response.send_message("`✅ Votre avis a été envoyé.`", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("`❌ Je ne peux pas écrire dans le salon d'avis.`", ephemeral=True)

class AvisStaff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="avis", description="Donner un avis sur un membre du staff")
    async def avis(self, interaction: discord.Interaction, staff: discord.Member):
        # Récupérer config
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT staff_role_id, avis_channel_id FROM avis_config WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            row = await cursor.fetchone()

        if not row or not row[0]:
            await interaction.response.send_message("`⚙️ Le rôle staff n'est pas configuré. Utilisez /avis_role.`", ephemeral=True)
            return

        staff_role = interaction.guild.get_role(int(row[0]))
        if not staff_role or staff not in staff_role.members:
            await interaction.response.send_message("`❌ Ce membre n'est pas du staff.`", ephemeral=True)
            return

        channel_id = row[1]
        if not channel_id:
            await interaction.response.send_message("`⚙️ Le salon d'avis n'est pas configuré. Utilisez /avis_channel.`", ephemeral=True)
            return

        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("`❌ Salon d'avis introuvable.`", ephemeral=True)
            return

        await interaction.response.send_modal(AvisModal(staff, channel))

    @discord.app_commands.command(name="avis_role", description="Définir le rôle staff")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def avis_role(self, interaction: discord.Interaction, role: discord.Role):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO avis_config (guild_id, staff_role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET staff_role_id = excluded.staff_role_id
            """, (str(interaction.guild.id), str(role.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ Rôle staff défini : {role.name}`", ephemeral=True)

    @discord.app_commands.command(name="avis_channel", description="Définir le salon pour les avis")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def avis_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO avis_config (guild_id, avis_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET avis_channel_id = excluded.avis_channel_id
            """, (str(interaction.guild.id), str(channel.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ Salon d'avis défini : {channel.mention}`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AvisStaff(bot))