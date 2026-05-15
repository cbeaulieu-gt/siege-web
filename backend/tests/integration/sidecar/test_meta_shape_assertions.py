"""Meta-tests proving that body-shape assertions are tight.

Each test sets ``BOT_TEST_MODE=fake_broken_shape`` in-process, wires a
``FakeDiscordClient`` to the bot's FastAPI app, issues the same request the
regular shape tests issue, re-runs the same assertion logic, and asserts it
raises ``AssertionError`` against the broken response.  This proves the
shape checks would actually catch a real regression.

Design — in-process ASGI transport with sys.modules swap
---------------------------------------------------------
These tests use ``httpx.AsyncClient`` with ``ASGITransport`` against the
bot's FastAPI app.

The challenge: the backend pytest session already has the backend's ``app``
package in ``sys.modules`` (as ``app.*``), while the bot's modules also live
in a package named ``app``.  The ``bot_app_modules`` fixture temporarily
removes the backend's ``app.*`` entries from ``sys.modules``, imports the
bot's modules under the ``app`` name, and restores the backend's ``app``
after each test.  ``monkeypatch`` handles cleanup.

This avoids the two-subprocess Winsock initialisation race on Windows while
still exercising the real bot HTTP handler logic via ASGI.

Option A vs Option B breakage
------------------------------
- ``/api/health`` → Option B shim in ``http_api.py``: drops ``bot_connected``.
- ``POST /api/notify`` → Option B shim in ``http_api.py``: returns ``"ok"``
  instead of ``"sent"``.
- ``GET /api/members`` → Option A shim in ``fake_discord.py``: elements have
  only ``id``, dropping ``username`` and ``display_name``.

See PR #425 for the manual deliberate-break step this automates.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from .conftest import BOT_API_KEY

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# The bot root is four parent levels above this file:
#   backend/tests/integration/sidecar/  ← this file
#   backend/tests/integration/
#   backend/tests/
#   backend/
#   <repo root>/
#   bot/
_BOT_DIR = Path(__file__).parents[4] / "bot"

# Auth header re-used across all meta-tests.
_AUTH_HEADERS = {"Authorization": f"Bearer {BOT_API_KEY}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bot_app_modules(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Import bot app modules, temporarily shadowing the backend ``app`` package.

    The backend pytest session caches the backend's ``app`` package in
    ``sys.modules`` as ``"app"`` and ``"app.*"``.  The bot's package also
    uses the name ``"app"``.  This fixture:

    1. Removes all ``app`` / ``app.*`` keys from ``sys.modules`` via
       ``monkeypatch.delitem`` (which restores each to its original value
       automatically on teardown).
    2. Inserts the bot directory at the front of ``sys.path``.
    3. Inserts a minimal ``discord`` stub (the backend venv has no
       ``discord.py``).
    4. Sets the env vars that ``app.config.Settings()`` requires.
    5. Imports the bot modules, populating ``sys.modules["app.*"]`` with
       the bot versions.
    6. Restores everything via ``monkeypatch`` teardown after the test.

    Returns:
        A dict with keys ``"http_api"`` and ``"fake_discord"`` pointing to
        the imported bot module objects.
    """
    # ---- 1 & 2. Remove backend app from sys.modules ----
    # monkeypatch.delitem restores each key to its original value on teardown,
    # so the backend's ``app.*`` entries are automatically reinstated after
    # the test completes — no explicit snapshot-and-restore is needed.
    backend_app_keys = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in backend_app_keys:
        monkeypatch.delitem(sys.modules, k)

    # ---- 3. Prepend bot dir to sys.path ----
    monkeypatch.syspath_prepend(str(_BOT_DIR))

    # ---- 4. Discord stub ----
    if "discord" not in sys.modules:

        class _StubHTTPException(Exception):
            """Minimal stub satisfying FastAPI's exception-handler registration."""

            def __init__(self, response: Any = None, text: str = "") -> None:
                self.response = response
                self.status: int = getattr(response, "status", 0)
                self.text = text
                super().__init__(text)

        class _StubNotFound(_StubHTTPException):
            pass

        class _StubForbidden(_StubHTTPException):
            pass

        discord_stub: ModuleType = MagicMock()
        discord_stub.HTTPException = _StubHTTPException
        discord_stub.NotFound = _StubNotFound
        discord_stub.Forbidden = _StubForbidden
        discord_stub.Intents = MagicMock()
        discord_stub.File = MagicMock()
        monkeypatch.setitem(sys.modules, "discord", discord_stub)

    # ---- 5. Required env vars for bot Settings() ----
    monkeypatch.setenv("DISCORD_TOKEN", "fake-token-meta")
    monkeypatch.setenv("BOT_API_KEY", BOT_API_KEY)
    # DISCORD_GUILD_ID and ENVIRONMENT already set by backend conftest.

    # ---- 6. Import bot modules ----
    import app.fake_discord as fake_discord_mod
    import app.http_api as http_api_mod
    from app.fake_discord import FakeDiscordClient
    from app.http_api import set_bot

    import app.config  # noqa: F401 — side-effect: registers Settings()

    # Wire a FakeDiscordClient into the HTTP app.
    bot = FakeDiscordClient(guild_id=123456789)
    set_bot(bot)
    http_api_mod.settings.bot_api_key = BOT_API_KEY

    return {"http_api": http_api_mod, "fake_discord": fake_discord_mod}


