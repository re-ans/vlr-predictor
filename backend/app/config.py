"""Centralised application settings, loaded from environment / .env.

Everything reads configuration from here so there is a single source of truth
and secrets never get hard-coded. The repo-root .env is loaded automatically.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is two levels up from this file: backend/app/config.py -> repo/
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PandaScore
    pandascore_token: str = Field(default="", alias="PANDASCORE_TOKEN")
    pandascore_base_url: str = Field(
        default="https://api.pandascore.co", alias="PANDASCORE_BASE_URL"
    )

    # vlrggapi (local self-hosted fork)
    vlrggapi_base_url: str = Field(
        default="http://127.0.0.1:3001", alias="VLRGGAPI_BASE_URL"
    )

    # Postgres
    database_url: str = Field(default="", alias="DATABASE_URL")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Auth
    jwt_secret: str = Field(default="dev-insecure-change-me", alias="JWT_SECRET")
    jwt_expire_minutes: int = Field(default=60 * 24 * 7, alias="JWT_EXPIRE_MINUTES")

    # Frontend (CORS)
    frontend_url: str = Field(default="", alias="FRONTEND_URL")

    # Scope
    ingest_regions: str = Field(default="", alias="INGEST_REGIONS")

    @property
    def ingest_region_list(self) -> list[str]:
        return [r.strip().lower() for r in self.ingest_regions.split(",") if r.strip()]


settings = Settings()
