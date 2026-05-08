"""Changelog status and mark-seen endpoints.

These endpoints let the frontend track whether a user has seen the latest
changelog and let it mark the changelog as viewed.  Service principals
(bot Bearer tokens) do not have a per-user row and therefore cannot use
these endpoints — calls from a service token receive HTTP 400.
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.models.member import Member
from app.schemas.changelog import ChangelogStatusResponse

router = APIRouter()

_SERVICE_PRINCIPAL_DETAIL = "endpoint requires a user session"


def _require_member_session(current_user: AuthenticatedUser) -> None:
    """Raise HTTP 400 if the caller is a service principal.

    Args:
        current_user: The resolved identity from the auth dependency.

    Raises:
        HTTPException: 400 when ``current_user.member_id`` is None (i.e. the
            caller authenticated via a service Bearer token rather than a
            browser session cookie).
    """
    if current_user.member_id is None:
        raise HTTPException(
            status_code=400,
            detail=_SERVICE_PRINCIPAL_DETAIL,
        )


@router.get("/changelog/status", response_model=ChangelogStatusResponse)
async def get_changelog_status(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangelogStatusResponse:
    """Return the authenticated user's last-seen changelog timestamp.

    Args:
        current_user: Resolved from the session cookie.
        db: Injected async database session.

    Returns:
        A ``ChangelogStatusResponse`` with ``last_seen_changelog_at`` set to
        the stored UTC timestamp, or ``None`` if the user has never dismissed
        the changelog.

    Raises:
        HTTPException: 400 if the caller is a service principal.
    """
    _require_member_session(current_user)
    member: Member | None = await db.get(Member, current_user.member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return ChangelogStatusResponse(last_seen_changelog_at=member.last_seen_changelog_at)


@router.post("/changelog/mark-seen", response_model=ChangelogStatusResponse)
async def mark_changelog_seen(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangelogStatusResponse:
    """Set the authenticated user's last-seen changelog timestamp to now.

    Idempotent — calling multiple times is safe; each call simply overwrites
    the previous timestamp with the current UTC time.

    Args:
        current_user: Resolved from the session cookie.
        db: Injected async database session.

    Returns:
        A ``ChangelogStatusResponse`` with the newly written timestamp.

    Raises:
        HTTPException: 400 if the caller is a service principal.
        HTTPException: 404 if the member row no longer exists.
    """
    _require_member_session(current_user)
    member: Member | None = await db.get(Member, current_user.member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    member.last_seen_changelog_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    await db.commit()
    return ChangelogStatusResponse(last_seen_changelog_at=member.last_seen_changelog_at)
