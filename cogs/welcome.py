# cogs/welcome.py
import discord
from discord.ext import commands
import aiosqlite
import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Chemin de l'image de fond (doit exister dans assets/)
BG_PATH = "assets/welcome_bg.png"

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
    """Génère une image de bienvenue sans dépendance externe."""
    if not os.path.exists(BG_PATH):
        raise FileNotFoundError("Fichier assets/welcome_bg.jpg manquant")

    # Charger le fond
    bg = Image.open(BG_PATH).convert("RGBA")
    
    # Charger et recadrer l'avatar en cercle
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((200, 200), Image.LANCZOS)

    mask = Image.new("L", (200, 200), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 200, 200), fill=255)
    avatar.putalpha(mask)

    # Coller l'avatar au centre
    x = (bg.width - 200) // 2
    y = 120
    bg.paste(avatar, (x, y), avatar)

    # Ajouter le texte
    draw = ImageDraw.Draw(bg)
    text = f"{member_name.upper()}. A Rejoin Royal-RP"
    
    # Utiliser la police système ou une police de secours
    try:
        font = ImageFont.truetype("assets/arial.ttf", 48)
    except:
        font = ImageFont.load_default()

    # Centrer le texte
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x_text = (bg.width - text_width) // 2
    y_text = 420

    # Contour + texte principal
    draw.text((x_text - 2, y_text - 2), text, fill="black", font=font)
    draw.text((x_text + 2, y_text + 2), text, fill="black", font=font)
    draw.text((x_text, y_text), text, fill="gold", font=font)

    # Exporter
    buffer = io.BytesIO()
    bg.save(buffer, format="JPG")
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
            # Télécharger l'avatar
            avatar_url = member.display_avatar.replace(size=512).url
            async with self.bot.session.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_data = await resp.read()
                else:
                    raise Exception("Avatar non accessible")
            
            # Générer l'image
            image_buffer = generate_welcome_image(member.name, avatar_data)
            file = discord.File(image_buffer, filename="welcome.jpg")
            await channel.send(file=file)

        except Exception as e:
            # En cas d'erreur, message de secours
            await channel.send(f"`⚙️ Bienvenue {member.mention} ! (Image désactivée)`")

        # Donner le rôle
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
            file = discord.File(image_buffer, filename="welcome_test.jpg")
            await channel.send(file=file)
            await interaction.response.send_message("`✅ Test envoyé.`", ephemeral=True)
        except Exception as e:
            await channel.send("`❌ Erreur : image non générée.`")
            await interaction.response.send_message("`❌ Échec du test.`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))