@pytest.fixture()
def broken_client(
    bot_app_modules: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncClient:
    """Return an ASGI client wired to the bot app in broken-shape mode.

    Depends on ``bot_app_modules`` (which imports the bot package) and sets
    ``BOT_TEST_MODE=fake_broken_shape`` so the Option A and Option B shims
    activate.

    Args:
        bot_app_modules: Fixture providing the imported bot module objects.
        monkeypatch: pytest fixture for reversible env-var changes.

    Returns:
        An ``AsyncClient`` with ``ASGITransport`` against the bot FastAPI app.
    """
    monkeypatch.setenv("BOT_TEST_MODE", "fake_broken_shape")
    http_app = bot_app_modules["http_api"].app
    return AsyncClient(transport=ASGITransport(app=http_app), base_url="http://test")


# ---------------------------------------------------------------------------
# Meta-test 1: /api/health — broken body shape (Option B)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_meta_health_response_shape_check_fails_on_broken_shape(
    broken_client: AsyncClient,
) -> None:
    """Proves the /api/health shape assertions would catch a real regression.

    The broken-shape shim omits ``bot_connected`` from the health response
    (returns only ``{"status": "healthy"}``).  The regular tests assert that
    exactly two keys are present and that ``bot_connected`` is a bool.  Both
    assertions must fail against the broken response.

    Args:
        broken_client: ASGI client against the bot app in broken-shape mode.
    """
    async with broken_client as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()

    # Mirror of test_health_response_shape_has_exactly_two_keys —
    # broken shape returns only {"status"}, so the set check must fail.
    with pytest.raises(AssertionError):
        assert set(data.keys()) == {"status", "bot_connected"}

    # Mirror of test_health_bot_connected_is_true_in_fake_mode —
    # key is absent; accept either AssertionError or KeyError.
    with pytest.raises((AssertionError, KeyError)):
        assert isinstance(data["bot_connected"], bool)


# ---------------------------------------------------------------------------
# Meta-test 2: POST /api/notify — broken status value (Option B)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_meta_notify_status_check_fails_on_broken_shape(
    broken_client: AsyncClient,
) -> None:
    """Proves the /api/notify body assertion would catch a real regression.

    The broken-shape shim returns ``{"status": "ok"}`` instead of
    ``{"status": "sent"}``.  The regular test asserts exact equality to
    ``{"status": "sent"}`` — that assertion must fail against the broken
    response.

    Args:
        broken_client: ASGI client against the bot app in broken-shape mode.
    """
    async with broken_client as client:
        response = await client.post(
            "/api/notify",
            json={"username": "known-user", "message": "Hello!"},
            headers=_AUTH_HEADERS,
        )

    assert response.status_code == 200

    # Mirror of test_notify_known_user_returns_200_sent —
    # {"status": "ok"} != {"status": "sent"}, so this must fail.
    with pytest.raises(AssertionError):
        assert response.json() == {"status": "sent"}


# ---------------------------------------------------------------------------
# Meta-test 3: GET /api/members — broken element shape (Option A)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_meta_members_element_shape_check_fails_on_broken_shape(
    broken_client: AsyncClient,
) -> None:
    """Proves the /api/members element-key assertion would catch a real regression.

    The broken-shape fake's ``get_members()`` returns elements with only
    ``id`` (drops ``username`` and ``display_name``).  The regular test
    asserts every element has exactly ``{"id", "username", "display_name"}``
    — that assertion must fail against the broken elements.

    Args:
        broken_client: ASGI client against the bot app in broken-shape mode.
    """
    async with broken_client as client:
        response = await client.get("/api/members", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    _members_list_keys = {"id", "username", "display_name"}

    # Mirror of test_get_members_elements_have_three_required_keys —
    # broken elements have only {"id"}, so the set comparison must fail.
    with pytest.raises(AssertionError):
        for element in data:
            assert set(element.keys()) == _members_list_keys, (
                f"Member element keys mismatch: got {set(element.keys())}, "
                f"expected {_members_list_keys}"
            )
