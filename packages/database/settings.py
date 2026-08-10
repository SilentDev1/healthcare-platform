from packages.runtime import runtime_settings


class DatabaseSettings:
    database_url = runtime_settings.database_url


database_settings = DatabaseSettings()
