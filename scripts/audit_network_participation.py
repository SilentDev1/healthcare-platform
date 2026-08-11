"""Conservative audit of stored official network-participation observations."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime

from sqlalchemy import select

from packages.database import (
    NetworkParticipationObservation,
    ProviderDirectorySource,
    session_factory,
)
from packages.network_foundation import conservative_network_status, freshness_status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()
    with session_factory() as session:
        rows = list(
            session.execute(
                select(NetworkParticipationObservation, ProviderDirectorySource)
                .join(
                    ProviderDirectorySource,
                    ProviderDirectorySource.id == NetworkParticipationObservation.source_id,
                )
                .where(NetworkParticipationObservation.state == args.state.upper())
            )
        )
    groups: dict[tuple[object, ...], set[str]] = defaultdict(set)
    freshness: Counter[str] = Counter()
    missing_provenance = 0
    ambiguous = 0
    for observation, source in rows:
        key = (
            observation.facility_id,
            observation.facility_location_id,
            observation.insurance_plan_entity_id,
            observation.insurance_network_entity_id,
        )
        groups[key].add(observation.status)
        freshness[freshness_status(observation.observed_at, source.freshness_days)] += 1
        missing_provenance += int(not source.source_url or not observation.source_evidence)
        ambiguous += int(observation.review_status != "approved" or observation.facility_id is None)
    conflicts = sum(
        conservative_network_status(statuses) == "CONFLICT_REVIEW_REQUIRED"
        for statuses in groups.values()
    )
    print(
        json.dumps(
            {
                "audited_at": datetime.now(UTC).isoformat(),
                "state": args.state.upper(),
                "observations": len(rows),
                "verified_in_network": sum(row[0].status == "IN_NETWORK_VERIFIED" for row in rows),
                "conflicts": conflicts,
                "ambiguous_matches": ambiguous,
                "missing_provenance": missing_provenance,
                "freshness": dict(freshness),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
