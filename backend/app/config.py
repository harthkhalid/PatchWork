from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Patchwork"
    debug: bool = False

    # GitHub App
    github_app_id: str = ""
    github_webhook_secret: str = ""
    github_private_key: str = ""  # PEM content or path via GITHUB_PRIVATE_KEY_PATH
    github_private_key_path: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    github_app_slug: str = "patchwork-ai"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # SQLite
    database_url: str = "sqlite+aiosqlite:///./patchwork.db"

    # Public URL for GitHub (webhooks, install redirects)
    public_base_url: str = "http://localhost:8000"

    # Rate limits (requests per minute per installation)
    github_api_rpm: int = 60
    openai_rpm: int = 30

    # Prompt
    active_prompt_version: str = "v2"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def resolve_private_key(settings: Settings) -> str:
    if settings.github_private_key.strip():
        return settings.github_private_key.replace("\\n", "\n")
    if settings.github_private_key_path:
        p = Path(settings.github_private_key_path)
        return p.read_text(encoding="utf-8")
    return ""
