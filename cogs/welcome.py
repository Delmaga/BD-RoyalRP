# cogs/welcome.py
import discord
from discord.ext import commands
import aiosqlite
import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Chemin de ton fond 1024x500 en JPG
BG_PATH = "assets/welcome_bg.jpg"

class WelcomeConfigModal(discord.ui.Modal, title="🛠️ Salon de bienvenue"):
    def __init__(self, guild_id: str):
        super().__init__()
        self.guild_id = guild_id
        self.channel_input = discord.ui.TextInput(
            label="ID du salon",
            placeholder="Ex: 123456789012345678",
            max_length=30
        )
        self.add_item(self.channel_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel_id = self.channel_input.value.strip()
        if not channel_id.isdigit():
            await interaction.response.send_message("`❌ ID invalide.`", ephemeral=True)
            return
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("`❌ Salon introuvable.`", ephemeral=True)
            return

        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO welcome_config (guild_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """, (self.guild_id, channel_id))
            await db.commit()

        await interaction.response.send_message(f"`✅ Salon défini : {channel.mention}`", ephemeral=True)

def generate_welcome_image(member_name: str, avatar_bytes: bytes) -> io.BytesIO:
    """Génère une image avec fond 1024x500, avatar + TEXTE TRÈS GRAND."""
    if not os.path.exists(BG_PATH):
        raise FileNotFoundError("Fichier assets/welcome_bg.jpg manquant")

    # Charger le fond
    bg = Image.open(BG_PATH).convert("RGB")
    
    # Charger l'avatar
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((200, 200), Image.LANCZOS)

    # Masque circulaire
    mask = Image.new("L", (200, 200), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 200, 200), fill=255)
    avatar.putalpha(mask)

    # Positionner l'avatar
    x_avatar = (bg.width - 200) // 2
    y_avatar = 150
    bg_rgba = bg.convert("RGBA")
    bg_rgba.paste(avatar, (x_avatar, y_avatar), avatar)

    # TEXTE AGRANDI (72pt) — centré en bas
    draw = ImageDraw.Draw(bg_rgba)
    text = f"{member_name.upper()}. A REJOINT K-LAND"

    try:
        font = ImageFont.truetype("assets/arial.ttf", 72)
    except:
        # Police de secours (moins jolie mais fonctionnelle)
        font = ImageFont.load_default()
        # Forcer une taille plus grande avec load_default
        # (optionnel, mais on garde 72pt pour cohérence visuelle si arial est absent)

    # Calcul de la largeur pour centrer
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x_text = (bg.width - text_width) // 2
    y_text = 430  # Position basse, bien visible

    # Contour noir épais + texte or
    draw.text((x_text - 4, y_text - 4), text, fill="black", font=font)
    draw.text((x_text + 4, y_text + 4), text, fill="black", font=font)
    draw.text((x_text, y_text), text, fill="gold", font=font)

    # Convertir en RGB pour sauvegarder
    final_image = bg_rgba.convert("RGB")

    # Exporter en PNG (qualité texte)
    buffer = io.BytesIO()
    final_image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT channel_id, role_id FROM welcome_config WHERE guild_id = ?",
                (str(member.guild.id),)
            )
            row = await cursor.fetchone()

        if not row or not row[0]:
            return

        channel_id, role_id = row
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return

        try:
            avatar_url = member.display_avatar.replace(size=512).url
            async with self.bot.session.get(avatar_url) as resp:
                avatar_data = await resp.read()
            image_buffer = generate_welcome_image(member.name, avatar_data)
            file = discord.File(image_buffer, filename="welcome.png")
            await channel.send(file=file)
        except Exception:
            await channel.send(f"`⚙️ Bienvenue {member.mention} !`")

        # Attribution du rôle
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role and role < member.guild.me.top_role:
                try:
                    await member.add_roles(role, reason="Rôle de bienvenue")
                except:
                    pass

    @discord.app_commands.command(name="welcome", description="Configurer le salon de bienvenue")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def welcome(self, interaction: discord.Interaction):
        modal = WelcomeConfigModal(str(interaction.guild.id))
        await interaction.response.send_modal(modal)

    @discord.app_commands.command(name="welcome_role", description="Définir le rôle à l’arrivée")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def welcome_role(self, interaction: discord.Interaction, role: discord.Role):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO welcome_config (guild_id, role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id
            """, (str(interaction.guild.id), str(role.id)))
            await db.commit()
        await interaction.response.send_message(f"`✅ Rôle défini : {role.name}`", ephemeral=True)

    @discord.app_commands.command(name="welcome_test", description="Tester l’image de bienvenue")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def welcome_test(self, interaction: discord.Interaction):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT channel_id FROM welcome_config WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            row = await cursor.fetchone()

        if not row or not row[0]:
            await interaction.response.send_message("`❌ Configurez /welcome d’abord.`", ephemeral=True)
            return

        channel = interaction.guild.get_channel(int(row[0]))
        if not channel:
            await interaction.response.send_message("`❌ Salon introuvable.`", ephemeral=True)
            return

        try:
            avatar_url = interaction.user.display_avatar.replace(size=512).url
            async with self.bot.session.get(avatar_url) as resp:
                avatar_data = await resp.read()
            image_buffer = generate_welcome_image(interaction.user.name, avatar_data)
            file = discord.File(image_buffer, filename="welcome_test.png")
            await channel.send(file=file)
            await interaction.response.send_message("`✅ Test envoyé.`", ephemeral=True)
        except Exception:
            await channel.send("`❌ Erreur lors de la génération de l’image.`")
            await interaction.response.send_message("`❌ Échec du test.`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))