from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.buildings import router as buildings_router
from app.api.health import router as health_router
from app.api.members import router as members_router
from app.api.reference import router as reference_router
from app.api.siege_members import router as siege_members_router
from app.api.sieges import router as sieges_router
from app.config import settings

app = FastAPI(
    title="Siege Assignment API",
    version="0.1.0",
    docs_url="/api/docs" if settings.environment == "development" else None,
    redoc_url=None,
)

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
