from pydantic import BaseModel


class VersionResponse(BaseModel):
    backend_version: str
    bot_version: str | None  # None if bot is unreachable
    frontend_version: str | None  # passed in from FRONTEND_VERSION env var
    git_sha: str | None
