from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    discord_bot_api_url: str
    discord_bot_api_key: str
    discord_guild_id: str
    discord_siege_channel: str = "clan-siege-assignments"
    discord_siege_images_channel: str = "clan-siege-assignment-images"
    environment: str = "development"


settings = Settings()
