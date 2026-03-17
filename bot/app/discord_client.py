import discord


class SiegeBot(discord.Client):
    """Discord client for the Siege Assignment System.

    All interaction methods are stubs to be implemented in Phase 1.
    """

    async def send_dm(self, username: str, message: str) -> None:
        """Send a direct message to a guild member by username.

        Args:
            username: The Discord username of the recipient.
            message: The text content to send.
        """
        raise NotImplementedError(
            f"send_dm is not yet implemented. Would send '{message}' to user '{username}'."
        )

    async def post_message(self, channel_name: str, message: str) -> None:
        """Post a text message to a guild channel by name.

        Args:
            channel_name: The name of the text channel to post into.
            message: The text content to post.
        """
        raise NotImplementedError(
            f"post_message is not yet implemented. "
            f"Would post '{message}' to channel '{channel_name}'."
        )

    async def post_image(self, channel_name: str, image_bytes: bytes) -> None:
        """Post an image to a guild channel by name.

        Args:
            channel_name: The name of the text channel to post into.
            image_bytes: The raw image data to attach.
        """
        raise NotImplementedError(
            f"post_image is not yet implemented. "
            f"Would post image ({len(image_bytes)} bytes) to channel '{channel_name}'."
        )

    async def get_members(self) -> list[str]:
        """Retrieve a list of member usernames from the configured guild.

        Returns:
            A list of Discord usernames in the guild.
        """
        raise NotImplementedError(
            "get_members is not yet implemented. Would return guild member usernames."
        )
