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


REAL_REGISTRY = Path("data/fixtures/verified_hospital_price_sources.json")
REQUIRED_FIELDS = (
    "ccn",
    "facility_name",
    "source_page_url",
    "machine_readable_file_url",
    "declared_format",
    "evidence",
)


def test_committed_registry_entries_are_well_formed() -> None:
    sources = load_registry(REAL_REGISTRY)

    assert sources, "registry must not be empty"
    seen_ccns: set[str] = set()
    for entry in sources:
        for field in REQUIRED_FIELDS:
            assert entry.get(field), f"{entry.get('ccn')}: missing {field}"
        assert entry["source_page_url"].startswith("https://")
        assert entry["machine_readable_file_url"].startswith("https://")
        assert "vendor_name" in entry and "health_system_name" in entry
        ccn = entry["ccn"]
        assert ccn not in seen_ccns, f"duplicate CCN in registry: {ccn}"
        seen_ccns.add(ccn)


def test_androscoggin_valley_source_registered() -> None:
    sources = load_registry(REAL_REGISTRY)
    by_ccn = {entry["ccn"]: entry for entry in sources}

    entry = by_ccn.get("301310")
    assert entry is not None, "CCN 301310 (Androscoggin Valley) must be registered"
    # Facility name must match the DB legal_name exactly (register_sources rejects mismatches).
    assert entry["facility_name"] == "ANDROSCOGGIN VALLEY HOSPITAL"
    assert (
        entry["machine_readable_file_url"]
        == "https://hospitalpricetransparencyfiles.com/androscoggin-valley-hospital/"
        "020280367_Androscoggin-Valley-Hospital_standardcharges.csv"
    )
    assert entry["declared_format"] == "csv"


def test_cottage_hospital_source_registered() -> None:
    sources = load_registry(REAL_REGISTRY)
    by_ccn = {entry["ccn"]: entry for entry in sources}

    entry = by_ccn.get("301301")
    assert entry is not None, "CCN 301301 (Cottage Hospital) must be registered"
    assert entry["facility_name"] == "COTTAGE HOSPITAL"
    # Must trace to Cottage Hospital's own domain (its EIN in the filename), not a
    # third-party estimate/aggregator or the old chargemaster.
    url = entry["machine_readable_file_url"]
    assert url.startswith("https://www.cottagehospital.org/")
    assert "020223321" in url  # Cottage Hospital EIN
    assert entry["declared_format"] == "csv"
