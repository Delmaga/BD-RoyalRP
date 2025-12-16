# cogs/ticket.py
import discord
from discord.ext import commands
import aiosqlite
import re
from datetime import datetime

# ---------- BOUTON CLOSE ----------
class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="CloseOperation", style=discord.ButtonStyle.red, emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("`❌ Vous n'avez pas la permission de fermer ce ticket.`", ephemeral=True)
            return

        await interaction.channel.delete(reason="Ticket fermé par un modérateur")

# ---------- MENU CATÉGORIES ----------
class TicketCategorySelect(discord.ui.Select):
    def __init__(self, categories, guild_id, ping_role_id):
        self.guild_id = guild_id
        self.ping_role_id = ping_role_id
        options = [
            discord.SelectOption(label=cat, value=cat)
            for cat in categories
        ]
        if not options:
            options = [discord.SelectOption(label="Aucune catégorie", value="none")]
        super().__init__(placeholder="Sélectionnez une catégorie", options=options)

    async def callback(self, interaction: discord.Interaction):
        category_name = self.values[0]
        if category_name == "none":
            await interaction.response.send_message("`❌ Aucune catégorie disponible.`", ephemeral=True)
            return

        # Créer le salon
        guild = interaction.guild
        member = interaction.user

        # Nom du salon : "Catégorie-ID"
        safe_name = re.sub(r'[^\w\- ]', '', category_name)[:20]
        channel_name = f"{safe_name}-{member.id}"

        # Vérifier si un ticket existe déjà
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(f"`⚠️ Vous avez déjà un ticket ouvert : {existing.mention}`", ephemeral=True)
            return

        # Permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Récupérer le rôle ping
        ping_role = None
        if self.ping_role_id:
            ping_role = guild.get_role(int(self.ping_role_id))

        # Créer le salon
        channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            reason=f"Ticket créé par {member}"
        )

        # Formater la date
        now = datetime.now().strftime("%A %d %B à %Hh%M")

        # Message de ticket
        embed = discord.Embed(
            description=(
                f"***Ticket - Royal RP***\n"
                f"***----------------------------------------***\n"
                f"{ping_role.mention if ping_role else '@Staff'}\n"
                f"***Nom :*** {member.mention}\n"
                f"***Catégories :*** `{category_name}`\n"
                f"***Le :*** `{now}`\n\n"
                f"Un Staff vous prendra en charge dans les plus bref délais .\n"
                f"Veuillez nous ***détailler votre demande***, afin que nous puissions vous répondre le mieux possible.\n"
                f"Délais possible entre ***24-48h.***"
            ),
            color=0x5865F2
        )
        view = CloseTicketButton()
        await channel.send(embed=embed, view=view)

        await interaction.response.send_message(f"`✅ Ticket créé : {channel.mention}`", ephemeral=True)

# ---------- COMMANDE /ticket create ----------
class TicketCreateView(discord.ui.View):
    def __init__(self, categories, guild_id, ping_role_id):
        super().__init__(timeout=180)
        self.add_item(TicketCategorySelect(categories, guild_id, ping_role_id))

# ---------- COG PRINCIPAL ----------
class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="ticket", description="Ouvrir un ticket")
    async def ticket_create(self, interaction: discord.Interaction):
        # Récupérer les catégories
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT name FROM ticket_categories WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            categories = [row[0] async for row in cursor]

        if not categories:
            await interaction.response.send_message("`❌ Aucune catégorie de ticket configurée. Un admin doit utiliser /ticket add-categorie.`", ephemeral=True)
            return

        # Récupérer le rôle ping
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT ping_role_id FROM ticket_config WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            row = await cursor.fetchone()
            ping_role_id = row[0] if row else None

        view = TicketCreateView(categories, str(interaction.guild.id), ping_role_id)
        embed = discord.Embed(
            title="***Ticket - Royal RP***",
            description=(
                "Sélectionnez la catégorie dont vous avez besoin.\n"
                "Tout ***troll*** ou ***Irrespect*** sera suivie d'un ban.\n"
                "Un Staff vous répondra le plus rapidement possible\n"
                "Délais possible entre ***24-48h***"
            ),
            color=0x5865F2
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.app_commands.command(name="ticket_ping", description="Définir le rôle à ping dans les tickets")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ticket_ping(self, interaction: discord.Interaction, role: discord.Role):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO ticket_config (guild_id, ping_role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET ping_role_id = excluded.ping_role_id
            """, (str(interaction.guild.id), str(role.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ Rôle de ping défini : {role.name}`", ephemeral=True)

    @discord.app_commands.command(name="ticket_add_categorie", description="Ajouter une catégorie de ticket")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ticket_add_categorie(self, interaction: discord.Interaction, nom: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "INSERT INTO ticket_categories (guild_id, name) VALUES (?, ?)",
                (str(interaction.guild.id), nom)
            )
            await db.commit()
        await interaction.response.send_message(f"`✅ Catégorie ajoutée : {nom}`", ephemeral=True)

    @discord.app_commands.command(name="ticket_del_categorie", description="Supprimer une catégorie de ticket")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ticket_del_categorie(self, interaction: discord.Interaction, nom: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "DELETE FROM ticket_categories WHERE guild_id = ? AND name = ?",
                (str(interaction.guild.id), nom)
            )
            await db.commit()
        await interaction.response.send_message(f"`✅ Catégorie supprimée : {nom}`", ephemeral=True)

    @discord.app_commands.command(name="ticket_edit_categorie", description="Modifier le nom d'une catégorie")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ticket_edit_categorie(self, interaction: discord.Interaction, ancien: str, nouveau: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                UPDATE ticket_categories
                SET name = ?
                WHERE guild_id = ? AND name = ?
            """, (nouveau, str(interaction.guild.id), ancien))
            await db.commit()
        await interaction.response.send_message(f"`✅ Catégorie renommée : {ancien} → {nouveau}`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TicketCog(bot))