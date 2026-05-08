"""Response schemas for the changelog endpoints."""

import datetime

from pydantic import BaseModel


class ChangelogStatusResponse(BaseModel):
    """Response shape for both GET /changelog/status and POST /changelog/mark-seen.

    Attributes:
        last_seen_changelog_at: UTC timestamp of when the user last dismissed
            the changelog, or None if they have never done so.
    """

    last_seen_changelog_at: datetime.datetime | None
