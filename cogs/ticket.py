# cogs/ticket.py
import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime
import re

# ========== BOUTON CLOSE ==========
class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="CloseOperation", style=discord.ButtonStyle.red, emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Vous n'avez pas la permission de fermer ce ticket.", ephemeral=True)
            return
        await interaction.channel.delete(reason="Ticket fermé par un staff")

# ========== MENU DÉROULANT (dans le message permanent) ==========
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
            await interaction.response.send_message("❌ Aucune catégorie disponible.", ephemeral=False)
            return

        guild = interaction.guild
        member = interaction.user

        # --- Récupérer et incrémenter le compteur global ---
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT ticket_counter FROM ticket_config WHERE guild_id = ?",
                (str(guild.id),)
            )
            row = await cursor.fetchone()
            if row:
                ticket_number = row[0]
                await db.execute(
                    "UPDATE ticket_config SET ticket_counter = ? WHERE guild_id = ?",
                    (ticket_number + 1, str(guild.id))
                )
            else:
                ticket_number = 1
                await db.execute(
                    "INSERT INTO ticket_config (guild_id, ticket_counter) VALUES (?, ?)",
                    (str(guild.id), 2)
                )
            await db.commit()

        # --- Nom du salon : "Catégorie-1" ---
        safe_cat = re.sub(r'[^\w\s-]', '', category_name).replace(' ', '-').lower()
        channel_name = f"{safe_cat}-{ticket_number}"

        # --- Permissions ---
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # --- Créer le salon ---
        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)

        # --- Rôle à pinguer ---
        ping_role = None
        if self.ping_role_id:
            ping_role = guild.get_role(int(self.ping_role_id))
        ping_mention = ping_role.mention if ping_role else "@here"

        # --- Date en français ---
        weekdays = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                  "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        now = datetime.now()
        date_str = f"{weekdays[now.weekday()]} {now.day} {months[now.month]} à {now.hour}h{now.minute:02d}"

        # --- MESSAGE EN TEXTE BRUT (pour que le ping marche) ---
        message_content = (
            f"***Ticket - Royal RP***\n"
            f"***----------------------------------------***\n"
            f"{ping_mention}\n"
            f"***Nom :*** {member.mention}\n"
            f"***Catégories :*** `{category_name}`\n"
            f"***Le :*** `{date_str}`\n\n"
            f"Un Staff vous prendra en charge dans les plus bref délais .\n"
            f"Veuillez nous ***détailler votre demande***, afin que nous puissions vous répondre le mieux possible.\n"
            f"Délais possible entre ***24-48h.***"
        )

        view = CloseTicketButton()
        await channel.send(content=message_content, view=view)
        await interaction.response.send_message(f"✅ Ticket créé : {channel.mention}", ephemeral=False)

# ========== VUE PERMANENTE ==========
class TicketPersistentView(discord.ui.View):
    def __init__(self, categories, guild_id, ping_role_id):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect(categories, guild_id, ping_role_id))

# ========== COG ==========
class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Enregistrer la vue persistante (reste active après redémarrage)
        self.bot.add_view(TicketPersistentView([], "", ""))

    @discord.app_commands.command(name="ticket", description="Créer un menu de ticket permanent dans ce salon")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ticket_menu(self, interaction: discord.Interaction):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT name FROM ticket_categories WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            categories = [row[0] async for row in cursor]

        if not categories:
            await interaction.response.send_message("❌ Aucune catégorie. Utilisez `/ticket add-categorie <nom>`.", ephemeral=False)
            return

        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT ping_role_id FROM ticket_config WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            row = await cursor.fetchone()
            ping_role_id = row[0] if row else None

        view = TicketPersistentView(categories, str(interaction.guild.id), ping_role_id)
        message_content = (
            f"***Ticket - Royal RP***\n\n"
            f"Sélectionnez la catégorie dont vous avez besoin.\n"
            f"Tout ***troll*** ou ***Irrespect*** sera suivie d'un ban.\n"
            f"Un Staff vous répondra le plus rapidement possible\n"
            f"Délais possible entre ***24-48h***"
        )
        await interaction.channel.send(content=message_content, view=view)
        await interaction.response.send_message("✅ Menu de ticket permanent créé.", ephemeral=False)

    @discord.app_commands.command(name="ticket_add_categorie", description="Ajouter une catégorie de ticket")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ticket_add_categorie(self, interaction: discord.Interaction, nom: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "INSERT INTO ticket_categories (guild_id, name) VALUES (?, ?)",
                (str(interaction.guild.id), nom)
            )
            await db.commit()
        await interaction.response.send_message(f"✅ Catégorie ajoutée : `{nom}`", ephemeral=False)

    @discord.app_commands.command(name="ticket_del_categorie", description="Supprimer une catégorie")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ticket_del_categorie(self, interaction: discord.Interaction, nom: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "DELETE FROM ticket_categories WHERE guild_id = ? AND name = ?",
                (str(interaction.guild.id), nom)
            )
            await db.commit()
        await interaction.response.send_message(f"✅ Catégorie supprimée : `{nom}`", ephemeral=False)

    @discord.app_commands.command(name="ticket_edit_categorie", description="Renommer une catégorie")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ticket_edit_categorie(self, interaction: discord.Interaction, ancien: str, nouveau: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "UPDATE ticket_categories SET name = ? WHERE guild_id = ? AND name = ?",
                (nouveau, str(interaction.guild.id), ancien)
            )
            await db.commit()
        await interaction.response.send_message(f"✅ Catégorie renommée : `{ancien}` → `{nouveau}`", ephemeral=False)

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
        await interaction.response.send_message(f"✅ Rôle de ping défini : {role.mention}", ephemeral=False)

async def setup(bot):
    await bot.add_cog(TicketCog(bot))