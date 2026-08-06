from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    cms_hospitals_source_url: str = (
        "https://data.cms.gov/provider-data/sites/default/files/resources/"
        "893c372430d9d71a1c52737d01239d47_1777413958/"
        "Hospital_General_Information.csv"
    )
    cms_download_max_bytes: int = Field(104_857_600, gt=0)
    cms_http_timeout_seconds: float = Field(60, gt=0, le=300)
    cms_http_max_retries: int = Field(3, ge=0, le=10)
    cms_parser_version: str = "1.0.0"
    cms_raw_data_dir: Path = Path("data/raw/cms_hospitals")
    cms_rejected_data_dir: Path = Path("data/rejected/cms_hospitals")


collector_settings = CollectorSettings()
