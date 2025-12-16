# cogs/moderation.py
import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
from datetime import datetime, timedelta
import re

DATA_DIR = "data"
BANS_FILE = os.path.join(DATA_DIR, "bans.json")
MUTES_FILE = os.path.join(DATA_DIR, "mutes.json")
WARNS_FILE = os.path.join(DATA_DIR, "warns.json")

# Crée le dossier data si inexistant
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(file):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)
        return {}
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def parse_time(time_str):
    """
    Parse une chaîne comme '5s', '10m', '2h', '3D', '1M', '2Y' → timedelta
    """
    total_seconds = 0
    matches = re.findall(r'(\d+)([smhD])', time_str)
    for amount, unit in matches:
        amount = int(amount)
        if unit == 's':
            total_seconds += amount
        elif unit == 'm':
            total_seconds += amount * 60
        elif unit == 'h':
            total_seconds += amount * 3600
        elif unit == 'D':
            total_seconds += amount * 86400
    # Pour les mois/années, on approxime (car pas exact dans timedelta)
    # Mais on les ignore ici pour simplicité et stabilité
    if 'M' in time_str or 'Y' in time_str:
        return None  # On ne gère que s, m, h, D
    return timedelta(seconds=total_seconds) if total_seconds > 0 else None

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_temp_tasks.start()

    def cog_unload(self):
        self.check_temp_tasks.cancel()

    @tasks.loop(seconds=30)
    async def check_temp_tasks(self):
        """Vérifie régulièrement les bannissements et mutes temporaires à lever"""
        # Unban
        bans = load_json(BANS_FILE)
        changed = False
        now = datetime.utcnow().timestamp()
        for guild_id in list(bans.keys()):
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
            for user_id in list(bans[guild_id].keys()):
                data = bans[guild_id][user_id]
                if data["until"] and now >= data["until"]:
                    try:
                        user = discord.Object(id=int(user_id))
                        await guild.unban(user, reason="Durée de ban temporaire expirée")
                    except:
                        pass
                    del bans[guild_id][user_id]
                    changed = True
            if not bans[guild_id]:
                del bans[guild_id]
        if changed:
            save_json(BANS_FILE, bans)

        # Unmute
        mutes = load_json(MUTES_FILE)
        changed = False
        for guild_id in list(mutes.keys()):
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
            for user_id in list(mutes[guild_id].keys()):
                data = mutes[guild_id][user_id]
                if data["until"] and now >= data["until"]:
                    member = guild.get_member(int(user_id))
                    if member:
                        mute_role = discord.utils.get(guild.roles, name="Muted")
                        if mute_role and mute_role in member.roles:
                            await member.remove_roles(mute_role, reason="Durée de mute expirée")
                    del mutes[guild_id][user_id]
                    changed = True
            if not mutes[guild_id]:
                del mutes[guild_id]
        if changed:
            save_json(MUTES_FILE, mutes)

    @commands.Cog.listener()
    async def on_ready(self):
        # Créer le rôle Muted si absent
        for guild in self.bot.guilds:
            if not discord.utils.get(guild.roles, name="Muted"):
                mute_role = await guild.create_role(name="Muted", reason="Créé par Royal Bot")
                for channel in guild.channels:
                    if isinstance(channel, discord.TextChannel):
                        await channel.set_permissions(mute_role, send_messages=False, add_reactions=False)

    def is_moderator():
        async def predicate(ctx):
            return ctx.author.guild_permissions.kick_members or ctx.author.guild_permissions.ban_members
        return commands.check(predicate)

    # === COMMANDES ===

    @commands.command(name="ban")
    @is_moderator()
    async def ban(self, ctx, member: discord.Member, time: str, *, reason: str = "Aucune raison"):
        duration = parse_time(time)
        if duration is None and time.lower() not in ["permanent", "perm", "p"]:
            await ctx.send("`❌` Format de durée invalide. Utilisez : `5s`, `10m`, `2h`, `3D`.")
            return

        if member == ctx.author:
            await ctx.send("`❌` Vous ne pouvez pas vous bannir vous-même.")
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("`❌` Vous ne pouvez pas bannir cet utilisateur (hiérarchie des rôles).")
            return

        # Appliquer le ban
        await member.ban(reason=reason)
        now = datetime.utcnow()

        # Sauvegarder
        bans = load_json(BANS_FILE)
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        if guild_id not in bans:
            bans[guild_id] = {}

        if duration:
            until = (now + duration).timestamp()
            human_time = f"dans {time}"
        else:
            until = None
            human_time = "permanent"

        bans[guild_id][user_id] = {
            "user_name": str(member),
            "moderator": str(ctx.author),
            "reason": reason,
            "banned_at": now.timestamp(),
            "until": until
        }
        save_json(BANS_FILE, bans)

        await ctx.send(f"`✅` {member} a été banni ({human_time}) • **Raison** : {reason}")

    @commands.command(name="unban")
    @is_moderator()
    async def unban(self, ctx, user: str):
        try:
            user_id = int(user) if user.isdigit() else None
            if not user_id:
                # Essayer de trouver par mention ou pseudo (moins fiable pour les bans)
                await ctx.send("`ℹ️` Veuillez fournir l'ID de l'utilisateur à débannir.")
                return

            bans = load_json(BANS_FILE)
            guild_id = str(ctx.guild.id)
            user_str = str(user_id)

            # Supprimer du fichier
            if guild_id in bans and user_str in bans[guild_id]:
                del bans[guild_id][user_str]
                if not bans[guild_id]:
                    del bans[guild_id]
                save_json(BANS_FILE, bans)

            try:
                await ctx.guild.unban(discord.Object(id=user_id))
                await ctx.send(f"`✅` Utilisateur (ID: `{user_id}`) débanni.")
            except discord.NotFound:
                await ctx.send("`⚠️` L'utilisateur n'était pas banni, mais son entrée a été nettoyée.")
        except Exception as e:
            await ctx.send(f"`❌` Erreur : {e}")

    @commands.command(name="banlist")
    @is_moderator()
    async def banlist(self, ctx):
        bans = load_json(BANS_FILE)
        guild_id = str(ctx.guild.id)
        if guild_id not in bans or not bans[guild_id]:
            await ctx.send("`ℹ️` Aucun utilisateur banni.")
            return

        embed = discord.Embed(title="📜 Liste des bannissements", color=0xff5555)
        for user_id, data in bans[guild_id].items():
            user_str = data["user_name"]
            reason = data["reason"]
            banned_at = datetime.fromtimestamp(data["banned_at"]).strftime("%d/%m/%Y %H:%M")
            if data["until"]:
                until = datetime.fromtimestamp(data["until"]).strftime("%d/%m/%Y %H:%M")
                duration = f"jusqu'au {until}"
            else:
                duration = "permanent"
            embed.add_field(
                name=f"{user_str} (ID: {user_id})",
                value=f"**Raison** : {reason}\n**Depuis** : {banned_at}\n**Durée** : {duration}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name="mute")
    @is_moderator()
    async def mute(self, ctx, member: discord.Member, time: str, *, reason: str = "Aucune raison"):
        if member == ctx.author:
            await ctx.send("`❌` Vous ne pouvez pas vous mutez vous-même.")
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("`❌` Vous ne pouvez pas mute cet utilisateur.")
            return

        duration = parse_time(time)
        if duration is None:
            await ctx.send("`❌` Format de durée invalide. Utilisez : `5s`, `10m`, `2h`, `3D`.")
            return

        # Vérifier/obtenir rôle Muted
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role:
            mute_role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                if isinstance(channel, discord.TextChannel):
                    await channel.set_permissions(mute_role, send_messages=False, add_reactions=False)

        await member.add_roles(mute_role, reason=reason)

        # Sauvegarder
        mutes = load_json(MUTES_FILE)
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        if guild_id not in mutes:
            mutes[guild_id] = {}

        until = (datetime.utcnow() + duration).timestamp()
        mutes[guild_id][user_id] = {
            "user_name": str(member),
            "moderator": str(ctx.author),
            "reason": reason,
            "muted_at": datetime.utcnow().timestamp(),
            "until": until
        }
        save_json(MUTES_FILE, mutes)

        human_until = datetime.fromtimestamp(until).strftime("%d/%m/%Y %H:%M")
        await ctx.send(f"`✅` {member} a été mute jusqu'au {human_until} • **Raison** : {reason}")

    @commands.command(name="unmute")
    @is_moderator()
    async def unmute(self, ctx, member: discord.Member):
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role or mute_role not in member.roles:
            await ctx.send("`⚠️` Cet utilisateur n'est pas mute.")
            return

        await member.remove_roles(mute_role, reason="Unmute manuel")

        # Supprimer du fichier
        mutes = load_json(MUTES_FILE)
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        if guild_id in mutes and user_id in mutes[guild_id]:
            del mutes[guild_id][user_id]
            if not mutes[guild_id]:
                del mutes[guild_id]
            save_json(MUTES_FILE, mutes)

        await ctx.send(f"`✅` {member} n'est plus mute.")

    @commands.command(name="mutelist")
    @is_moderator()
    async def mutelist(self, ctx):
        mutes = load_json(MUTES_FILE)
        guild_id = str(ctx.guild.id)
        if guild_id not in mutes or not mutes[guild_id]:
            await ctx.send("`ℹ️` Aucun utilisateur mute.")
            return

        embed = discord.Embed(title="🔇 Liste des mutes", color=0xffaa00)
        for user_id, data in mutes[guild_id].items():
            user_str = data["user_name"]
            reason = data["reason"]
            muted_at = datetime.fromtimestamp(data["muted_at"]).strftime("%d/%m/%Y %H:%M")
            until = datetime.fromtimestamp(data["until"]).strftime("%d/%m/%Y %H:%M")
            embed.add_field(
                name=f"{user_str} (ID: {user_id})",
                value=f"**Raison** : {reason}\n**Depuis** : {muted_at}\n**Jusqu'au** : {until}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name="warn")
    @is_moderator()
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        if member == ctx.author:
            await ctx.send("`❌` Vous ne pouvez pas vous avertir vous-même.")
            return

        warns = load_json(WARNS_FILE)
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        if guild_id not in warns:
            warns[guild_id] = {}
        if user_id not in warns[guild_id]:
            warns[guild_id][user_id] = []

        warn_entry = {
            "reason": reason,
            "moderator": str(ctx.author),
            "at": datetime.utcnow().timestamp()
        }
        warns[guild_id][user_id].append(warn_entry)
        save_json(WARNS_FILE, warns)

        await ctx.send(f"`⚠️` {member} a été averti • **Raison** : {reason}")

    @commands.command(name="unwarn")
    @is_moderator()
    async def unwarn(self, ctx, member: discord.Member, *, reason_to_remove: str):
        warns = load_json(WARNS_FILE)
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id not in warns or user_id not in warns[guild_id]:
            await ctx.send("`ℹ️` Cet utilisateur n'a aucun avertissement.")
            return

        before_count = len(warns[guild_id][user_id])
        warns[guild_id][user_id] = [
            w for w in warns[guild_id][user_id] if w["reason"] != reason_to_remove
        ]
        after_count = len(warns[guild_id][user_id])

        if before_count == after_count:
            await ctx.send("`❌` Aucun avertissement avec cette raison n'a été trouvé.")
        else:
            if not warns[guild_id][user_id]:
                del warns[guild_id][user_id]
            if not warns[guild_id]:
                del warns[guild_id]
            save_json(WARNS_FILE, warns)
            await ctx.send(f"`✅` Avertissement supprimé pour {member}.")

    @commands.command(name="warnlist")
    @is_moderator()
    async def warnlist(self, ctx, member: discord.Member = None):
        warns = load_json(WARNS_FILE)
        guild_id = str(ctx.guild.id)

        if member is None:
            # Lister tous les warns du serveur
            if guild_id not in warns or not warns[guild_id]:
                await ctx.send("`ℹ️` Aucun avertissement sur ce serveur.")
                return

            embed = discord.Embed(title="⚠️ Liste de tous les avertissements", color=0xffdd00)
            for uid, entries in warns[guild_id].items():
                user_str = "Inconnu"
                user = ctx.guild.get_member(int(uid))
                if user:
                    user_str = str(user)
                reasons = "\n".join([f"- {e['reason']} (par {e['moderator']})" for e in entries])
                embed.add_field(name=f"{user_str} (ID: {uid})", value=reasons[:1024], inline=False)
            await ctx.send(embed=embed)
        else:
            # Lister les warns d’un membre
            user_id = str(member.id)
            if guild_id not in warns or user_id not in warns[guild_id]:
                await ctx.send(f"`ℹ️` {member} n’a aucun avertissement.")
                return

            embed = discord.Embed(title=f"⚠️ Avertissements — {member}", color=0xffdd00)
            for entry in warns[guild_id][user_id]:
                at = datetime.fromtimestamp(entry["at"]).strftime("%d/%m/%Y %H:%M")
                embed.add_field(
                    name=f"Par {entry['moderator']} — {at}",
                    value=entry["reason"],
                    inline=False
                )
            await ctx.send(embed=embed)

# Setup
async def setup(bot):
    await bot.add_cog(Moderation(bot))