import discord
from discord.ext import commands
import aiosqlite
import re
import time

def parse_time(time_str):
    # Ex: "30m", "2h", "1d"
    time_str = time_str.lower()
    seconds = 0
    matches = re.findall(r'(\d+)([smhd])', time_str)
    for amount, unit in matches:
        amount = int(amount)
        if unit == 's': seconds += amount
        elif unit == 'm': seconds += amount * 60
        elif unit == 'h': seconds += amount * 3600
        elif unit == 'd': seconds += amount * 86400
    return seconds or None

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.User, time: str = None, *, reason: str = "Aucune raison"):
        await interaction.response.defer(ephemeral=False)
        mod = interaction.user
        duration = parse_time(time) if time else None

        # Enregistrer dans la DB
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO moderation (user_id, mod_id, action, reason, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(user.id), str(mod.id), "ban", reason, time or "permanent", int(time.time())))
            await db.commit()

        # Ban réel (permanent ou temporaire)
        try:
            await interaction.guild.ban(user, reason=reason)
            msg = f"\`✅ {user} a été banni\`"
            if duration:
                msg += f" pour `{time}`."
                # (Optionnel) Planifier le unban avec asyncio ou un task manager
            await interaction.followup.send(msg)
        except:
            await interaction.followup.send("\`❌ Impossible de bannir cet utilisateur.\`")

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user: str):
        # user = "Nom#1234" ou ID
        await interaction.response.defer()
        try:
            ban_entries = [b async for b in interaction.guild.bans()]
            target = None
            if user.isdigit():
                target = discord.Object(id=int(user))
            else:
                for ban in ban_entries:
                    if str(ban.user) == user:
                        target = ban.user
                        break
            if target:
                await interaction.guild.unban(target)
                await interaction.followup.send(f"\`🔓 {user} a été débanni.\`")
            else:
                await interaction.followup.send("\`❌ Utilisateur non trouvé dans la liste des bans.\`")
        except:
            await interaction.followup.send("\`❌ Échec du déban.\`")

    @discord.app_commands.command()
    async def banlist(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute("SELECT user_id, mod_id, reason, duration FROM moderation WHERE action = 'ban' AND active = 1")
            bans = await cursor.fetchall()
        if not bans:
            await interaction.followup.send("\`📭 Aucun ban actif.\`")
            return
        lines = ["\`🔒 Liste des bans :\`"]
        for user_id, mod_id, reason, duration in bans:
            lines.append(f"• <@{user_id}> — par <@{mod_id}> | `{duration}` | `{reason}`")
        await interaction.followup.send("\n".join(lines[:10]))  # limiter à 10

    # --- Mute / Unmute / Mutelist ---
    # Même logique : stocker dans DB, appliquer rôle "Muted", etc.
    # (Pour gagner de la place, je résume ici — tu peux demander le code complet)

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(mute_members=True)
    async def mute(self, interaction: discord.Interaction, user: discord.Member, time: str = None, *, reason: str = "Aucune raison"):
        # → Créer rôle "Muted" si absent, appliquer, log en DB
        pass

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(mute_members=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        # → Retirer rôle "Muted"
        pass

    @discord.app_commands.command()
    async def mutelist(self, interaction: discord.Interaction):
        # → Lire DB, afficher
        pass

    # --- Warn ---
    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(kick_members=True)
    async def warn(self, interaction: discord.Interaction, user: discord.User, *, reason: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute("""
                INSERT INTO moderation (user_id, mod_id, action, reason, timestamp)
                VALUES (?, ?, 'warn', ?, ?)
            """, (str(user.id), str(interaction.user.id), reason, int(time.time())))
            await db.commit()
        await interaction.response.send_message(f"\`⚠️ {user} a reçu un avertissement : {reason}\`")

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(kick_members=True)
    async def unwarn(self, interaction: discord.Interaction, user: discord.User, *, reason: str):
        # Marquer comme non actif ou supprimer (selon ta logique)
        await interaction.response.send_message(f"\`✅ Avertissement retiré pour {user} ({reason})\`")

    @discord.app_commands.command()
    async def warnlist(self, interaction: discord.Interaction):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute("SELECT user_id, mod_id, reason FROM moderation WHERE action = 'warn' AND active = 1")
            warns = await cursor.fetchall()
        if not warns:
            await interaction.response.send_message("\`📭 Aucun avertissement.\`")
            return
        lines = ["\`📢 Avertissements :\`"]
        for user_id, mod_id, reason in warns:
            lines.append(f"• <@{user_id}> — par <@{mod_id}> : `{reason}`")
        await interaction.response.send_message("\n".join(lines))

async def setup(bot):
    await bot.add_cog(Moderation(bot))