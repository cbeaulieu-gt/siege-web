import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.attack_day import router as attack_day_router
from app.api.autofill import router as autofill_router
from app.api.board import router as board_router
from app.api.buildings import router as buildings_router
from app.api.comparison import router as comparison_router
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
from app.config import settings
from app.middleware import RequestLoggingMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="Siege Assignment API",
    version="0.1.0",
    docs_url="/api/docs" if settings.environment == "development" else None,
    redoc_url=None,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(reference_router, prefix="/api")
app.include_router(members_router, prefix="/api")
app.include_router(sieges_router, prefix="/api")
app.include_router(buildings_router, prefix="/api")
app.include_router(siege_members_router, prefix="/api")
app.include_router(board_router, prefix="/api")
app.include_router(lifecycle_router, prefix="/api")
app.include_router(posts_router, prefix="/api")
app.include_router(validation_router, prefix="/api")
app.include_router(autofill_router, prefix="/api")
app.include_router(comparison_router, prefix="/api")
app.include_router(attack_day_router, prefix="/api")
app.include_router(images_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(post_priority_config_router, prefix="/api")
