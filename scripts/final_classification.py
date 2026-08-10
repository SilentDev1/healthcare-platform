"""Final classification: classify every hospital and check stop conditions.

Accepts --state for geographic scope. Classifications are evidence-based
and never fabricated.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.inventory import load_inventory
from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PricingHealthScore,
    session_factory,
)
from packages.database.pricing_models import ParserReview

# Classification categories
CLASSIFICATIONS = (
    "excluded_psychiatric",
    "publishable",
    "no_transparency_page",
    "unsupported_format",
    "cdm_only",
    "download_failed",
    "no_matched_procedures",
    "quality_suppressed",
    "discovery_failure",
    "parser_failure",
    "other_review_required",
)


def classify_facility(session: Session, facility_id: object, state_code: str) -> dict[str, object]:
    """Classify a single facility's status."""
    facility = session.get(Facility, facility_id)
    if not facility:
        return {"classification": "other_review_required", "reason": "facility not found"}

    # Check inventory for exclusions
    try:
        inventory = load_inventory()
        entry = inventory.get_by_name(facility.legal_name)
        if entry and entry.status == "excluded_psychiatric":
            return {
                "classification": "excluded_psychiatric",
                "reason": entry.exclusion_reason or "State psychiatric facility",
                "evidence": {"facility_type": entry.facility_type, "ccn": entry.cms_ccn},
            }
    except Exception:
        pass

    # Check for publishable pricing
    publishable_count = (
        session.scalar(
            select(func.count(FacilityProcedurePriceSummary.id)).where(
                FacilityProcedurePriceSummary.facility_id == facility_id,
                FacilityProcedurePriceSummary.publication_status == "publishable",
            )
        )
        or 0
    )
    if publishable_count > 0:
        return {
            "classification": "publishable",
            "reason": f"{publishable_count} publishable price summaries",
            "evidence": {"publishable_count": publishable_count},
        }

    # Check for sources
    sources = list(
        session.scalars(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id == facility_id,
                FacilityPriceSource.active.is_(True),
            )
        )
    )
    if not sources:
        return {
            "classification": "discovery_failure",
            "reason": "No MRF sources discovered",
            "evidence": {"website": facility.website_url},
        }

    # Check for downloaded files
    downloaded = [s for s in sources if s.source_file_id is not None]
    if not downloaded:
        failed = [s for s in sources if s.last_failed_download_at is not None]
        if failed:
            return {
                "classification": "download_failed",
                "reason": f"Download failed for {len(failed)} source(s)",
                "evidence": {
                    "urls": [s.machine_readable_file_url for s in failed],
                    "last_failed": str(
                        max(s.last_failed_download_at for s in failed if s.last_failed_download_at)
                    ),
                },
            }
        return {
            "classification": "download_failed",
            "reason": "No files downloaded yet",
            "evidence": {"source_count": len(sources)},
        }

    # Check for parsed records
    record_count = (
        session.scalar(
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.facility_id == facility_id
            )
        )
        or 0
    )
    if record_count == 0:
        # Check if parser quarantined the file
        quarantined = (
            session.scalar(
                select(func.count(ParserReview.id)).where(
                    ParserReview.status == "unsupported_pending_review",
                    ParserReview.source_file_id.in_(
                        [s.source_file_id for s in downloaded if s.source_file_id]
                    ),
                )
            )
            or 0
        )
        if quarantined > 0:
            return {
                "classification": "unsupported_format",
                "reason": f"{quarantined} file(s) quarantined as unsupported format",
                "evidence": {"quarantined_files": quarantined},
            }
        return {
            "classification": "parser_failure",
            "reason": "Files downloaded but no records parsed",
            "evidence": {"downloaded_files": len(downloaded)},
        }

    # Has records but no publishable pricing
    health_score = session.scalar(
        select(PricingHealthScore).where(PricingHealthScore.facility_id == facility_id)
    )
    if health_score and float(health_score.mapping_score) < 10:
        return {
            "classification": "no_matched_procedures",
            "reason": "Records parsed but no procedures matched via approved codes",
            "evidence": {
                "record_count": record_count,
                "mapping_score": float(health_score.mapping_score),
            },
        }
    if health_score and float(health_score.anomaly_score) < 20:
        return {
            "classification": "quality_suppressed",
            "reason": "Records matched but quality issues prevent publication",
            "evidence": {
                "record_count": record_count,
                "anomaly_score": float(health_score.anomaly_score),
            },
        }

    return {
        "classification": "no_matched_procedures",
        "reason": "Records exist but no publishable procedure-price mappings",
        "evidence": {"record_count": record_count},
    }


def classify_all(session: Session, state_code: str = "NH") -> dict[str, object]:
    """Classify every facility in the state."""
    facility_ids = sorted(active_consumer_facility_ids(session, state_code), key=str)

    classifications: list[dict[str, object]] = []
    summary_counts: dict[str, int] = {}

    for fid in facility_ids:
        facility = session.get(Facility, fid)
        result = classify_facility(session, fid, state_code)
        cls = str(result["classification"])
        summary_counts[cls] = summary_counts.get(cls, 0) + 1
        classifications.append(
            {
                "facility_id": str(fid),
                "facility_name": facility.display_name if facility else "Unknown",
                **result,
            }
        )

    # Stop conditions check
    all_reviewed = len(classifications) == len(facility_ids)
    all_classified = all(c["classification"] != "other_review_required" for c in classifications)

    return {
        "state": state_code,
        "total_facilities": len(facility_ids),
        "classification_summary": summary_counts,
        "classifications": classifications,
        "stop_conditions": {
            "all_hospitals_reviewed": all_reviewed,
            "all_hospitals_classified": all_classified,
            "publishable_count": summary_counts.get("publishable", 0),
            "excluded_count": summary_counts.get("excluded_psychiatric", 0),
            "remaining_unresolved": summary_counts.get("other_review_required", 0),
        },
        "classified_at": datetime.now(UTC).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Final hospital classification")
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()

    with session_factory() as session:
        report = classify_all(session, args.state)

    print(f"\n=== Final Classification Report ({report['state']}) ===")
    print(f"  Total facilities: {report['total_facilities']}")
    print("\n  Classification summary:")
    summary = report["classification_summary"]
    assert isinstance(summary, dict)
    for cls, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"    {cls}: {count}")
    print("\n  Stop conditions:")
    stops = report["stop_conditions"]
    assert isinstance(stops, dict)
    for key, val in stops.items():
        print(f"    {key}: {val}")

    # Save report
    output_dir = Path("data/generated")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(UTC).date().isoformat()
    output_path = output_dir / f"final_classification_{args.state}_{date_str}.json"
    output_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n  Report saved: {output_path}")


if __name__ == "__main__":
    main()
