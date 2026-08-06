from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.nppes_organizations.importer import backfill_cms_identifiers
from packages.database import Facility, FacilityAlias, session_factory
from packages.identity import normalize_name

CURATED_ALIASES = (("MARY HITCHCOCK MEMORIAL HOSPITAL", "Dartmouth Hitchcock Medical Center"),)


def seed_facility_identity(session: Session) -> dict[str, int]:
    identifiers = backfill_cms_identifiers(session)
    aliases = 0
    for legal_name, alias_name in CURATED_ALIASES:
        facility = session.scalar(select(Facility).where(Facility.legal_name == legal_name))
        normalized = normalize_name(alias_name)
        existing = (
            session.scalar(
                select(FacilityAlias.id).where(
                    FacilityAlias.facility_id == facility.id,
                    FacilityAlias.normalized_alias == normalized,
                )
            )
            if facility
            else None
        )
        if facility and existing is None:
            session.add(
                FacilityAlias(
                    facility_id=facility.id,
                    alias_name=alias_name,
                    normalized_alias=normalized,
                    alias_type="system",
                    source_file_id=facility.source_file_id,
                )
            )
            aliases += 1
    session.flush()
    return {"cms_identifiers_inserted": identifiers, "curated_aliases_inserted": aliases}


def main() -> None:
    with session_factory() as session:
        summary = seed_facility_identity(session)
        session.commit()
        print(summary)


if __name__ == "__main__":
    main()
