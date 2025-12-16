import discord
from discord.ext import commands
import aiosqlite
import time

# --- Modal : Raison ---
class ReasonModal(discord.ui.Modal, title="📝 Raison de la sanction"):
    def __init__(self, member: discord.Member, duration: str, action: str):
        super().__init__()
        self.member = member
        self.duration = duration
        self.action = action

        self.reason = discord.ui.TextInput(
            label="Raison",
            style=discord.TextStyle.long,
            placeholder="Ex: Spam, insultes, tentative de raid...",
            required=True,
            max_length=300
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        member = self.member
        mod = interaction.user

        # Appliquer l'action
        if self.action == "ban":
            try:
                await interaction.guild.ban(member, reason=reason)
                msg = f"\`✅ {member} banni ({self.duration})\`"
            except Exception as e:
                await interaction.response.send_message(f"\`❌ Erreur ban : {e}\`", ephemeral=True)
                return
        elif self.action == "mute":
            # À compléter avec rôle "Muted"
            msg = f"\`🔇 {member} muté ({self.duration})\`"
        else:
            await interaction.response.send_message("\`⚠️ Action inconnue.\`", ephemeral=True)
            return

        # Log en DB
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO moderation (user_id, mod_id, action, reason, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(member.id), str(mod.id), self.action, reason, self.duration, int(time.time())))
            await db.commit()

        await interaction.response.send_message(msg, ephemeral=True)

# --- Select : Membres ---
class MemberSelect(discord.ui.Select):
    def __init__(self, members):
        options = [
            discord.SelectOption(label=str(m), value=str(m.id))
            for m in members[:24]  # 24 + 1 bouton = 25 max
        ]
        super().__init__(placeholder="👤 Choisissez un membre", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_member_id = int(self.values[0])
        self.disabled = True
        await interaction.response.edit_message(view=self.view)

# --- Select : Unité ---
class TimeUnitSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Secondes", value="s", emoji="⏱️"),
            discord.SelectOption(label="Minutes", value="m", emoji="🕒"),
            discord.SelectOption(label="Heures", value="h", emoji="🕖"),
            discord.SelectOption(label="Jours", value="d", emoji="📅"),
        ]
        super().__init__(placeholder="⏳ Unité", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.time_unit = self.values[0]
        self.disabled = True
        await interaction.response.edit_message(view=self.view)

# --- Modal : Quantité ---
class TimeAmountModal(discord.ui.Modal, title="🔢 Durée"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.amount = discord.ui.TextInput(label="Valeur (ex: 30)", max_length=4)
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.amount.value)
            if val <= 0:
                raise ValueError
            self.view.time_amount = val
            await interaction.response.send_message("\`✅ Durée enregistrée.\`", ephemeral=True)
        except:
            await interaction.response.send_message("\`❌ Nombre invalide.\`", ephemeral=True)

# --- Vue principale ---
class ModerationView(discord.ui.View):
    def __init__(self, members, action):
        super().__init__(timeout=180)
        self.selected_member_id = None
        self.time_amount = None
        self.time_unit = None
        self.action = action

        self.add_item(MemberSelect(members))
        self.add_item(TimeUnitSelect())

    @discord.ui.button(label="🔢 Entrer la durée", style=discord.ButtonStyle.grey, row=2)
    async def input_time(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(TimeAmountModal(self))

    @discord.ui.button(label="✅ Appliquer", style=discord.ButtonStyle.red, row=2)
    async def apply(self, interaction: discord.Interaction, _):
        if not all([self.selected_member_id, self.time_amount, self.time_unit]):
            await interaction.response.send_message("\`❌ Tous les champs requis.\`", ephemeral=True)
            return

        member = interaction.guild.get_member(self.selected_member_id)
        if not member:
            await interaction.response.send_message("\`❌ Membre introuvable.\`", ephemeral=True)
            return

        duration = f"{self.time_amount}{self.time_unit}"
        await interaction.response.send_modal(ReasonModal(member, duration, self.action))

# --- Commande /modo ---
class ModerationUI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="modo", description="Interface visuelle de modération")
    @discord.app_commands.checks.has_permissions(ban_members=True)
    async def modo(self, interaction: discord.Interaction):
        members = [m for m in interaction.guild.members if not m.bot and m != interaction.user]
        if not members:
            await interaction.response.send_message("\`📭 Aucun membre à sanctionner.\`", ephemeral=True)
            return

        view = ModerationView(members, action="ban")
        embed = discord.Embed(
            title="🛡️ Interface de Modération",
            description="Sélectionnez un membre, une durée, puis appliquez une sanction.",
            color=0xFF5555
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationUI(bot))