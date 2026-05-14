"""HTTP client for the Discord bot sidecar API.

Provides async methods for communicating with the Discord bot sidecar over its
internal HTTP API.  The ``sync_day_role`` method additionally implements the
outbound day-role-sync webhook contract defined in
``docs/webhooks/day-role-sync.md``.
"""

import asyncio
import logging
from datetime import datetime
from typing import Literal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class BotClient:
    """HTTP client for the Discord bot sidecar API."""

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=settings.discord_bot_api_url,
            headers={"Authorization": f"Bearer {settings.discord_bot_api_key}"},
            timeout=10.0,
        )

    async def notify(self, username: str, message: str) -> bool:
        """Send DM via bot. Returns True on success, False on error."""
        try:
            async with self._make_client() as client:
                response = await client.post(
                    "/api/notify",
                    json={"username": username, "message": message},
                )
                response.raise_for_status()
                return True
        except httpx.HTTPError:
            return False

    async def post_message(self, channel_name: str, message: str) -> bool:
        """Post text to channel. Returns True on success, False on error."""
        try:
            async with self._make_client() as client:
                response = await client.post(
                    "/api/post-message",
                    json={"channel_name": channel_name, "message": message},
                )
                response.raise_for_status()
                return True
        except httpx.HTTPError:
            return False

    async def post_image(self, channel_name: str, image_bytes: bytes, filename: str) -> str | None:
        """Post image to channel. Returns the CDN URL on success, None on error."""
        try:
            async with httpx.AsyncClient(
                base_url=settings.discord_bot_api_url,
                headers={"Authorization": f"Bearer {settings.discord_bot_api_key}"},
                timeout=30.0,
            ) as client:
                response = await client.post(
                    f"/api/post-image?channel_name={channel_name}",
                    files={"file": (filename, image_bytes, "image/png")},
                )
                response.raise_for_status()
                return response.json()["url"]
        except httpx.HTTPError:
            return None

    async def get_members(self) -> list[dict]:
        """Get guild member list."""
        try:
            async with self._make_client() as client:
                response = await client.get("/api/members")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError:
            return []

    async def get_member(self, discord_user_id: str) -> dict:
        """
        Check guild membership via bot sidecar.
        Returns the member dict (including ``is_member`` boolean).
        Raises ``httpx.HTTPError`` if the sidecar is unreachable or returns
        a non-2xx status.
        """
        async with self._make_client() as client:
            response = await client.get(f"/api/members/{discord_user_id}")
            response.raise_for_status()
            return response.json()

    async def sync_day_role(
        self,
        *,
        discord_id: int | None,
        siege_id: int,
        day_number: int | None,
        action: Literal["set", "clear"],
        assigned_at: datetime,
        correlation_id: str,
    ) -> bool:
        """Fire the outbound day-role-sync webhook for one member assignment.

        Implements the producer side of the contract defined in
        ``docs/webhooks/day-role-sync.md``.

        Short-circuits (no HTTP call, returns ``True``) when:

        - ``DAY_ROLE_SYNC_ENABLED`` is ``false`` (feature flag / kill switch).
        - ``discord_id`` is ``None`` (member has no Discord account linked).

        Returns ``False`` (no retry) when:

        - ``DAY_ROLE_SYNC_URL`` is unset while the feature flag is ``true``.
        - The receiver returns a ``4xx`` response.
        - All retry attempts fail (single retry on ``5xx`` per §5).
        - The receiver returns ``status: "failed"``.

        Returns ``True`` when the receiver responds ``200`` with
        ``status: "applied"``, ``"skipped"``, or ``"partial"`` (partial is a
        soft failure per spec §10 — do not retry, alert operator instead).

        Args:
            discord_id: Discord snowflake integer for the member whose
                assignment changed.  Pass ``None`` to skip the call
                (member has no linked Discord account).
            siege_id: Primary key of the siege record.  Included in the
                payload for receiver-side correlation and audit.
            day_number: Attack-day number (``1`` or ``2``).  Required when
                ``action="set"``; must be ``None`` when ``action="clear"``.
            action: ``"set"`` — member assigned to the day.
                ``"clear"`` — member removed from the day.  Serialized to
                ``"assign"`` / ``"unassign"`` on the wire per §2.
            assigned_at: Tz-aware UTC datetime of the assignment change.
                Serialized with millisecond precision per §2.
            correlation_id: UUID v4 supplied by the caller.  Preserved
                across the internal retry so downstream operators can
                correlate both attempts in logs.

        Returns:
            ``True`` if the webhook was delivered successfully (or
            short-circuited because the feature is disabled / discord_id is
            None).  ``False`` if delivery failed.
        """
        # ------------------------------------------------------------------ #
        # AC1 — feature flag disabled → silent no-op                         #
        # ------------------------------------------------------------------ #
        if not settings.day_role_sync_enabled:
            logger.debug(
                "day_role_sync disabled — skipping webhook call",
                extra={"correlation_id": correlation_id},
            )
            return True

        # ------------------------------------------------------------------ #
        # AC2 — discord_id=None → no payload to send                         #
        # ------------------------------------------------------------------ #
        if discord_id is None:
            logger.info(
                "sync_day_role skipped: discord_id is None " "(correlation_id=%s, siege_id=%s)",
                correlation_id,
                siege_id,
            )
            return True

        # ------------------------------------------------------------------ #
        # AC3 — URL missing while flag is true                                #
        # ------------------------------------------------------------------ #
        sync_url = settings.day_role_sync_url
        if not sync_url:
            logger.warning(
                "DAY_ROLE_SYNC_ENABLED=true but DAY_ROLE_SYNC_URL is unset "
                "or empty — treating day-role-sync as disabled "
                "(correlation_id=%s)",
                correlation_id,
            )
            return False

        # ------------------------------------------------------------------ #
        # Build §2 payload                                                    #
        # ------------------------------------------------------------------ #
        wire_action = "assign" if action == "set" else "unassign"

        # assigned_at must be UTC with millisecond precision (§2 / §7).
        # isoformat(timespec="milliseconds") on a UTC datetime yields the form
        # "2026-05-14T13:52:18.247+00:00"; we normalise the offset to "Z" for
        # readability and spec conformance.
        assigned_at_str = assigned_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")

        payload: dict = {
            "discord_id": str(discord_id),
            "siege_id": siege_id,
            "action": wire_action,
            "assigned_at": assigned_at_str,
            "correlation_id": correlation_id,
        }

        # Include day_number only for "assign" (set) actions per issue #323 AC.
        if action == "set" and day_number is not None:
            payload["day_number"] = day_number

        # ------------------------------------------------------------------ #
        # HTTP call with single 5xx retry (§5)                               #
        # ------------------------------------------------------------------ #
        last_status: int | None = None
        last_body: str = ""

        async with httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {settings.discord_bot_api_key}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        ) as client:
            for attempt in range(1, 3):  # attempts 1 and 2
                try:
                    response = await client.post(sync_url, json=payload)
                    last_status = response.status_code
                    last_body = response.text[:500]
                except httpx.HTTPError as exc:
                    logger.warning(
                        "sync_day_role HTTP error on attempt %d " "(correlation_id=%s): %s",
                        attempt,
                        correlation_id,
                        exc,
                    )
                    if attempt == 1:
                        await asyncio.sleep(0.5)
                        continue
                    return False

                if response.is_success:
                    return self._handle_sync_response(response, correlation_id)

                if 400 <= last_status < 500:
                    # 4xx — client error, no retry per §5.
                    logger.warning(
                        "sync_day_role 4xx on attempt %d "
                        "(correlation_id=%s, status=%d, body=%.200s)",
                        attempt,
                        correlation_id,
                        last_status,
                        last_body,
                    )
                    return False

                # 5xx — retry once.
                if attempt == 1:
                    logger.warning(
                        "sync_day_role 5xx on attempt 1 — retrying after 500ms "
                        "(correlation_id=%s, status=%d)",
                        correlation_id,
                        last_status,
                    )
                    await asyncio.sleep(0.5)
                    continue

        # ------------------------------------------------------------------ #
        # Retry exhausted — observability per §5 SHOULD                       #
        # ------------------------------------------------------------------ #
        logger.warning(
            "sync_day_role retry exhausted — delivery dropped "
            "(correlation_id=%s, discord_id=%s, siege_id=%s, "
            "action=%s, last_status=%s, last_body=%.200s)",
            correlation_id,
            discord_id,
            siege_id,
            wire_action,
            last_status,
            last_body,
        )
        return False

    @staticmethod
    def _handle_sync_response(
        response: httpx.Response,
        correlation_id: str,
    ) -> bool:
        """Parse a 200 day-role-sync response body and return success flag.

        Logs an INFO line for applied/skipped, WARNING for partial/failed.
        Returns ``True`` for applied/skipped/partial; ``False`` for failed.

        Args:
            response: The 200 httpx.Response from the receiver.
            correlation_id: UUID propagated from the originating call for log
                correlation.

        Returns:
            ``True`` when status is ``"applied"``, ``"skipped"``, or
            ``"partial"``.  ``False`` when status is ``"failed"``.
        """
        try:
            body = response.json()
        except Exception:
            logger.warning(
                "sync_day_role: failed to parse response JSON " "(correlation_id=%s, body=%.200s)",
                correlation_id,
                response.text[:200],
            )
            return False

        status = body.get("status", "")
        reason = body.get("reason")
        added = body.get("added", [])
        removed = body.get("removed", [])

        if status == "applied":
            logger.info(
                "sync_day_role applied " "(correlation_id=%s, added=%s, removed=%s)",
                correlation_id,
                added,
                removed,
            )
            return True

        if status == "skipped":
            logger.info(
                "sync_day_role skipped " "(correlation_id=%s, reason=%s)",
                correlation_id,
                reason,
            )
            return True

        if status == "partial":
            logger.warning(
                "sync_day_role partial — operator investigation required "
                "(correlation_id=%s, reason=%s, added=%s, removed=%s)",
                correlation_id,
                reason,
                added,
                removed,
            )
            return True

        if status == "failed":
            logger.warning(
                "sync_day_role failed " "(correlation_id=%s, reason=%s)",
                correlation_id,
                reason,
            )
            return False

        logger.warning(
            "sync_day_role: unrecognised status %r " "(correlation_id=%s)",
            status,
            correlation_id,
        )
        return False


bot_client = BotClient()
