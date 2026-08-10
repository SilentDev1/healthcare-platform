from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.runtime import AppEnvironment, RuntimeSettings
from packages.runtime import runtime_settings as global_runtime_settings
from packages.runtime.safety import require_fixture_safe


def deployed_settings(**overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "app_env": "beta",
        "public_app_url": "https://beta.example.test",
        "api_public_url": "https://api-beta.example.test",
        "database_url": "postgresql+psycopg://user:secret@db.example.test/carevero",
        "allowed_origins": "https://beta.example.test",
        "trusted_hosts": "beta.example.test,api-beta.example.test",
        "source_storage_bucket": "carevero-beta-sources",
        "admin_api_enabled": False,
    }
    values.update(overrides)
    return RuntimeSettings.model_validate(values)


def test_beta_configuration_requires_isolation_and_https() -> None:
    settings = deployed_settings()
    assert settings.app_env is AppEnvironment.BETA
    assert settings.is_deployed
    with pytest.raises(ValidationError, match="non-local database"):
        deployed_settings(database_url="postgresql+psycopg://user:secret@localhost/carevero")
    with pytest.raises(ValidationError, match="HTTPS"):
        deployed_settings(public_app_url="http://beta.example.test")
    with pytest.raises(ValidationError, match="non-wildcard"):
        deployed_settings(allowed_origins="*")


def test_beta_configuration_accepts_cloud_sql_socket() -> None:
    settings = deployed_settings(
        database_url=(
            "postgresql+psycopg://carevero:secret@/carevero?host=/cloudsql/project:region:instance"
        )
    )

    assert settings.is_deployed


def test_fixture_operations_are_refused_in_beta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(global_runtime_settings, "app_env", AppEnvironment.BETA)
    with pytest.raises(RuntimeError, match="disabled in beta"):
        require_fixture_safe("fixture import", Path("data/fixtures/example.csv"))
