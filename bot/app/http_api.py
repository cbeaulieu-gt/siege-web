from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

app = FastAPI(title="Siege Bot HTTP API", version="0.1.0")

_bearer_scheme = HTTPBearer()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> None:
    """Validate the Bearer token against the configured bot API key."""
    if credentials.credentials != settings.bot_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check — no authentication required."""
    return {"status": "healthy"}


@app.post("/api/notify", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def notify(_: None = Depends(verify_api_key)) -> dict[str, str]:
    """Send a DM notification to a guild member. Not yet implemented."""
    return {"detail": "Not Implemented"}


@app.post("/api/post-message", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def post_message(_: None = Depends(verify_api_key)) -> dict[str, str]:
    """Post a text message to a guild channel. Not yet implemented."""
    return {"detail": "Not Implemented"}


@app.post("/api/post-image", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def post_image(_: None = Depends(verify_api_key)) -> dict[str, str]:
    """Post an image to a guild channel. Not yet implemented."""
    return {"detail": "Not Implemented"}


@app.get("/api/members", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_members(_: None = Depends(verify_api_key)) -> dict[str, str]:
    """Retrieve guild member list. Not yet implemented."""
    return {"detail": "Not Implemented"}
