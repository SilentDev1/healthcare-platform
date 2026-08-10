"""Validate a beta/production configuration without printing secrets."""

import json

from packages.runtime import RuntimeSettings


def main() -> None:
    settings = RuntimeSettings()
    print(
        json.dumps(
            {
                "status": "valid",
                "environment": settings.app_env,
                "public_app_url": settings.public_app_url,
                "api_public_url": settings.api_public_url,
                "database_host_configured": bool(settings.database_url),
                "allowed_origin_count": len(settings.origins),
                "trusted_host_count": len(settings.hosts),
                "durable_storage_configured": bool(settings.source_storage_bucket),
                "scheduler_enabled": settings.scheduler_enabled,
                "seo_indexing_enabled": settings.seo_indexing_enabled,
                "admin_api_enabled": settings.admin_api_enabled,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
