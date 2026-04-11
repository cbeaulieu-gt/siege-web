"""Public config endpoint — exposes non-sensitive runtime flags to the frontend."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/config")
async def get_config() -> dict:
    """Return public runtime configuration flags.

    This endpoint is intentionally unauthenticated so the frontend can read
    flags (e.g. ``auth_disabled``) before the user has logged in.
    """
    return {
        "auth_disabled": settings.auth_disabled,
    }
