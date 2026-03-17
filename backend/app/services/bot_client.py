"""HTTP client for the Discord bot sidecar API."""

import httpx

from app.config import settings


class BotClient:
    """HTTP client for the Discord bot sidecar API."""

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=settings.discord_bot_api_url,
            headers={"Authorization": f"Bearer {settings.discord_bot_api_key}"},
            timeout=10.0,
        )

    async def notify(self, username: str, message: str) -> bool:
        """Send DM via bot. Returns True on success, False on error."""
        try:
            async with self._make_client() as client:
                response = await client.post(
                    "/api/notify",
                    json={"username": username, "message": message},
                )
                response.raise_for_status()
                return True
        except httpx.HTTPError:
            return False

    async def post_message(self, channel_name: str, message: str) -> bool:
        """Post text to channel. Returns True on success, False on error."""
        try:
            async with self._make_client() as client:
                response = await client.post(
                    "/api/post-message",
                    json={"channel_name": channel_name, "message": message},
                )
                response.raise_for_status()
                return True
        except httpx.HTTPError:
            return False

    async def post_image(
        self, channel_name: str, image_bytes: bytes, filename: str
    ) -> bool:
        """Post image to channel. Returns True on success, False on error."""
        try:
            async with self._make_client() as client:
                response = await client.post(
                    f"/api/post-image?channel_name={channel_name}",
                    files={"file": (filename, image_bytes, "image/png")},
                )
                response.raise_for_status()
                return True
        except httpx.HTTPError:
            return False

    async def get_members(self) -> list[dict]:
        """Get guild member list."""
        try:
            async with self._make_client() as client:
                response = await client.get("/api/members")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError:
            return []


bot_client = BotClient()
