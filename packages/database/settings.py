from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg://carecompare:carecompare_local_only@localhost:5432/carecompare"
    )


database_settings = DatabaseSettings()
