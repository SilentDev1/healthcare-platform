from packages.runtime import RuntimeSettings


class ApiSettings(RuntimeSettings):
    api_title: str = "Carevero API"
    api_version: str = "0.1.0"


api_settings = ApiSettings()
