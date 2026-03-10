from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SF_TRACKING_",
        extra="ignore",
    )

    app_name: str = "SF Express Tracking Dashboard"
    api_prefix: str = "/api"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "data")
    upload_dir: Path | None = None
    database_path: Path | None = None
    frontend_dist_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / "frontend" / "dist"
    )
    export_dir: Path | None = None
    enable_scheduler: bool = True
    default_language: str = "zh-CN"
    request_timeout_seconds: int = 30
    upload_preview_rows: int = 100
    upload_max_size_mb: int = 20
    frontend_origin: str = "http://127.0.0.1:5173"

    def model_post_init(self, __context: object) -> None:
        if self.upload_dir is None:
            self.upload_dir = self.data_dir / "uploads"
        if self.database_path is None:
            self.database_path = self.data_dir / "app.db"
        if self.export_dir is None:
            self.export_dir = self.data_dir / "exports"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    @property
    def app_settings_path(self) -> Path:
        return self.data_dir / "app_settings.json"

    @property
    def export_presets_path(self) -> Path:
        return self.data_dir / "export_presets.json"

    @property
    def dev_cipher_key_path(self) -> Path:
        return self.data_dir / ".cipher.key"

    @property
    def alembic_ini_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "alembic.ini"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
