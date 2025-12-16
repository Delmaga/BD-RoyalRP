import discord
from discord.ext import commands
import aiosqlite
import time

class AvisModal(discord.ui.Modal, title="⭐ Donner un avis sur un staff"):
    def __init__(self, staff: discord.Member):
        super().__init__()
        self.staff = staff

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
        try:
            stars = float(self.stars.value)
            if not (0.5 <= stars <= 5.0):
                raise ValueError
        except:
            await interaction.response.send_message("`❌ Étoiles : nombre entre 0.5 et 5.0 (ex: 4.5)`", ephemeral=True)
            return

        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "INSERT INTO avis (user_id, staff_id, content, stars, guild_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (str(interaction.user.id), str(self.staff.id), self.comment.value, stars, str(interaction.guild.id), int(time.time()))
            )
            await db.commit()

        await interaction.response.send_message(
            f"`⭐ Merci ! Votre avis ({stars} étoiles) sur {self.staff} a été enregistré.`",
            ephemeral=True
        )

class AvisStaff(commands.Cog):
    @discord.app_commands.command(name="avis", description="Donner un avis sur un membre du staff")
    async def avis(self, interaction: discord.Interaction, staff: discord.Member):
        await interaction.response.send_modal(AvisModal(staff))

    @discord.app_commands.command(name="avis_role", description="Définir le rôle staff pour les avis")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def avis_role(self, interaction: discord.Interaction, role: discord.Role):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO avis_config (guild_id, staff_role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET staff_role_id = ?
            """, (str(interaction.guild.id), str(role.id), str(role.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ Rôle staff défini : {role.name}`", ephemeral=True)

    @discord.app_commands.command(name="avis_list", description="Voir les avis d'un membre du staff")
    async def avis_list(self, interaction: discord.Interaction, staff: discord.Member):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT stars, content, user_id FROM avis WHERE staff_id = ? AND guild_id = ? ORDER BY timestamp DESC LIMIT 10",
                (str(staff.id), str(interaction.guild.id))
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message(f"`📭 Aucun avis pour {staff}.`", ephemeral=False)
            return

        avg = sum(r[0] for r in rows) / len(rows)
        lines = [f"`⭐ Avis pour {staff} — Moyenne : {avg:.1f}/5.0`"]
        for stars, content, user_id in rows:
            lines.append(f"`• {stars}⭐ par <@{user_id}> : \"{content}\"`")
        await interaction.response.send_message("\n".join(lines), ephemeral=False)

async def setup(bot):
    await bot.add_cog(AvisStaff(bot))