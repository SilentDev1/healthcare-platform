"""Read-only: trace a suspicious (facility, procedure) price back to its raw source record(s).

Given a facility name substring and a procedure slug, prints the publishable price summaries and
the underlying raw HospitalPriceRecord rows (raw description, code, gross/cash/negotiated amounts,
setting, source file) so an unusual price can be judged against the authoritative source rather
than deleted on suspicion.

Run: python -m scripts.trace_price_anomaly --facility LACONIA --procedure allergy-testing
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from sqlalchemy import select

from packages.database import (
    Facility,
    HospitalPriceRecord,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    Procedure,
    session_factory,
)
from packages.database.pricing_models import FacilityProcedurePriceSummary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facility", required=True)
    parser.add_argument("--procedure", required=True)
    parser.add_argument("--max-price", type=float, default=None, help="only records with cash/gross <= this")
    args = parser.parse_args()

    with session_factory() as session:
        proc = session.scalar(select(Procedure).where(Procedure.slug == args.procedure))
        fac = session.scalar(
            select(Facility).where(Facility.display_name.ilike(f"%{args.facility}%"))
        )
        if not proc or not fac:
            print("NOT_FOUND facility or procedure")
            return

        summaries = session.scalars(
            select(FacilityProcedurePriceSummary).where(
                FacilityProcedurePriceSummary.facility_id == fac.id,
                FacilityProcedurePriceSummary.procedure_id == proc.id,
            )
        ).all()
        print(f"FACILITY={fac.display_name} PROCEDURE={proc.slug}")
        print(f"SUMMARIES={len(summaries)}")
        for s in summaries:
            print(json.dumps({
                "publication_status": s.publication_status,
                "service_setting": s.service_setting,
                "cash_min": str(s.cash_price_min), "cash_max": str(s.cash_price_max),
                "neg_min": str(s.negotiated_price_min), "neg_max": str(s.negotiated_price_max),
                "record_count": s.record_count, "scope": s.included_component_scope,
            }, default=str))

        # Raw records mapped to this procedure at this facility
        recs = session.execute(
            select(HospitalPriceRecord)
            .join(PriceRecordProcedureMapping, PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id)
            .where(
                HospitalPriceRecord.facility_id == fac.id,
                PriceRecordProcedureMapping.procedure_id == proc.id,
                PriceRecordProcedureMapping.reviewed.is_(True),
            )
        ).scalars().all()
        print(f"RAW_MAPPED_RECORDS={len(recs)}")
        shown = 0
        for r in recs:
            gross = float(r.gross_charge) if r.gross_charge is not None else None
            cash = float(r.discounted_cash_price) if r.discounted_cash_price is not None else None
            if args.max_price is not None:
                vals = [v for v in (gross, cash) if v is not None]
                if not vals or min(vals) > args.max_price:
                    continue
            codes = [
                f"{c.code_system}:{c.code}"
                for c in session.scalars(
                    select(PriceServiceCode).where(PriceServiceCode.hospital_price_record_id == r.id)
                )
            ]
            print("RAWREC=" + json.dumps({
                "raw_description": r.raw_description,
                "codes": codes,
                "gross": gross, "cash": cash,
                "neg_min": str(r.deidentified_minimum_negotiated_rate),
                "neg_max": str(r.deidentified_maximum_negotiated_rate),
                "setting": r.setting, "billing_class": r.billing_class,
                "drug_unit": r.drug_unit, "unit_measure": r.drug_type_of_measurement,
                "parser": r.parser_name, "source_record_id": r.source_record_identifier,
            }, default=str))
            shown += 1
            if shown >= 40:
                break


if __name__ == "__main__":
    main()
