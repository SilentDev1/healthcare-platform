"""Track B / Phase 12 — Affiliated hospital-MRF linkage audit (READ ONLY).

Finds cases where pricing for a currently-UNPRICED non-hospital service location may
already exist in imported raw hospital MRF data, so we can recover ONLY evidence-backed
links. Writes a JSON report; changes nothing.

Evidence tiers (strongest first):
  A. DIRECT_LOCATION_LINK   — a HospitalPriceRecord already carries facility_location_id ==
                              an unpriced location (raw price linked but not published there).
  B. SAME_FACILITY_SIBLING  — an unpriced location belongs to a Facility that HAS publishable
                              summaries (its raw records may cover this location).
  C. ORG_AFFILIATION_TOKEN  — an unpriced location's Organization also owns a priced facility,
                              AND that facility's raw MRF payload/description contains the
                              location's city/name/NPI token (needs review, not auto-applied).

Run locally (schema-compatible dev DB) or as a Cloud Run job:
  python -m scripts.audit_affiliated_mrf_linkage --output=/mnt/sources/verification/affiliated_mrf_linkage.json
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database.models import (
    Facility,
    FacilityIdentifier,
    FacilityLocation,
    LocationCapability,
    Organization,
)
from packages.database.pricing_models import FacilityProcedurePriceSummary as Summary
from packages.database.pricing_models import HospitalPriceRecord
from packages.database.session import session_factory


def _tokens(*vals: str | None) -> set[str]:
    out: set[str] = set()
    for v in vals:
        if not v:
            continue
        for tok in re.split(r"[^a-z0-9]+", v.lower()):
            if len(tok) >= 4:  # drop short/noise tokens
                out.add(tok)
    return out


def run(session: Session) -> dict[str, Any]:
    # Facilities/locations that already publish (consumer-visible) prices.
    priced_loc_ids = set(
        session.scalars(
            select(Summary.facility_location_id).where(
                Summary.publication_status == "publishable",
                Summary.facility_location_id.is_not(None),
            )
        ).all()
    )
    priced_facility_ids = set(
        session.scalars(
            select(Summary.facility_id).where(Summary.publication_status == "publishable")
        ).all()
    )

    # Active locations with NO publishable summary at that location = "unpriced".
    unpriced_rows = session.execute(
        select(FacilityLocation, Facility, Organization)
        .join(Facility, Facility.id == FacilityLocation.facility_id)
        .join(Organization, Organization.id == Facility.organization_id, isouter=True)
        .where(FacilityLocation.active.is_(True), Facility.active.is_(True))
    ).all()
    unpriced = [
        (loc, fac, org)
        for (loc, fac, org) in unpriced_rows
        if loc.id not in priced_loc_ids
    ]

    caps_by_loc: dict[Any, list[str]] = defaultdict(list)
    for lid, cap in session.execute(
        select(LocationCapability.facility_location_id, LocationCapability.capability).where(
            LocationCapability.active.is_(True)
        )
    ):
        caps_by_loc[lid].append(cap)

    # --- Check A: raw records already linked to an unpriced location ---------------
    unpriced_loc_ids = {loc.id for (loc, _f, _o) in unpriced}
    a_hits: dict[Any, int] = {}
    for loc_id, cnt in session.execute(
        select(HospitalPriceRecord.facility_location_id, func.count())
        .where(HospitalPriceRecord.facility_location_id.in_(unpriced_loc_ids))
        .group_by(HospitalPriceRecord.facility_location_id)
    ):
        a_hits[loc_id] = int(cnt)

    # Priced facilities' owning organizations (for affiliation).
    priced_org_ids = set(
        session.scalars(
            select(Facility.organization_id).where(
                Facility.id.in_(priced_facility_ids), Facility.organization_id.is_not(None)
            )
        ).all()
    )

    # NPIs per facility (identifier evidence).
    npis_by_facility: dict[Any, set[str]] = defaultdict(set)
    for fid, itype, ivalue in session.execute(
        select(FacilityIdentifier.facility_id, FacilityIdentifier.identifier_type, FacilityIdentifier.identifier_value)
    ):
        if ivalue and (itype or "").lower() == "npi":
            npis_by_facility[fid].add(str(ivalue).strip())

    findings: list[dict[str, Any]] = []
    for loc, fac, org in unpriced:
        caps = caps_by_loc.get(loc.id, [])
        tiers: list[str] = []
        evidence: dict[str, Any] = {}

        if loc.id in a_hits:
            tiers.append("DIRECT_LOCATION_LINK")
            evidence["raw_records_linked"] = a_hits[loc.id]

        if fac.id in priced_facility_ids:
            tiers.append("SAME_FACILITY_SIBLING")
            evidence["priced_facility"] = fac.display_name

        # Org affiliation with a priced facility (different facility, same organization).
        if fac.organization_id and fac.organization_id in priced_org_ids and fac.id not in priced_facility_ids:
            # Look for the location's identity tokens in the affiliated priced facility's raw payloads.
            aff_facility_ids = list(
                session.scalars(
                    select(Facility.id).where(
                        Facility.organization_id == fac.organization_id,
                        Facility.id.in_(priced_facility_ids),
                    )
                ).all()
            )
            loc_tokens = _tokens(loc.location_name, loc.city, fac.display_name)
            loc_npis = npis_by_facility.get(fac.id, set())
            token_hit = False
            npi_hit = False
            # Sample up to 400 raw records from the affiliated priced facilities.
            sample = session.execute(
                select(HospitalPriceRecord.raw_description, HospitalPriceRecord.raw_payload)
                .where(HospitalPriceRecord.facility_id.in_(aff_facility_ids))
                .limit(400)
            ).all()
            for desc, payload in sample:
                blob = (desc or "") + " " + json.dumps(payload, ensure_ascii=False)[:2000]
                low = blob.lower()
                if loc_npis and any(n in blob for n in loc_npis):
                    npi_hit = True
                    break
                if loc.city and loc.location_name and any(
                    t in low for t in loc_tokens if t not in {"health", "center", "medical"}
                ):
                    token_hit = True
            if npi_hit:
                tiers.append("ORG_AFFILIATION_NPI")
                evidence["affiliated_priced_org"] = org.display_name if org else None
            elif token_hit:
                tiers.append("ORG_AFFILIATION_TOKEN")
                evidence["affiliated_priced_org"] = org.display_name if org else None

        if tiers:
            findings.append(
                {
                    "location_id": str(loc.id),
                    "location_name": loc.location_name or fac.display_name,
                    "facility": fac.display_name,
                    "organization": org.display_name if org else None,
                    "city": loc.city,
                    "capabilities": caps,
                    "evidence_tiers": tiers,
                    "evidence": evidence,
                }
            )

    findings.sort(key=lambda f: (0 if "DIRECT_LOCATION_LINK" in f["evidence_tiers"] else 1, f["facility"]))
    report = {
        "kind": "affiliated_mrf_linkage_audit",
        "read_only": True,
        "totals": {
            "priced_locations": len(priced_loc_ids),
            "unpriced_locations_examined": len(unpriced),
            "candidates_with_evidence": len(findings),
            "direct_location_link": sum("DIRECT_LOCATION_LINK" in f["evidence_tiers"] for f in findings),
            "same_facility_sibling": sum("SAME_FACILITY_SIBLING" in f["evidence_tiers"] for f in findings),
            "org_affiliation": sum(
                any(t.startswith("ORG_AFFILIATION") for t in f["evidence_tiers"]) for f in findings
            ),
        },
        "findings": findings,
    }
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="data/affiliated_mrf_linkage_audit.json")
    args = ap.parse_args()
    with session_factory() as session:
        report = run(session)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    t = report["totals"]
    print("AFFILIATED_MRF_LINKAGE_AUDIT (read-only)")
    print(f"  priced_locations={t['priced_locations']} unpriced_examined={t['unpriced_locations_examined']}")
    print(f"  candidates_with_evidence={t['candidates_with_evidence']}")
    print(f"    DIRECT_LOCATION_LINK={t['direct_location_link']}")
    print(f"    SAME_FACILITY_SIBLING={t['same_facility_sibling']}")
    print(f"    ORG_AFFILIATION={t['org_affiliation']}")
    for f in report["findings"][:25]:
        print(f"    - {f['facility']} / {f['location_name']} [{','.join(f['capabilities'])}] :: {','.join(f['evidence_tiers'])} {f['evidence']}")
    print(f"  wrote {args.output}")


if __name__ == "__main__":
    main()
