from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    log_level: str = "INFO"
    api_title: str = "CareCompare API"
    api_version: str = "0.1.0"


api_settings = ApiSettings()
