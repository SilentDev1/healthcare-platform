from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    log_level: str = "INFO"
    api_title: str = "Carevero API"
    api_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


api_settings = ApiSettings()
