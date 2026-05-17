"""FastAPI dependency for request authentication.

Checks three paths in order:
1. AUTH_DISABLED=true (development only) → stub user
2. Authorization: Bearer <token> → service principal
3. Cookie: session=<jwt> → authenticated user
4. Otherwise → HTTP 401

The ``get_acting_member_id`` dependency extends service-token auth with an
optional ``X-Acting-Discord-Id`` header that allows the bot to act on behalf
of a specific member for ``/me/*`` endpoints.
"""

import secrets
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import JWT_ALGORITHM, settings
from app.db.session import get_db
from app.models.member import Member


@dataclass
class AuthenticatedUser:
    """Represents the currently authenticated user or service principal.

    Attributes:
        member_id: Database PK of the authenticated member; ``None`` for
            service-token principals.
        name: Display name of the authenticated entity.
        is_service: ``True`` when authenticated via Bearer service token.
        role: Member role string, or ``None`` for service principals.
        discord_id: Discord snowflake string of the authenticated member,
            or ``None`` for service principals.
        acting_member_id: Resolved database PK of the member named by the
            ``X-Acting-Discord-Id`` header on service-token requests.  Always
            ``None`` for cookie-authenticated users and for service-token
            requests that omit the header.
    """

    member_id: int | None
    name: str
    is_service: bool
    role: str | None = None
    discord_id: str | None = None
    acting_member_id: int | None = None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:
    """Resolve the caller's identity from the incoming request.

    Tries three mechanisms in priority order: dev bypass flag, Bearer token
    for service-to-service calls, and a signed JWT session cookie for
    browser-based users.

    For service-token requests, the optional ``X-Acting-Discord-Id`` header
    is consulted.  When present, the named Discord ID is resolved to a Member
    record and stored in ``acting_member_id``; the header is silently ignored
    on cookie-authenticated requests (cookie wins).

    Args:
        request: The incoming FastAPI/Starlette request object.
        db: Async SQLAlchemy session injected by ``get_db``.

    Returns:
        An ``AuthenticatedUser`` describing the verified caller.

    Raises:
        HTTPException: 404 when ``X-Acting-Discord-Id`` is present but names
            an unknown Discord user.  401 when no valid credential is found.
    """
    # 1. Dev bypass — only permitted when ENVIRONMENT=development
    if settings.auth_disabled:
        return AuthenticatedUser(member_id=None, name="dev-user", is_service=False)

    # 2. Service token (Bearer) — timing-safe comparison prevents timing attacks
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and settings.bot_service_token:
        provided = auth_header.removeprefix("Bearer ")
        if secrets.compare_digest(provided, settings.bot_service_token):
            acting_discord_id = request.headers.get("X-Acting-Discord-Id")
            acting_member_id: int | None = None
            if acting_discord_id is not None:
                if not acting_discord_id.isdigit() or len(acting_discord_id) > 20:
                    raise HTTPException(
                        status_code=400,
                        detail="X-Acting-Discord-Id must be a numeric Discord snowflake",
                    )
                result = await db.execute(
                    select(Member).where(Member.discord_id == acting_discord_id)
                )
                acting_member = result.scalar_one_or_none()
                if acting_member is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Acting Discord user not found",
                    )
                acting_member_id = acting_member.id
            return AuthenticatedUser(
                member_id=None,
                name="bot-service",
                is_service=True,
                acting_member_id=acting_member_id,
                discord_id=acting_discord_id,
            )

    # 3. User session cookie — decode JWT and look up the member record.
    #    X-Acting-Discord-Id is intentionally ignored here; the cookie's
    #    member_id is the authoritative subject.
    session_token = request.cookies.get("session")
    if session_token:
        try:
            payload = jwt.decode(session_token, settings.session_secret, algorithms=[JWT_ALGORITHM])
            member = await db.get(Member, int(payload["sub"]))
            if member:
                return AuthenticatedUser(
                    member_id=member.id,
                    name=member.name,
                    is_service=False,
                    role=member.role.value if member.role else None,
                    discord_id=member.discord_id,
                )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError):
            pass

    raise HTTPException(status_code=401, detail="Not authenticated")


async def get_acting_member_id(
    user: AuthenticatedUser = Depends(get_current_user),
) -> int:
    """Resolve the subject member ID for ``/me/*`` endpoints.

    Cookie-authenticated requests resolve to the session member's ID.
    Service-token requests resolve to the member named by the
    ``X-Acting-Discord-Id`` header.  A service-token request without the
    header is rejected with 401 because there is no unambiguous subject.

    Args:
        user: The verified caller returned by ``get_current_user``.

    Returns:
        The database primary key of the acting member.

    Raises:
        HTTPException: 401 when the caller is a service principal without an
            ``X-Acting-Discord-Id`` header.
    """
    if user.member_id is not None:
        return user.member_id
    if user.acting_member_id is not None:
        return user.acting_member_id
    raise HTTPException(status_code=401, detail="Acting subject required")
