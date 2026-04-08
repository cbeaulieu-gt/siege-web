"""Bot test configuration — set env vars and mock discord before any imports."""

import os
import sys
from types import ModuleType
from unittest.mock import MagicMock

# Set required env vars before Settings() runs.
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")
os.environ.setdefault("BOT_API_KEY", "test-key")
os.environ.setdefault("ENVIRONMENT", "test")

# discord.py 2.4.0 imports audioop which was removed in Python 3.13+.
# Create a minimal mock of the discord module so tests can import app code
# without a real Discord connection.
if "discord" not in sys.modules:
    discord_mock = MagicMock()

    # discord.Client must be a real class so SiegeBot can subclass it.
    class _FakeClient:
        def __init__(self, **kwargs):
            pass

    # discord.TextChannel must be a real class for isinstance() checks.
    class _FakeTextChannel:
        pass

    # discord.NotFound and discord.HTTPException must be real exception classes
    # so that ``except discord.NotFound`` and ``except discord.HTTPException``
    # clauses in http_api.py work correctly during tests.
    class _FakeHTTPException(Exception):
        pass

    class _FakeNotFound(_FakeHTTPException):
        pass

    discord_mock.Client = _FakeClient
    discord_mock.TextChannel = _FakeTextChannel
    discord_mock.HTTPException = _FakeHTTPException
    discord_mock.NotFound = _FakeNotFound
    discord_mock.Intents = MagicMock()
    discord_mock.File = MagicMock()
    # Provide a real find() so SiegeBot methods work with mock guilds
    def _find(predicate, iterable):
        for item in iterable:
            if predicate(item):
                return item
        return None

    utils_mock = MagicMock()
    utils_mock.find = _find
    discord_mock.utils = utils_mock

    sys.modules["discord"] = discord_mock
    # Also stub sub-modules that discord.py would normally register.
    for sub in [
        "discord.abc",
        "discord.app_commands",
        "discord.ext",
        "discord.ext.commands",
    ]:
        sys.modules[sub] = MagicMock()
