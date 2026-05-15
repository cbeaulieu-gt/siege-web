"""Integration test fixtures for the bot HTTP sidecar.

Launches the bot process in fake mode (``BOT_TEST_MODE=fake``) as a real
subprocess on port 8001, waits until it reports healthy, then tears it down
after all tests complete.

The subprocess approach exercises the real TCP stack and uvicorn middleware —
unlike the in-process ``ASGITransport`` used by unit tests in
``bot/tests/test_http_api.py`` and the engineered-break meta-tests in
``test_meta_shape_assertions.py``.

Environment variables injected into the subprocess
---------------------------------------------------
  ``BOT_TEST_MODE=fake``          Activates ``FakeDiscordClient`` (no token).
  ``BOT_API_KEY=test-token-integration``  Shared secret for auth tests.
  ``DISCORD_TOKEN=fake-token``    Satisfies pydantic-settings validation;
                                  never used in fake mode.
  ``DISCORD_GUILD_ID=123456789``  Must be an integer-parseable string.
  ``ENVIRONMENT=test``            Keeps debug/docs disabled.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOT_API_KEY = "test-token-integration"
BOT_PORT = 8001
BOT_BASE_URL = f"http://localhost:{BOT_PORT}"
AUTH_HEADERS = {"Authorization": f"Bearer {BOT_API_KEY}"}

# Path to the bot package root (contains ``app/`` and ``pyproject.toml``).
_BOT_DIR = Path(__file__).parents[4] / "bot"

# Python interpreter inside the *bot* venv, not the backend venv.
# The integration suite is discovered by the backend's pytest (which uses
# backend/.venv), but the bot subprocess runs from the bot's own venv so
# that discord.py and its transitive deps are available.
# Cross-platform: Scripts/python.exe on Windows, bin/python on POSIX.
_BOT_PYTHON = (
    _BOT_DIR / ".venv" / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else _BOT_DIR / ".venv" / "bin" / "python"
)

_HEALTH_TIMEOUT_SECONDS = 30
_HEALTH_POLL_INTERVAL = 0.25


def _wait_for_health(base_url: str, timeout: float) -> None:
    """Poll ``GET {base_url}/api/health`` until it returns 200.

    Args:
        base_url: The bot sidecar base URL (e.g. ``http://localhost:8001``).
        timeout: Maximum number of seconds to wait before raising.

    Raises:
        RuntimeError: If the health endpoint does not respond within
            ``timeout`` seconds.
    """
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/api/health", timeout=2.0)
            if response.status_code == 200:
                return
        except Exception as exc:
            last_exc = exc
        time.sleep(_HEALTH_POLL_INTERVAL)
    raise RuntimeError(
        f"Bot sidecar did not become healthy within {timeout}s. "
        f"Last error: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Session-scoped subprocess fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def bot_url() -> Generator[str, None, None]:
    """Start the bot sidecar subprocess in fake mode; yield its base URL.

    The subprocess is started once per test session and torn down via
    ``SIGTERM`` after all tests complete.  All integration tests in this
    package receive the base URL via this fixture.

    Yields:
        The bot sidecar base URL (``http://localhost:8001``).

    Raises:
        RuntimeError: If the subprocess fails to start or the health check
            does not pass within ``_HEALTH_TIMEOUT_SECONDS``.
    """
    env = {
        "BOT_TEST_MODE": "fake",
        "BOT_API_KEY": BOT_API_KEY,
        "DISCORD_TOKEN": "fake-token",
        "DISCORD_GUILD_ID": "123456789",
        "ENVIRONMENT": "test",
        # Suppress telemetry — no Azure connection string in test.
        "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
        # Ensure the subprocess can import the bot ``app`` package.
        "PYTHONPATH": str(_BOT_DIR),
    }

    proc = subprocess.Popen(
        [str(_BOT_PYTHON), "-m", "app.main"],
        cwd=str(_BOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_health(BOT_BASE_URL, _HEALTH_TIMEOUT_SECONDS)
    except RuntimeError:
        proc.terminate()
        stdout = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
        stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        raise RuntimeError(
            f"Bot subprocess failed to start.\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    yield BOT_BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
