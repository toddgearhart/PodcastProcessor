from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    data_dir: Path = Path("/data")
    podcast_dir: Path = Path("/podcasts")
    podcast_public_base_url: str = "http://localhost:8081/files/podcasts"
    database_url: str | None = None
    max_upload_mb: int = Field(default=4096, ge=1)

    admin_username: str = "admin"
    admin_password_hash: str = ""
    session_secret: str = "change-me-before-deployment"
    secure_cookies: bool = True

    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"

    wordpress_url: str = ""
    wordpress_username: str = ""
    wordpress_application_password: str = ""
    wordpress_category_id: int | None = None

    whisper_model: str = "medium.en"
    whisper_compute_type: str = "int8"
    whisper_threads: int = Field(default=4, ge=1)

    log_level: str = "INFO"
    worker_poll_seconds: float = Field(default=2.0, ge=0.2)

    @field_validator("podcast_public_base_url", "wordpress_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("wordpress_category_id", mode="before")
    @classmethod
    def blank_category_is_none(cls, value):
        return None if value == "" else value

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'podcast_processor.db'}"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def model_dir(self) -> Path:
        return self.data_dir / "models"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.podcast_dir.mkdir(parents=True, exist_ok=True)

    def validate_runtime(self) -> list[str]:
        issues: list[str] = []
        if not self.admin_password_hash:
            issues.append("ADMIN_PASSWORD_HASH is not configured")
        if self.session_secret == "change-me-before-deployment":
            issues.append("SESSION_SECRET still uses the insecure default")
        if not self.openai_api_key:
            issues.append("OPENAI_API_KEY is not configured")
        if not self.wordpress_url:
            issues.append("WORDPRESS_URL is not configured")
        if not self.wordpress_username or not self.wordpress_application_password:
            issues.append("WordPress credentials are not configured")
        return issues


@lru_cache
def get_settings() -> Settings:
    return Settings()
