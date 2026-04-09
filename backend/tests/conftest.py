"""
Shared pytest configuration for backend tests.

Sets required environment variables before any app module is imported so that
pydantic-settings (which reads env at class instantiation time) has the values
it needs even when a local .env file is absent.

Only vars without defaults in Settings are set here; everything else either has
a sensible default or is already present in the developer's .env file.
"""

import os

import pytest

# Ensure ENVIRONMENT is always set — Settings has no default for this field so
# that production deployments fail fast if it is missing.  Tests run as "test".
os.environ.setdefault("ENVIRONMENT", "test")

# Provide placeholder values for required fields that have no defaults, in case
# the developer's .env is absent (e.g. a fresh checkout running tests for the
# first time before configuring local secrets).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("DISCORD_BOT_API_URL", "http://localhost:8001")
os.environ.setdefault("DISCORD_BOT_API_KEY", "test-key")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")


@pytest.fixture(autouse=True)
def disable_auth_for_tests(monkeypatch):
    """Bypass auth middleware for all tests by default.

    Individual tests that exercise auth behaviour override this by calling
    ``monkeypatch.setattr("app.config.settings.auth_disabled", False)``
    explicitly, which takes precedence because monkeypatch patches are applied
    in order within the same test.
    """
    monkeypatch.setattr("app.config.settings.auth_disabled", True)
