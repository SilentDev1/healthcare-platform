from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NppesSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    nppes_source_url: str = (
        "https://npiregistry.cms.hhs.gov/api/?version=2.1&enumeration_type=NPI-2"
        "&state=NH&taxonomy_description=Hospital&limit=200"
    )
    nppes_http_timeout_seconds: float = Field(60, gt=0, le=300)
    nppes_download_max_bytes: int = Field(25_000_000, gt=0)
    nppes_parser_version: str = "1.0.0"
    nppes_raw_data_dir: Path = Path("data/raw/nppes")


nppes_settings = NppesSettings()
