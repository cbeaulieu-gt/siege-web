"""Integration tests for POST /api/post-image.

Exercises the live bot sidecar (started by the ``bot_url`` fixture in
``conftest.py``) over a real TCP socket.

Contract source: ``bot/INTERFACE.md`` → ``POST /api/post-image`` section.

The ``file`` part is an in-memory minimal PNG so the suite requires no
on-disk fixtures.

Magic trigger values (from ``bot/app/fake_discord.py``)
--------------------------------------------------------
  ``"known-channel"``    → 200 success with ``url``
  ``"unknown-chan"``     → 404 (channel not found)
  ``"chan-forbidden"``   → 403 (bot lacks send permission)
  ``"chan-http4xx"``     → 502 (Discord 4xx, rate-limited)
  ``"chan-http5xx"``     → 503 (Discord 5xx)
  ``"chan-timeout"``     → 503 (asyncio.TimeoutError)
"""

from __future__ import annotations

import httpx

from .conftest import AUTH_HEADERS

# Minimal 1×1 white PNG — valid multipart bytes that satisfy UploadFile.
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _post_image(
    bot_url: str,
    channel_name: str,
    headers: dict | None = None,
    png: bytes = _MINIMAL_PNG,
) -> httpx.Response:
    """Helper: POST a multipart image request to the sidecar.

    Args:
        bot_url: Base URL of the running sidecar.
        channel_name: Value for the ``channel_name`` form field.
        headers: HTTP headers to include.  Defaults to ``AUTH_HEADERS``.
        png: Image bytes to send.  Defaults to ``_MINIMAL_PNG``.

    Returns:
        The ``httpx.Response`` from the sidecar.
    """
    if headers is None:
        headers = AUTH_HEADERS
    return httpx.post(
        f"{bot_url}/api/post-image",
        data={"channel_name": channel_name},
        files={"file": ("test.png", png, "image/png")},
        headers=headers,
    )


def test_post_image_known_channel_returns_200_with_url(bot_url: str) -> None:
    """POST /api/post-image to a known channel returns 200 with a URL.

    Validates both status code and body shape — ``status`` must equal
    ``"sent"`` and ``url`` must be a non-empty string.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = _post_image(bot_url, "known-channel")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    assert isinstance(data["url"], str)
    assert len(data["url"]) > 0


def test_post_image_unknown_channel_returns_404_with_detail(bot_url: str) -> None:
    """POST /api/post-image with an unknown channel returns 404 with ``detail``.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = _post_image(bot_url, "unknown-chan")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)


def test_post_image_missing_channel_name_form_field_returns_422(bot_url: str) -> None:
    """POST /api/post-image with ``channel_name`` omitted from form returns 422.

    ``channel_name`` is a ``Form(...)`` field — omitting it entirely from
    the multipart body triggers FastAPI validation.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-image",
        files={"file": ("test.png", _MINIMAL_PNG, "image/png")},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) > 0
    item = data["detail"][0]
    assert "loc" in item
    assert "msg" in item
    assert "type" in item


def test_post_image_channel_name_as_query_param_returns_422(bot_url: str) -> None:
    """POST /api/post-image with ``channel_name`` as query param returns 422.

    ``channel_name`` must be a multipart form field; passing it as a query
    parameter leaves the form field absent, producing a 422.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-image?channel_name=known-channel",
        files={"file": ("test.png", _MINIMAL_PNG, "image/png")},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


def test_post_image_discord_forbidden_returns_403(bot_url: str) -> None:
    """POST /api/post-image when bot lacks send permission returns 403.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = _post_image(bot_url, "chan-forbidden")
    assert response.status_code == 403
    data = response.json()
    assert "permission denied" in data["detail"].lower()


def test_post_image_discord_4xx_returns_502(bot_url: str) -> None:
    """POST /api/post-image on Discord 4xx returns 502.

    ``FakeDiscordClient`` raises ``discord.HTTPException(status=429)`` for
    ``"chan-http4xx"``.  The global handler returns a generic detail message —
    the upstream status code is logged server-side, not exposed to callers.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = _post_image(bot_url, "chan-http4xx")
    assert response.status_code == 502
    data = response.json()
    assert data["detail"] == "Upstream Discord error"
    assert "429" not in data["detail"]


def test_post_image_discord_5xx_returns_503(bot_url: str) -> None:
    """POST /api/post-image on Discord 5xx returns 503.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = _post_image(bot_url, "chan-http5xx")
    assert response.status_code == 503
    data = response.json()
    assert "unavailable" in data["detail"].lower()


def test_post_image_timeout_returns_503(bot_url: str) -> None:
    """POST /api/post-image on asyncio.TimeoutError returns 503.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = _post_image(bot_url, "chan-timeout")
    assert response.status_code == 503
    data = response.json()
    assert "unavailable" in data["detail"].lower()
