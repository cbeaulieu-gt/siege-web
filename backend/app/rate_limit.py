"""Rate-limiting utilities shared across the application.

This module owns the single ``Limiter`` instance that is registered on
``app.state`` in ``app.main``.  Keeping it here breaks the circular-import
that would arise if ``app.api.auth`` tried to import from ``app.main``.
"""

import uuid

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: F401 — re-exported
from slowapi.errors import RateLimitExceeded  # noqa: F401 — re-exported
from slowapi.util import get_remote_address

from app.config import settings


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP from X-Forwarded-For for rate bucketing.

    Reads the *leftmost* value from the ``X-Forwarded-For`` header, which is
    the IP the Azure Container Apps ingress appended as the true origin.
    Client-supplied values further to the right in the header chain are
    ignored because they can be trivially spoofed.  Falls back to the ASGI
    transport remote address when the header is absent (e.g. local dev with
    no proxy).

    Trust assumption: exactly one trusted reverse-proxy hop (Container Apps
    ingress) prepends the real client IP as the leftmost entry.  If your
    deployment adds additional upstream proxies, shift the index right
    accordingly.

    Args:
        request: The incoming FastAPI/Starlette request.

    Returns:
        A string representation of the client IP address.
    """
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # Cap before splitting — defense-in-depth against pathologically long
        # headers; ASGI servers already cap total header size, but this keeps
        # our split O(1) if anything upstream changes.
        forwarded_for = forwarded_for[:8192]
        # Leftmost entry is written by the trusted ingress proxy.
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


def _rate_limit_key(request: Request) -> str:
    """Composite key function that honours the AUTH_DISABLED bypass.

    When ``AUTH_DISABLED=true`` (dev/test mode) each request receives a
    unique UUID bucket so rate-limit counters never accumulate — effectively
    disabling limiting without touching the ``Limiter.enabled`` flag (which
    is set at construction time and therefore insensitive to monkeypatching
    in tests).

    When auth is enabled, delegates to ``_get_client_ip`` for normal
    IP-based bucketing.

    Args:
        request: The incoming FastAPI/Starlette request.

    Returns:
        A string key used by slowapi to group requests into rate-limit
        buckets.
    """
    if settings.auth_disabled:
        # Unique per request — no bucket ever fills up.
        return f"bypass-{uuid.uuid4()}"
    return _get_client_ip(request)


# Single application-wide Limiter instance.  Registered on ``app.state`` and
# used as a decorator in ``app.api.auth``.
limiter: Limiter = Limiter(key_func=_rate_limit_key)
