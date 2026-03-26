import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.discord_client import SiegeBot

_VERSION_FILE = Path(__file__).parent.parent / "VERSION"

app = FastAPI(title="Siege Bot HTTP API", version="0.1.0")

_bearer_scheme = HTTPBearer()

_bot: SiegeBot | None = None


def set_bot(bot: SiegeBot) -> None:
    global _bot
    _bot = bot


def _get_bot() -> SiegeBot:
    if _bot is None or not _bot.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not connected",
        )
    return _bot


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> None:
    """Validate the Bearer token against the configured bot API key."""
    if credentials.credentials != settings.bot_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


class NotifyRequest(BaseModel):
    username: str
    message: str


class PostMessageRequest(BaseModel):
    channel_name: str
    message: str


@app.get("/version")
async def version() -> dict[str, str]:
    """Return the bot version — no authentication required.

    Returns ``1.0.1+42.abc1234`` when BUILD_NUMBER and GIT_SHA are present
    (i.e. in a CI-built image), or just the bare semver in local development.
    """
    try:
        semver = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        semver = "unknown"
    build_number = os.environ.get("BUILD_NUMBER", "unknown")
    git_sha = os.environ.get("GIT_SHA", "unknown")
    if build_number != "unknown" and git_sha != "unknown":
        ver = f"{semver}+{build_number}.{git_sha[:7]}"
    else:
        ver = semver
    return {"version": ver}


@app.get("/api/health")
async def health() -> dict:
    """Health check — no authentication required."""
    return {"status": "healthy", "bot_connected": _bot is not None and _bot.is_ready()}


@app.post("/api/notify")
async def notify(
    body: NotifyRequest,
    _: None = Depends(verify_api_key),
) -> dict[str, str]:
    """Send a DM notification to a guild member."""
    bot = _get_bot()
    try:
        await bot.send_dm(body.username, body.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"status": "sent"}


@app.post("/api/post-message")
async def post_message(
    body: PostMessageRequest,
    _: None = Depends(verify_api_key),
) -> dict[str, str]:
    """Post a text message to a guild channel."""
    bot = _get_bot()
    try:
        await bot.post_message(body.channel_name, body.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"status": "sent"}


@app.post("/api/post-image")
async def post_image(
    channel_name: str,
    file: UploadFile,
    _: None = Depends(verify_api_key),
) -> dict[str, str]:
    """Post an image to a guild channel."""
    bot = _get_bot()
    image_bytes = await file.read()
    try:
        url = await bot.post_image(channel_name, image_bytes, file.filename or "image.png")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"status": "sent", "url": url}


@app.get("/api/members")
async def get_members(
    _: None = Depends(verify_api_key),
) -> list[dict]:
    """Retrieve guild member list."""
    bot = _get_bot()
    return await bot.get_members()
