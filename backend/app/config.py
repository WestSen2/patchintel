"""Application settings, loaded from environment / .env file.

Secrets (STEAM_API_KEY, OPENAI_API_KEY) live ONLY in backend/.env,
which is gitignored. Never hardcode them here.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite for zero-setup local dev; Postgres via docker compose for "real" runs.
    database_url: str = "sqlite:///./patchintel.db"

    # Steam Web API key -> https://steamcommunity.com/dev/apikey
    steam_api_key: str = ""

    # Community Deadlock API (key optional, raises rate limits)
    deadlock_api_base: str = "https://api.deadlock-api.com"
    deadlock_api_key: str = ""

    # OpenAI for patch summarization (pipeline runs without it via NullSummarizer)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    app_secret_key: str = "dev-only-change-me"
    # Public base URL of the app — Steam OpenID realm/return_to.
    # Local dev default; set to https://your.domain in production.
    app_base_url: str = "http://localhost:8000"

    # Demo mode: serve fabricated data banner (deployed previews)
    demo_mode: bool = False

    # Comma-separated allowed CORS origins (frontend dev server + deploy)
    cors_origins: str = "http://localhost:5173"

    # Poller cadence (hours)
    patch_poll_interval_hours: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
