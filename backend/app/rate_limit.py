"""Rate-limiting utilities shared across the application.

This module owns the single ``Limiter`` instance that is registered on
``app.state`` in ``app.main``.  Keeping it here breaks the circular-import
that would arise if ``app.api.auth`` tried to import from ``app.main``.

The module also exposes:

- ``_get_client_ip`` — XFF-aware IP extractor with IP validation and a
  throttled production trust-model warning.
- ``rate_limit_exceeded_handler`` — custom async 429 handler that sets a
  ``Retry-After`` header derived from the rate-limit window, without relying
  on slowapi's private API.  The only public contracts we rely on from
  slowapi are ``Limiter`` and ``RateLimitExceeded``; the
  ``>=0.1.9,<0.2`` pin in ``requirements.txt`` is still good hygiene as
  defense-in-depth (minor upgrades may rename even public symbols), but we
  no longer import ``_rate_limit_exceeded_handler``.
"""

import ipaddress
import logging
import time
import uuid

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded  # noqa: F401 — re-exported
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse, Response

from app.config import settings

# Module-level logger — records appear under "app.rate_limit".
logger = logging.getLogger(__name__)

# Rate-limit the production XFF-absent warning so it does not flood logs.
_last_xff_absent_warning: float = 0.0
_XFF_WARN_INTERVAL_SECS: float = 60.0


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP from X-Forwarded-For for rate bucketing.

    Reads the *leftmost* value from the ``X-Forwarded-For`` header, which is
    the IP the Azure Container Apps ingress appended as the true origin.
    Client-supplied values further to the right in the header chain are
    ignored because they can be trivially spoofed.

    The leftmost candidate is validated with :func:`ipaddress.ip_address`.
    If the value is not a valid IP address (e.g. an attacker-injected string),
    the function falls through to the ASGI transport remote address so that:

    - Garbage strings cannot be used as shared-bucket keys to collude with
      other attackers.
    - Rotating unique garbage values cannot generate a fresh rate-limit bucket
      on every request (unlimited bypass).

    Falls back to the ASGI transport remote address when the header is absent
    (e.g. local dev with no proxy).  In production, absence of the header
    triggers a throttled WARNING because it suggests direct backend access
    that bypasses Container Apps ingress.

    Trust assumption: exactly one trusted reverse-proxy hop (Container Apps
    ingress) prepends the real client IP as the leftmost entry.  If your
    deployment adds additional upstream proxies, shift the index right
    accordingly.

    Args:
        request: The incoming FastAPI/Starlette request.

    Returns:
        A string representation of the client IP address to use as the
        rate-limit bucket key.
    """
    global _last_xff_absent_warning

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # Cap before splitting — defense-in-depth against pathologically long
        # headers; ASGI servers already cap total header size, but this keeps
        # our split O(1) if anything upstream changes.
        forwarded_for = forwarded_for[:8192]
        leftmost = forwarded_for.split(",")[0].strip()
        try:
            ipaddress.ip_address(leftmost)
            return leftmost
        except ValueError:
            # Invalid IP in XFF — fall through to the ASGI remote address so
            # that garbage values cannot escape or manipulate rate-limit buckets.
            pass
    else:
        # XFF absent — warn in production since direct backend access bypassing
        # Container Apps ingress indicates a misconfiguration.  The warning is
        # throttled to at most once per 60 s to avoid log flooding.
        if settings.environment == "production":
            now = time.monotonic()
            if now - _last_xff_absent_warning >= _XFF_WARN_INTERVAL_SECS:
                _last_xff_absent_warning = now
                logger.warning(
                    "X-Forwarded-For absent in production request — trust "
                    "model assumes Container Apps ingress is in front. "
                    "Direct backend access may indicate misconfiguration."
                )

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


def _parse_retry_after_seconds(detail: str) -> int | None:
    """Parse a slowapi rate-limit detail string into a window size in seconds.

    slowapi's ``RateLimitExceeded.detail`` is the human-readable rate string
    such as ``"10 per 1 minute"`` or ``"5 per 1 second"``.  This function
    extracts the window duration and converts it to seconds so it can be used
    as a conservative ``Retry-After`` upper bound when the accurate countdown
    from ``get_window_stats`` is unavailable.

    Args:
        detail: The rate-limit detail string from ``RateLimitExceeded.detail``.

    Returns:
        The window duration in whole seconds, or ``None`` if the string could
        not be parsed.
    """
    _unit_to_seconds: dict[str, int] = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }
    lower = detail.lower()
    for unit, secs in _unit_to_seconds.items():
        if unit in lower:
            # Look for an optional multiplier immediately before the unit,
            # e.g. "10 per 2 minute" → multiplier 2, result 120.
            parts = lower.split(unit)[0].split()
            if parts:
                try:
                    multiplier = int(parts[-1])
                    return multiplier * secs
                except ValueError:
                    return secs
            return secs
    return None


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return a JSON 429 response with a ``Retry-After`` header.

    Replaces slowapi's private ``_rate_limit_exceeded_handler`` so we own
    the response format and guarantee a ``Retry-After`` header without
    depending on slowapi internals.

    The ``Retry-After`` value is derived in two steps:

    1. **Via slowapi's header injection** — if
       ``request.state.view_rate_limit`` is populated (normal path), we
       delegate to ``request.app.state.limiter._inject_headers`` which calls
       ``get_window_stats`` for an accurate per-window countdown.
    2. **Fallback parsing** — if injection fails or the header is still
       absent, we parse the rate-limit detail string (e.g. ``"10 per 1
       minute"``) and use the window size as a conservative upper bound.
       If parsing also fails we fall back to ``60`` seconds.

    The only slowapi public contracts used here are ``Limiter``,
    ``RateLimitExceeded``, and ``_inject_headers`` (semi-private but stable
    across 0.1.x; the ``<0.2`` version pin provides defense-in-depth).

    Args:
        request: The incoming Starlette/FastAPI request that triggered the
            rate limit.
        exc: The :class:`~slowapi.errors.RateLimitExceeded` exception raised
            by slowapi.

    Returns:
        A :class:`~starlette.responses.JSONResponse` with status 429 and a
        ``Retry-After`` header.
    """
    response: Response = JSONResponse(
        {"detail": f"Rate limit exceeded: {exc.detail}"},
        status_code=429,
    )

    # Attempt to inject accurate rate-limit headers (including Retry-After)
    # via slowapi's header-injection helper.  Guarded so we never hard-fail
    # if the state attribute or limiter reference is absent.
    try:
        view_rate_limit = getattr(request.state, "view_rate_limit", None)
        if view_rate_limit is not None:
            response = request.app.state.limiter._inject_headers(response, view_rate_limit)
    except Exception:
        # Storage unreachable or injection failed — fall through to fallback.
        pass

    # Guarantee Retry-After is present even when injection did not set it.
    if "Retry-After" not in response.headers:
        retry_secs: int = _parse_retry_after_seconds(str(exc.detail)) or 60
        response.headers["Retry-After"] = str(retry_secs)

    return response


# Single application-wide Limiter instance.  Registered on ``app.state`` and
# used as a decorator in ``app.api.auth``.
limiter: Limiter = Limiter(key_func=_rate_limit_key)
