from enum import StrEnum
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    BETA = "beta"
    PRODUCTION = "production"


class RuntimeSettings(BaseSettings):
    """Shared runtime contract. Beta/production never inherit development defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: AppEnvironment = AppEnvironment.LOCAL
    app_version: str = "dev"
    public_app_url: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000"
    database_url: str = (
        "postgresql+psycopg://carecompare:carecompare_local_only@localhost:5432/carecompare"
    )
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    log_level: str = "INFO"
    data_dir: Path = Path("data")
    source_download_dir: Path = Path("data/raw/hospital_prices")
    source_storage_bucket: str | None = None
    # Carevero-controlled bucket for verified facility imagery (state-neutral).
    facility_media_bucket: str | None = None
    # Public base URL used to build image URLs for objects in the media bucket.
    facility_media_public_base_url: str | None = None
    scheduler_enabled: bool = False
    beta_mode: bool = False
    seo_indexing_enabled: bool = True
    feedback_enabled: bool = False
    beta_feedback_email: str | None = None
    public_map_enabled: bool = True
    public_pricing_enabled: bool = True
    admin_api_enabled: bool = True
    admin_shared_secret: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 2
    db_pool_recycle_seconds: int = 1800
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    max_query_string_bytes: int = 4096
    max_request_body_bytes: int = 1_048_576
    http_timeout_seconds: float = 15.0

    @field_validator("public_app_url", "api_public_url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def is_deployed(self) -> bool:
        return self.app_env in {AppEnvironment.BETA, AppEnvironment.PRODUCTION}

    @property
    def origins(self) -> list[str]:
        return [value.strip().rstrip("/") for value in self.allowed_origins.split(",") if value]

    @property
    def hosts(self) -> list[str]:
        return [value.strip() for value in self.trusted_hosts.split(",") if value]

    @model_validator(mode="after")
    def validate_deployed_environment(self) -> "RuntimeSettings":
        if not self.is_deployed:
            return self
        errors: list[str] = []
        parsed_database_url = urlparse(
            self.database_url.replace("postgresql+psycopg", "postgresql")
        )
        db_host = (parsed_database_url.hostname or "").lower()
        db_socket = parse_qs(parsed_database_url.query).get("host", [""])[0]
        uses_cloud_sql_socket = db_socket.startswith("/cloudsql/")
        if db_host in {"", "localhost", "127.0.0.1", "::1", "test", "postgres"} and not (
            db_host == "" and uses_cloud_sql_socket
        ):
            errors.append("DATABASE_URL must reference an isolated non-local database")
        for name, value in (
            ("PUBLIC_APP_URL", self.public_app_url),
            ("API_PUBLIC_URL", self.api_public_url),
        ):
            parsed = urlparse(value)
            if parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1"}:
                errors.append(f"{name} must be a non-local HTTPS URL")
        if not self.origins or "*" in self.origins:
            errors.append("ALLOWED_ORIGINS must be an explicit non-wildcard list")
        if not self.hosts or "*" in self.hosts:
            errors.append("TRUSTED_HOSTS must be an explicit non-wildcard list")
        if self.admin_api_enabled and not self.admin_shared_secret:
            errors.append("ADMIN_SHARED_SECRET is required when ADMIN_API_ENABLED=true")
        if self.feedback_enabled and not self.beta_feedback_email:
            errors.append("BETA_FEEDBACK_EMAIL is required when FEEDBACK_ENABLED=true")
        if not self.source_storage_bucket:
            errors.append("SOURCE_STORAGE_BUCKET is required for durable source storage")
        if self.source_download_dir.as_posix().startswith("data/fixtures"):
            errors.append("SOURCE_DOWNLOAD_DIR cannot be a fixture directory")
        if errors:
            raise ValueError("invalid deployed configuration: " + "; ".join(errors))
        return self


runtime_settings = RuntimeSettings()
