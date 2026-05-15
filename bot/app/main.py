"""Entry point: runs the Discord bot and FastAPI HTTP sidecar concurrently.

When the ``BOT_TEST_MODE`` environment variable is set to ``"fake"``, the
real discord.py client is replaced with an in-memory ``FakeDiscordClient``
that requires no Discord token or network connection.  This mode is used
exclusively by the integration test suite in
``backend/tests/integration/sidecar/`` — never in production.

A second test mode ``BOT_TEST_MODE=fake_broken_shape`` also uses
``FakeDiscordClient`` but instructs it (via ``fake_discord.is_broken_shape_mode()``)
and the HTTP handlers (via shims in ``http_api.py``) to return
intentionally-wrong response shapes.  This powers the engineered-break
meta-tests in ``backend/tests/integration/sidecar/test_meta_shape_assertions.py``
that prove the regular shape assertions are tight.
"""

import asyncio
import logging
import os

import discord
import uvicorn

from app.config import settings
from app.discord_client import SiegeBot
from app.http_api import app as http_app
from app.http_api import set_bot
from app.telemetry import configure_telemetry

logger = logging.getLogger(__name__)

_BOT_TEST_MODE = os.environ.get("BOT_TEST_MODE", "").lower()


def _http_port() -> int:
    """Return the port the HTTP sidecar should bind to.

    Reads ``HTTP_PORT`` from the environment (default ``8001``).  Test
    fixtures can set ``HTTP_PORT=8002`` to run a second subprocess without
    conflicting with the primary integration-test instance.

    Returns:
        Integer port number for uvicorn to bind.
    """
    return int(os.environ.get("HTTP_PORT", "8001"))


async def run_http_server() -> None:
    """Run the FastAPI/uvicorn HTTP sidecar on the configured port."""
    config = uvicorn.Config(
        http_app,
        host="0.0.0.0",
        port=_http_port(),
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_discord_client(bot: SiegeBot) -> None:
    """Connect and run the Discord client."""
    async with bot:
        await bot.start(settings.discord_token)


async def main() -> None:
    """Start both the Discord client and HTTP server concurrently.

    In fake mode (``BOT_TEST_MODE=fake`` or ``BOT_TEST_MODE=fake_broken_shape``)
    the discord.py client is replaced with an in-memory ``FakeDiscordClient``
    and only the HTTP server task is started — there is no Discord connection
    to manage.

    The ``fake_broken_shape`` variant uses the same ``FakeDiscordClient`` but
    the client and HTTP handlers return intentionally-wrong shapes so the
    engineered-break meta-tests can confirm the regular shape assertions are
    tight.
    """
    if _BOT_TEST_MODE in ("fake", "fake_broken_shape"):
        from app.fake_discord import FakeDiscordClient

        logger.info(
            "BOT_TEST_MODE=%s: using FakeDiscordClient (no Discord token required)",
            _BOT_TEST_MODE,
        )
        bot = FakeDiscordClient(guild_id=int(settings.discord_guild_id))
        set_bot(bot)
        await run_http_server()
    else:
        intents = discord.Intents.default()
        intents.members = True
        bot = SiegeBot(guild_id=int(settings.discord_guild_id), intents=intents)
        set_bot(bot)

        async with asyncio.TaskGroup() as tg:
            tg.create_task(run_discord_client(bot))
            tg.create_task(run_http_server())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Configure telemetry with the HTTP sidecar app so FastAPIInstrumentor
    # can wrap it.  OTEL_SERVICE_NAME must be set in the container environment
    # (see infra/modules/container-apps.bicep) to populate cloud_RoleName
    # in Application Insights.
    configure_telemetry(http_app)
    asyncio.run(main())
