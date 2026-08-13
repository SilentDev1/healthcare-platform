from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HospitalPriceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    hospital_price_max_bytes: int = Field(750_000_000, gt=0)
    hospital_price_max_expanded_bytes: int = Field(1_500_000_000, gt=0)
    # Ceiling for archives parsed by streaming member bytes on demand (never
    # materialized on disk). Larger than the on-disk cap because streaming keeps
    # memory bounded; still a hard backstop against zip bombs / runaway files.
    hospital_price_max_streaming_expanded_bytes: int = Field(8_000_000_000, gt=0)
    hospital_price_max_archive_files: int = Field(5, ge=1, le=100)
    hospital_price_connection_timeout_seconds: float = Field(15, gt=0, le=120)
    hospital_price_read_timeout_seconds: float = Field(300, gt=0, le=600)
    hospital_price_part_file_suffix: str = ".part"
    hospital_price_max_redirects: int = Field(5, ge=0, le=10)
    hospital_price_http_retries: int = Field(2, ge=0, le=5)
    hospital_price_batch_size: int = Field(500, ge=10, le=5000)
    hospital_price_parser_version: str = "1.0.0"
    hospital_price_user_agent: str = (
        "CareCompare-HPT-Research/1.0 (public hospital transparency client)"
    )
    hospital_price_raw_dir: Path = Path("data/raw/hospital_prices/nh")
    hospital_price_profiling_enabled: bool = False
    hospital_price_profiling_milestone_rows: int = Field(1000, ge=100, le=50000)
    hospital_price_checkpoint_enabled: bool = True
    hospital_price_checkpoint_interval: int = Field(1, ge=1, le=100)


hospital_price_settings = HospitalPriceSettings()
