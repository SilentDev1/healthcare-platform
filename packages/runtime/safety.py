from pathlib import Path

from packages.runtime import AppEnvironment, runtime_settings


def require_fixture_safe(operation: str, path: Path | None = None) -> None:
    """Refuse synthetic/test data operations in deployed environments."""
    if runtime_settings.app_env in {AppEnvironment.BETA, AppEnvironment.PRODUCTION}:
        detail = f" ({path})" if path else ""
        raise RuntimeError(f"{operation}{detail} is disabled in {runtime_settings.app_env.value}")
