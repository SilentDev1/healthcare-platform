import json
from pathlib import Path

from scripts.register_verified_price_sources import load_registry


def test_verified_source_registry_has_deterministic_identity_and_evidence(tmp_path: Path) -> None:
    registry = tmp_path / "sources.json"
    registry.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "ccn": "300001",
                        "facility_name": "EXAMPLE HOSPITAL",
                        "source_page_url": "https://hospital.example/prices",
                        "machine_readable_file_url": "https://hospital.example/standardcharges.csv",
                        "declared_format": "csv",
                        "vendor_name": None,
                        "health_system_name": None,
                        "evidence": "Direct link on official hospital page",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = load_registry(registry)

    assert sources[0]["ccn"] == "300001"
    assert sources[0]["source_page_url"].startswith("https://")
    assert sources[0]["machine_readable_file_url"].startswith("https://")
    assert sources[0]["evidence"]
