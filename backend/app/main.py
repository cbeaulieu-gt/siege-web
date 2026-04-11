import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.attack_day import router as attack_day_router
from app.api.auth import router as auth_router
from app.api.autofill import router as autofill_router
from app.api.board import router as board_router
from app.api.buildings import router as buildings_router
from app.api.comparison import router as comparison_router
from app.api.config import router as config_router
from app.api.discord_sync import router as discord_sync_router
from app.api.health import router as health_router
from app.api.images import router as images_router
from app.api.lifecycle import router as lifecycle_router
from app.api.members import router as members_router
from app.api.notifications import router as notifications_router
from app.api.post_priority_config import router as post_priority_config_router
from app.api.posts import router as posts_router
from app.api.reference import router as reference_router
from app.api.siege_members import router as siege_members_router
from app.api.sieges import router as sieges_router
from app.api.validation import router as validation_router
from app.api.version import router as version_router
from app.config import settings
from app.dependencies.auth import get_current_user
from app.middleware import RequestLoggingMiddleware
from app.telemetry import configure_telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

configure_telemetry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs startup guards before serving requests."""
    if settings.auth_disabled and settings.environment != "development":
        raise RuntimeError(
            "AUTH_DISABLED=true is not permitted outside development. "
            f"Current environment: {settings.environment}"
        )
    if not settings.auth_disabled:
        if not settings.session_secret or "changeme" in settings.session_secret.lower():
            raise RuntimeError(
                "SESSION_SECRET must be set to a secure random value when auth is enabled. "
                f"Current environment: {settings.environment}"
            )
        if settings.environment != "development" and not settings.bot_service_token:
            raise RuntimeError(
                "BOT_SERVICE_TOKEN must be set in non-development environments. "
                f"Current environment: {settings.environment}"
            )
    yield


app = FastAPI(
    title="Siege Assignment API",
    version="0.1.0",
    docs_url="/api/docs" if settings.environment == "development" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes — no auth required
app.include_router(health_router, prefix="/api")
app.include_router(version_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(auth_router, prefix="/api")

# Protected routes — require authentication
_auth_deps = [Depends(get_current_user)]
app.include_router(reference_router, prefix="/api", dependencies=_auth_deps)
app.include_router(discord_sync_router, prefix="/api", dependencies=_auth_deps)
app.include_router(members_router, prefix="/api", dependencies=_auth_deps)
app.include_router(sieges_router, prefix="/api", dependencies=_auth_deps)
app.include_router(buildings_router, prefix="/api", dependencies=_auth_deps)
app.include_router(siege_members_router, prefix="/api", dependencies=_auth_deps)
app.include_router(board_router, prefix="/api", dependencies=_auth_deps)
app.include_router(lifecycle_router, prefix="/api", dependencies=_auth_deps)
app.include_router(posts_router, prefix="/api", dependencies=_auth_deps)
app.include_router(validation_router, prefix="/api", dependencies=_auth_deps)
app.include_router(autofill_router, prefix="/api", dependencies=_auth_deps)
app.include_router(comparison_router, prefix="/api", dependencies=_auth_deps)
app.include_router(attack_day_router, prefix="/api", dependencies=_auth_deps)
app.include_router(images_router, prefix="/api", dependencies=_auth_deps)
app.include_router(notifications_router, prefix="/api", dependencies=_auth_deps)
app.include_router(post_priority_config_router, prefix="/api", dependencies=_auth_deps)
