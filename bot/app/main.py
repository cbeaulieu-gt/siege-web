"""Entry point: runs the Discord bot and FastAPI HTTP sidecar concurrently."""

import asyncio
import logging

import discord
import uvicorn

from app.config import settings
from app.discord_client import SiegeBot
from app.http_api import app as http_app
from app.http_api import set_bot
from app.telemetry import configure_telemetry

logger = logging.getLogger(__name__)


async def run_http_server() -> None:
    """Run the FastAPI/uvicorn HTTP sidecar on port 8001."""
    config = uvicorn.Config(
        http_app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_discord_client(bot: SiegeBot) -> None:
    """Connect and run the Discord client."""
    async with bot:
        await bot.start(settings.discord_token)


async def main() -> None:
    """Start both the Discord client and HTTP server concurrently."""
    intents = discord.Intents.default()
    intents.members = True
    bot = SiegeBot(guild_id=int(settings.discord_guild_id), intents=intents)
    set_bot(bot)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(run_discord_client(bot))
        tg.create_task(run_http_server())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    configure_telemetry()
    asyncio.run(main())
