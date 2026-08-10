"""Register human-verified hospital MRF sources using deterministic facility identity.

The registry is state-independent: every source is assigned by CMS Certification
Number (CCN), and includes the official source page that authorizes the MRF URL.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Facility, FacilityPriceSource, session_factory

DEFAULT_REGISTRY = Path("data/fixtures/verified_hospital_price_sources.json")


class VerifiedSource(TypedDict):
    ccn: str
    facility_name: str
    source_page_url: str
    machine_readable_file_url: str
    declared_format: str
    vendor_name: str | None
    health_system_name: str | None
    evidence: str


def load_registry(path: Path) -> list[VerifiedSource]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("verified source registry must contain a sources list")
    return sources


def register_sources(
    session: Session, sources: list[VerifiedSource], *, state: str | None = None
) -> dict[str, object]:
    created = updated = 0
    errors: list[str] = []
    now = datetime.now(UTC)
    for entry in sources:
        facility = session.scalar(
            select(Facility).where(Facility.cms_certification_number == entry["ccn"])
        )
        if facility is None:
            errors.append(f"{entry['ccn']}: facility not found")
            continue
        if facility.legal_name != entry["facility_name"]:
            errors.append(
                f"{entry['ccn']}: expected {entry['facility_name']}, found {facility.legal_name}"
            )
            continue
        if state is not None:
            facility_states = {location.state for location in facility.locations}
            if state.upper() not in facility_states:
                continue

        existing = session.scalar(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id == facility.id,
                FacilityPriceSource.machine_readable_file_url == entry["machine_readable_file_url"],
            )
        )
        if existing is None:
            existing = FacilityPriceSource(
                facility_id=facility.id,
                source_type="hospital_mrf",
                source_page_url=entry["source_page_url"],
                machine_readable_file_url=entry["machine_readable_file_url"],
                declared_format=entry["declared_format"],
                active=True,
                discovery_method="verified_official_source",
                first_seen_at=now,
                last_seen_at=now,
                vendor_name=entry["vendor_name"],
                health_system_name=entry["health_system_name"],
            )
            session.add(existing)
            created += 1
        else:
            existing.source_page_url = entry["source_page_url"]
            existing.declared_format = entry["declared_format"]
            existing.active = True
            existing.last_seen_at = now
            existing.vendor_name = entry["vendor_name"]
            existing.health_system_name = entry["health_system_name"]
            updated += 1
    return {"created": created, "updated": updated, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--state")
    args = parser.parse_args()
    sources = load_registry(args.registry)
    with session_factory() as session:
        result = register_sources(session, sources, state=args.state)
        session.commit()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
