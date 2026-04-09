from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    discord_bot_api_url: str
    discord_bot_api_key: str
    discord_guild_id: str
    discord_siege_channel: str = "clan-siege-assignments"
    discord_siege_images_channel: str = "clan-siege-assignment-images"

    # ENVIRONMENT must be explicitly set — no default so misconfigured deployments fail fast.
    environment: str

    # Discord OAuth2 — empty defaults so existing envs without these vars still start.
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = ""

    # HS256 signing key for JWTs — empty default; rotate in production.
    session_secret: str = ""

    # Bearer token for bot→backend calls; empty string disables the check.
    bot_service_token: str = ""

    # Dev-only auth bypass — startup guard rejects True outside development.
    auth_disabled: bool = False


settings = Settings()

JWT_ALGORITHM = "HS256"
