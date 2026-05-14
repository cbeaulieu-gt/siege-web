"""Internal helper: schedule outbound day-role-sync webhook calls.

This module encapsulates all caller-side invariants for the day-role-sync
webhook contract defined in ``docs/webhooks/day-role-sync.md``.

It is intentionally thin — all HTTP mechanics, retry logic, and response
parsing live in ``BotClient.sync_day_role()``.  This layer handles only
the caller-side concerns:

- Feature gate (``DAY_ROLE_SYNC_ENABLED``) checked before scheduling.
- ``discord_id=None`` filter with an INFO log.
- ``assigned_at`` generation with strict monotonicity across fan-out
  calls: each call to ``next_assigned_at()`` returns a value strictly
  greater than the previous one, even when two calls fall within the
  same millisecond.
- ``correlation_id`` is generated once per user action by the caller;
  this module never generates it.

Usage::

    from app.api._role_sync import next_assigned_at, schedule_role_sync
    import uuid

    correlation_id = str(uuid.uuid4())

    for member in affected_members:
        schedule_role_sync(
            background_tasks,
            discord_id=member.discord_id,
            siege_id=siege_id,
            day_number=member.attack_day,
            action="assign",
            assigned_at=next_assigned_at(),
            correlation_id=correlation_id,
        )
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import BackgroundTasks

from app.config import settings
from app.services.bot_client import bot_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level monotonic state — tracks the last timestamp emitted so that
# successive calls within the same millisecond still produce strictly
# increasing values.
# ---------------------------------------------------------------------------
_ONE_MS = timedelta(milliseconds=1)
_last_assigned_at: datetime | None = None


def next_assigned_at() -> datetime:
    """Return a UTC-aware datetime, strictly greater than the previous call.

    Provides millisecond precision (contract §2).  When two calls happen
    within the same millisecond, the second call increments by 1 ms so
    the strict-monotonicity invariant (contract §7) is preserved across
    a fan-out batch.

    Thread safety: this function is intentionally single-threaded (FastAPI
    runs route handlers in the same event loop thread).  If concurrent
    access becomes a requirement, wrap the state update in a lock.

    Returns:
        A UTC-aware ``datetime`` with sub-millisecond precision zeroed,
        strictly greater than the value returned by the previous call.
    """
    global _last_assigned_at  # noqa: PLW0603

    wall_ns = time.time_ns()
    # Truncate to millisecond boundary.
    wall_ms = wall_ns // 1_000_000
    wall_us = wall_ms * 1_000  # microseconds, sub-ms zeroed
    candidate = datetime.fromtimestamp(wall_us / 1_000_000, tz=UTC)

    if _last_assigned_at is not None and candidate <= _last_assigned_at:
        # Same millisecond (or rare clock regression): bump by 1 ms.
        candidate = _last_assigned_at + _ONE_MS

    _last_assigned_at = candidate
    return candidate


def schedule_role_sync(
    background_tasks: BackgroundTasks,
    *,
    discord_id: str | None,
    siege_id: int,
    day_number: int | None,
    action: Literal["assign", "unassign"],
    assigned_at: datetime,
    correlation_id: str,
) -> None:
    """Schedule a fire-and-forget webhook call via FastAPI BackgroundTasks.

    The HTTP response to the operator is sent before the webhook fires.
    This function applies the feature gate and discord_id filter so that
    ``BotClient.sync_day_role`` receives only valid, gate-enabled calls.

    Args:
        background_tasks: FastAPI ``BackgroundTasks`` from the route handler.
        discord_id: Discord snowflake string for the member.  Pass ``None``
            or empty string to skip (member has no linked Discord account).
            Logged at INFO when skipped.
        siege_id: Primary key of the siege record.
        day_number: Attack-day number (``1`` or ``2``).  Required when
            ``action="assign"``; should be ``None`` when
            ``action="unassign"`` (client omits it from the payload).
        action: ``"assign"`` — member placed on a day.
            ``"unassign"`` — member removed from a day.
        assigned_at: UTC-aware datetime for the assignment change.  Must be
            strictly greater than the previous call's value for the same
            ``discord_id`` within a fan-out batch.  Use ``next_assigned_at()``
            to satisfy the monotonicity invariant automatically.
        correlation_id: UUID v4 generated once per user action.  Shared
            across all calls in a fan-out batch (contract §8).

    Returns:
        None.  The call is always fire-and-forget.
    """
    if not settings.day_role_sync_enabled:
        # Feature gate closed — suppress all scheduling silently.
        # BotClient.sync_day_role() also checks this flag, but checking here
        # avoids even enqueuing the background task.
        return

    if not discord_id:
        # discord_id is None or empty string — skip per contract §10.
        # BotClient also handles this, but filtering here avoids scheduling
        # a no-op background task and gives a caller-layer log entry.
        logger.info(
            "role_sync skipped: discord_id is None or empty "
            "(siege_id=%s, correlation_id=%s, action=%s)",
            siege_id,
            correlation_id,
            action,
        )
        return

    # ``discord_id`` on the Member model is a ``str | None``.  BotClient
    # accepts ``int | None`` in its type signature but does ``str(discord_id)``
    # internally, so passing the string directly is correct and avoids an
    # unnecessary int() cast that could raise on non-numeric strings.
    background_tasks.add_task(
        bot_client.sync_day_role,
        discord_id=discord_id,  # type: ignore[arg-type]
        siege_id=siege_id,
        day_number=day_number,
        action=action,
        assigned_at=assigned_at,
        correlation_id=correlation_id,
    )
