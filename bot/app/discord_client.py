import io

import discord


class SiegeBot(discord.Client):
    """Discord client for the Siege Assignment System."""

    def __init__(self, guild_id: int, **kwargs):
        super().__init__(**kwargs)
        self.guild_id = guild_id
        self._guild: discord.Guild | None = None

    async def on_ready(self):
        self._guild = self.get_guild(self.guild_id)

    def _require_guild(self) -> discord.Guild:
        if self._guild is None:
            raise RuntimeError("Bot not ready — guild not loaded yet")
        return self._guild

    async def send_dm(self, username: str, message: str) -> None:
        """Find member by username in the guild, open DM, send message."""
        guild = self._require_guild()
        member = discord.utils.find(
            lambda m: m.name.lower() == username.lower(), guild.members
        )
        if member is None:
            raise ValueError(f"Member '{username}' not found in guild")
        dm = await member.create_dm()
        await dm.send(message)

    async def post_message(self, channel_name: str, message: str) -> None:
        """Find text channel by name, post message."""
        guild = self._require_guild()
        channel = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel) and c.name == channel_name,
            guild.channels,
        )
        if channel is None:
            raise ValueError(f"Channel '{channel_name}' not found in guild")
        await channel.send(message)

    async def post_image(
        self, channel_name: str, image_bytes: bytes, filename: str = "image.png"
    ) -> None:
        """Find text channel by name, post image as Discord file attachment."""
        guild = self._require_guild()
        channel = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel) and c.name == channel_name,
            guild.channels,
        )
        if channel is None:
            raise ValueError(f"Channel '{channel_name}' not found in guild")
        await channel.send(file=discord.File(io.BytesIO(image_bytes), filename=filename))

    async def get_members(self) -> list[dict]:
        """Return list of guild members as dicts with id, username, display_name."""
        guild = self._require_guild()
        return [
            {
                "id": str(m.id),
                "username": m.name,
                "display_name": m.display_name,
            }
            for m in guild.members
        ]
