import discord
from discord.ext import commands
import aiosqlite
import time

# ========== VUE : Menu staff + Boutons étoiles ==========
class AvisView(discord.ui.View):
    def __init__(self, staff_members, guild_id):
        super().__init__(timeout=180)
        self.selected_staff = None
        self.stars = 0.0
        self.guild_id = guild_id

        # Menu déroulant : staff
        options = [
            discord.SelectOption(label=str(m), value=str(m.id))
            for m in staff_members[:24]
        ]
        if not options:
            return

        self.staff_select = discord.ui.Select(
            placeholder="👤 Quel staff vous a aidé ?",
            options=options
        )
        self.staff_select.callback = self.on_staff_select
        self.add_item(self.staff_select)

        # Ligne d'étoiles : 0.5, 1, 1.5, ..., 5
        star_values = [0.5] + list(range(1, 6))
        for i, stars in enumerate(star_values):
            btn = discord.ui.Button(
                label=f"{stars}⭐",
                style=discord.ButtonStyle.secondary,
                row=1
            )
            btn.callback = self.make_star_callback(stars)
            self.add_item(btn)

    async def on_staff_select(self, interaction: discord.Interaction):
        self.selected_staff = interaction.guild.get_member(int(self.staff_select.values[0]))
        await interaction.response.send_message("\`✅ Staff sélectionné.\`", ephemeral=True)

    def make_star_callback(self, stars):
        async def callback(interaction: discord.Interaction):
            self.stars = stars
            if not self.selected_staff:
                await interaction.response.send_message("\`❌ Veuillez d'abord choisir un staff.\`", ephemeral=True)
                return
            modal = AvisCommentModal(self.selected_staff, self.stars, self.guild_id)
            await interaction.response.send_modal(modal)
        return callback

# ========== MODAL : Commentaire ==========
class AvisCommentModal(discord.ui.Modal, title="✍️ Votre commentaire"):
    def __init__(self, staff: discord.Member, stars: float, guild_id: int):
        super().__init__()
        self.staff = staff
        self.stars = stars
        self.guild_id = guild_id

        self.comment = discord.ui.TextInput(
            label="Commentaire",
            style=discord.TextStyle.paragraph,
            placeholder="Décrivez votre expérience avec ce membre du staff...",
            required=True,
            max_length=500
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        comment = self.comment.value

        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "INSERT INTO avis (user_id, staff_id, content, stars, guild_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (str(user.id), str(self.staff.id), comment, self.stars, str(self.guild_id), int(time.time()))
            )
            await db.commit()

        await interaction.response.send_message(
            f"\`⭐ Merci ! Votre avis ({self.stars} étoiles) sur {self.staff} a été enregistré.\`",
            ephemeral=True
        )

# ========== COG PRINCIPAL ==========
class AvisStaff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- /avis (accessible à TOUS) ---
    @discord.app_commands.command(name="avis", description="Donner un avis sur un membre du staff")
    async def avis(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id

        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute("SELECT staff_role_id FROM avis_config WHERE guild_id = ?", (str(guild_id),))
            row = await cursor.fetchone()

        if not row or not row[0]:
            await interaction.response.send_message(
                "\`⚙️ Le rôle staff n'a pas été défini. Un admin doit utiliser /avis role.\`",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(int(row[0]))
        if not role:
            await interaction.response.send_message("\`❌ Rôle staff introuvable.\`", ephemeral=True)
            return

        staff_members = [m for m in role.members if not m.bot]
        if not staff_members:
            await interaction.response.send_message("\`📭 Aucun staff disponible pour les avis.\`", ephemeral=True)
            return

        view = AvisView(staff_members, guild_id)
        if not view.children:
            await interaction.response.send_message("\`📭 Aucun staff à évaluer.\`", ephemeral=True)
            return

        embed = discord.Embed(
            title="⭐ Évaluez le staff",
            description="Sélectionnez un membre du staff, donnez des étoiles, puis écrivez un commentaire.",
            color=0xF1C40F
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # --- /avis role (réservé aux admins) ---
    @discord.app_commands.command(name="avis role", description="Définir le rôle utilisé pour les avis staff")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def avis_role(self, interaction: discord.Interaction, role: discord.Role):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO avis_config (guild_id, staff_role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET staff_role_id = ?
            """, (str(interaction.guild.id), str(role.id), str(role.id)))
            await db.commit()

        await interaction.response.send_message(
            f"\`✅ Le rôle staff est maintenant : {role.name}\`",
            ephemeral=True
        )

    # --- /avis list <staff> (accessible à TOUS) ---
    @discord.app_commands.command(name="avis list", description="Voir tous les avis reçus par un membre du staff")
    async def avis_list(self, interaction: discord.Interaction, staff: discord.Member):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT user_id, stars, content, timestamp FROM avis WHERE staff_id = ? AND guild_id = ? ORDER BY timestamp DESC",
                (str(staff.id), str(interaction.guild.id))
            )
            avis_list = await cursor.fetchall()

        if not avis_list:
            await interaction.response.send_message(
                f"\`📭 Aucun avis trouvé pour {staff}.\`",
                ephemeral=False
            )
            return

        # Calculer la moyenne
        avg = sum(row[1] for row in avis_list) / len(avis_list)

        lines = [f"\`⭐ Avis pour {staff} — Moyenne : {avg:.1f}/5.0\`"]
        for user_id, stars, content, _ in avis_list[:10]:  # limiter à 10
            lines.append(f"\n\`• {stars}⭐ par <@{user_id}>\`\n\`  \"{content}\"\`")

        await interaction.response.send_message("\n".join(lines), ephemeral=False)

async def setup(bot):
    await bot.add_cog(AvisStaff(bot))