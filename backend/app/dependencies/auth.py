"""FastAPI dependency for request authentication.

Checks three paths in order:
1. AUTH_DISABLED=true (development only) → stub user
2. Authorization: Bearer <token> → service principal
3. Cookie: session=<jwt> → authenticated user
4. Otherwise → HTTP 401
"""

import secrets
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models.member import Member


@dataclass
class AuthenticatedUser:
    """Represents the currently authenticated user or service principal."""

    member_id: int | None
    name: str
    is_service: bool


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:
    """Resolve the caller's identity from the incoming request.

    Tries three mechanisms in priority order: dev bypass flag, Bearer token
    for service-to-service calls, and a signed JWT session cookie for
    browser-based users.
    """
    # 1. Dev bypass — only permitted when ENVIRONMENT=development (startup guard enforces this)
    if settings.auth_disabled:
        return AuthenticatedUser(member_id=None, name="dev-user", is_service=False)

    # 2. Service token (Bearer) — timing-safe comparison prevents timing attacks
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and settings.bot_service_token:
        provided = auth_header.removeprefix("Bearer ")
        if secrets.compare_digest(provided, settings.bot_service_token):
            return AuthenticatedUser(member_id=None, name="bot-service", is_service=True)

    # 3. User session cookie — decode JWT and look up the member record
    session_token = request.cookies.get("session")
    if session_token:
        try:
            payload = jwt.decode(
                session_token, settings.session_secret, algorithms=["HS256"]
            )
            member = await db.get(Member, int(payload["sub"]))
            if member:
                return AuthenticatedUser(
                    member_id=member.id, name=member.name, is_service=False
                )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError):
            pass

    raise HTTPException(status_code=401, detail="Not authenticated")
