"""Read-only diagnostic: report how a SourceFile links to facilities.

Given a source_file_id, prints every FacilityPriceSource that references it (with
facility CCN + active flag), the facility_id distribution of its
HospitalPriceRecords, and the publishable-summary counts per facility. Used to
debug records landing under the wrong facility when several price sources point at
one source file. Never mutates anything.
"""

import argparse
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    SourceFile,
    get_session,
)


def diagnose(source_file_id: uuid.UUID, session: Session | None = None) -> None:
    if session is None:
        session = next(get_session())

    source = session.get(SourceFile, source_file_id)
    print(f"SourceFile {source_file_id}: {'FOUND' if source else 'MISSING'}")
    if source is not None:
        print(f"  source_url={source.source_url}")
        print(f"  storage_path={source.storage_path}")
        print(f"  status={source.status}")

    print("\n== FacilityPriceSources referencing this source_file ==")
    price_sources = session.scalars(
        select(FacilityPriceSource).where(FacilityPriceSource.source_file_id == source_file_id)
    ).all()
    for ps in price_sources:
        fac = session.get(Facility, ps.facility_id)
        ccn = fac.cms_certification_number if fac else "?"
        name = fac.legal_name if fac else "?"
        print(
            f"  price_source={ps.id} active={ps.active} facility={ps.facility_id} "
            f"ccn={ccn} legal_name={name!r} url={ps.machine_readable_file_url}"
        )

    print("\n== HospitalPriceRecord facility_id distribution (this source_file) ==")
    rows = session.execute(
        select(HospitalPriceRecord.facility_id, func.count(HospitalPriceRecord.id))
        .where(HospitalPriceRecord.source_file_id == source_file_id)
        .group_by(HospitalPriceRecord.facility_id)
    ).all()
    for facility_id, count in rows:
        fac = session.get(Facility, facility_id)
        ccn = fac.cms_certification_number if fac else "?"
        print(f"  facility={facility_id} ccn={ccn}: {count} records")

    print("\n== Publishable summaries per facility (this source_file) ==")
    srows = session.execute(
        select(
            FacilityProcedurePriceSummary.facility_id,
            FacilityProcedurePriceSummary.publication_status,
            func.count(FacilityProcedurePriceSummary.id),
        )
        .where(FacilityProcedurePriceSummary.source_file_id == source_file_id)
        .group_by(
            FacilityProcedurePriceSummary.facility_id,
            FacilityProcedurePriceSummary.publication_status,
        )
    ).all()
    for facility_id, status, count in srows:
        fac = session.get(Facility, facility_id)
        ccn = fac.cms_certification_number if fac else "?"
        print(f"  facility={facility_id} ccn={ccn} status={status}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnose SourceFile -> facility linkage")
    parser.add_argument("--source-file-id", type=uuid.UUID, required=True)
    args = parser.parse_args()
    diagnose(args.source_file_id)
