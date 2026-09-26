"""Runtime settings for the local bank lab."""

from __future__ import annotations

import secrets
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from ``BANK_LAB_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BANK_LAB_",
        extra="ignore",
    )

    app_name: str = "Example Bank Lab"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./runtime/bank_lab.db"
    session_pepper: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    cookie_secure: bool = False
    session_idle_minutes: int = 30
    session_absolute_hours: int = 8
    login_failure_limit: int = 5
    login_window_minutes: int = 5
    login_block_minutes: int = 5
    auto_create_schema: bool = False
    templates_dir: Path = Path("templates")
    run_id: str = "BASELINE"
    scenario_id: str | None = None

    @model_validator(mode="after")
    def validate_secure_mode(self) -> Settings:
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("production requires secure cookies")
        if self.scenario_id is not None and self.environment != "scenario":
            raise ValueError("scenario_id is allowed only in an isolated scenario environment")
        return self
