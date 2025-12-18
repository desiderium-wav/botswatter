import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red


class Botswatter(commands.Cog):
    """
    Aggressive moderation cog:
    - Purges image messages past the 14-day limit
    - Instantly bans users posting configured keywords
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7723918842, force_registration=True)

        default_guild = {
            "keywords": [],
            "enabled_channels": []
        }

        self.config.register_guild(**default_guild)

    # ------------------------------------------------------------
    # IMAGE PURGE (NO 14-DAY LIMIT)
    # ------------------------------------------------------------
    @commands.command(name="purgeimages")
    @checks.admin_or_permissions(manage_messages=True)
    async def purge_images(self, ctx, channel: discord.TextChannel = None):
        """
        Deletes ALL messages containing images in a channel.
        Deletes individually to bypass the 14-day bulk limit.
        """
        channel = channel or ctx.channel
        deleted = 0

        await ctx.send(f"🧹 Beginning image purge in {channel.mention}…")

        async for message in channel.history(limit=None):
            try:
                if message.attachments:
                    for a in message.attachments:
                        if a.content_type and a.content_type.startswith("image"):
                            await message.delete()
                            deleted += 1
                            break

                elif message.embeds:
                    for e in message.embeds:
                        if e.image or e.thumbnail:
                            await message.delete()
                            deleted += 1
                            break

            except discord.Forbidden:
                await ctx.send("❌ Missing permissions to delete messages.")
                return
            except discord.HTTPException:
                pass  # rate limits happen; continue

        await ctx.send(f"✅ Image purge complete. Deleted **{deleted}** messages.")

    # ------------------------------------------------------------
    # AUTOBAN CONFIGURATION
    # ------------------------------------------------------------
    @commands.group(name="autoban", invoke_without_command=True)
    @checks.admin_or_permissions(ban_members=True)
    async def autoban(self, ctx):
        """Manage autoban keywords and channels."""
        await ctx.send("Subcommands: add | remove | list | channel")

    @autoban.command(name="add")
    async def autoban_add(self, ctx, *, phrase: str):
        keywords = await self.config.guild(ctx.guild).keywords()
        keywords.append(phrase.lower())
        await self.config.guild(ctx.guild).keywords.set(keywords)
        await ctx.send(f"☠️ Autoban phrase added: `{phrase}`")

    @autoban.command(name="remove")
    async def autoban_remove(self, ctx, *, phrase: str):
        keywords = await self.config.guild(ctx.guild).keywords()
        keywords = [k for k in keywords if k != phrase.lower()]
        await self.config.guild(ctx.guild).keywords.set(keywords)
        await ctx.send(f"🗑️ Autoban phrase removed: `{phrase}`")

    @autoban.command(name="list")
    async def autoban_list(self, ctx):
        keywords = await self.config.guild(ctx.guild).keywords()
        if not keywords:
            await ctx.send("No autoban phrases configured.")
        else:
            await ctx.send(
                "**Autoban phrases:**\n" +
                "\n".join(f"- `{k}`" for k in keywords)
            )

    @autoban.command(name="channel")
    async def autoban_channel(self, ctx, channel: discord.TextChannel):
        channels = await self.config.guild(ctx.guild).enabled_channels()

        if channel.id in channels:
            channels.remove(channel.id)
            await ctx.send(f"🔕 Removed {channel.mention} from monitoring.")
        else:
            channels.append(channel.id)
            await ctx.send(f"🔔 Added {channel.mention} to monitoring.")

        await self.config.guild(ctx.guild).enabled_channels.set(channels)

    # ------------------------------------------------------------
    # MESSAGE LISTENER (INSTANT BAN)
    # ------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild_conf = self.config.guild(message.guild)
        keywords = await guild_conf.keywords()
        channels = await guild_conf.enabled_channels()

        if message.channel.id not in channels:
            return

        content = message.content.lower()

        for phrase in keywords:
            if phrase in content:
                try:
                    await message.guild.ban(
                        message.author,
                        reason=f"Botswatter autoban trigger: {phrase}",
                        delete_message_days=0
                    )
                    await message.delete()
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass
                return
