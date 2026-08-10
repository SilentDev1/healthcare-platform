"""Audit NH hospital coverage: verify acute-care facilities exist."""

import json
from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.inventory import get_official_domains
from packages.database import (
    Facility,
    FacilityIdentifier,
    FacilityLocation,
    FacilityPriceSource,
    HospitalPriceRecord,
    session_factory,
)

# Reference list of 26 NH acute-care hospitals with CMS CCN
NH_HOSPITALS = (
    ("ALICE PECK DAY MEMORIAL HOSPITAL", "300029"),
    ("ANDROSCOGGIN VALLEY HOSPITAL", "301312"),
    ("CATHOLIC MEDICAL CENTER", "300034"),
    ("CHESHIRE MEDICAL CENTER", "300019"),
    ("CONCORD HOSPITAL", "300001"),
    ("CONCORD HOSPITAL- FRANKLIN", "301309"),
    ("CONCORD HOSPITAL- LACONIA", "300005"),
    ("COTTAGE HOSPITAL", "301310"),
    ("ELLIOT HOSPITAL", "300010"),
    ("EXETER HOSPITAL INC", "300024"),
    ("FRISBIE MEMORIAL HOSPITAL", "300014"),
    ("HAMPSTEAD HOSPITAL & RESIDENTIAL TREATMENT FACILIT", "304007"),
    ("HUGGINS HOSPITAL", "301311"),
    ("LITTLETON REGIONAL HEALTHCARE", "300011"),
    ("MARY HITCHCOCK MEMORIAL HOSPITAL", "300003"),
    ("MEMORIAL HOSPITAL, THE", "301305"),
    ("MONADNOCK COMMUNITY HOSPITAL", "300023"),
    ("NEW HAMPSHIRE HOSPITAL", "304000"),
    ("NEW LONDON HOSPITAL", "301302"),
    ("PARKLAND MEDICAL CENTER", "300017"),
    ("PORTSMOUTH REGIONAL HOSPITAL", "300016"),
    ("SOUTHERN NH MEDICAL CENTER", "300020"),
    ("SPEARE MEMORIAL HOSPITAL", "301304"),
    ("ST JOSEPH HOSPITAL", "300012"),
    ("UPPER CONNECTICUT VALLEY HOSPITAL", "301306"),
    ("VALLEY REGIONAL HOSPITAL", "301307"),
    ("WEEKS MEDICAL CENTER", "301303"),
    ("WENTWORTH-DOUGLASS HOSPITAL", "300018"),
)


@dataclass
class HospitalAuditEntry:
    facility_name: str
    ccn: str
    found_in_db: bool
    facility_id: str | None
    has_npi: bool
    has_address: bool
    has_source: bool
    source_url: str | None
    source_format: str | None
    has_parsed_records: bool
    record_count: int
    has_domain: bool
    domain: str | None


def audit_nh_hospitals(session: Session) -> list[HospitalAuditEntry]:
    entries: list[HospitalAuditEntry] = []

    for legal_name, ccn in NH_HOSPITALS:
        facility = session.scalar(select(Facility).where(Facility.legal_name == legal_name))
        if facility is None:
            facility = session.scalar(
                select(Facility).where(Facility.cms_certification_number == ccn)
            )

        has_npi = False
        has_address = False
        has_source = False
        source_url: str | None = None
        source_format: str | None = None
        record_count = 0

        if facility:
            has_npi = (
                session.scalar(
                    select(func.count(FacilityIdentifier.id)).where(
                        FacilityIdentifier.facility_id == facility.id,
                        FacilityIdentifier.identifier_type == "NPI_ORGANIZATION",
                    )
                )
                or 0
            ) > 0
            has_address = (
                session.scalar(
                    select(func.count(FacilityLocation.id)).where(
                        FacilityLocation.facility_id == facility.id
                    )
                )
                or 0
            ) > 0
            price_source = session.scalar(
                select(FacilityPriceSource).where(
                    FacilityPriceSource.facility_id == facility.id,
                    FacilityPriceSource.active.is_(True),
                )
            )
            if price_source:
                has_source = True
                source_url = price_source.machine_readable_file_url
                source_format = price_source.detected_format
            record_count = (
                session.scalar(
                    select(func.count(HospitalPriceRecord.id)).where(
                        HospitalPriceRecord.facility_id == facility.id
                    )
                )
                or 0
            )

        domain = get_official_domains().get(legal_name)
        entries.append(
            HospitalAuditEntry(
                facility_name=legal_name,
                ccn=ccn,
                found_in_db=facility is not None,
                facility_id=str(facility.id) if facility else None,
                has_npi=has_npi,
                has_address=has_address,
                has_source=has_source,
                source_url=source_url,
                source_format=source_format,
                has_parsed_records=record_count > 0,
                record_count=record_count,
                has_domain=domain is not None,
                domain=domain,
            )
        )
    return entries


def main() -> None:
    with session_factory() as session:
        entries = audit_nh_hospitals(session)

    found = sum(1 for e in entries if e.found_in_db)
    with_source = sum(1 for e in entries if e.has_source)
    with_records = sum(1 for e in entries if e.has_parsed_records)
    with_domain = sum(1 for e in entries if e.has_domain)
    total = len(entries)

    print("\n=== NH Hospital Coverage Audit ===")
    print(f"  Total reference hospitals: {total}")
    print(f"  Found in DB: {found}/{total}")
    print(f"  With domain mapping: {with_domain}/{total}")
    print(f"  With price source: {with_source}/{total}")
    print(f"  With parsed records: {with_records}/{total}")

    missing = [e for e in entries if not e.found_in_db]
    if missing:
        print("\n  MISSING from DB:")
        for e in missing:
            print(f"    - {e.facility_name} (CCN: {e.ccn})")

    no_domain = [e for e in entries if not e.has_domain]
    if no_domain:
        print("\n  MISSING domain mapping:")
        for e in no_domain:
            print(f"    - {e.facility_name}")

    print("\n  Full audit JSON:")
    print(json.dumps([asdict(e) for e in entries], indent=2))


if __name__ == "__main__":
    main()
