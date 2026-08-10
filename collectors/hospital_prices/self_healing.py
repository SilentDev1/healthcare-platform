"""Self-healing discovery: verify and recover broken MRF source URLs.

Checks source health via HEAD requests, follows redirects to find moved
files, and re-runs discovery on the facility domain when sources break.
Works generically for any facility regardless of state.
"""

from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityPriceSource,
    FacilityPriceSourceHistory,
)


def check_source_health(
    session: Session,
    source: FacilityPriceSource,
    http: httpx.Client,
) -> str:
    """HEAD request to verify URL still works.

    Returns: "ok", "moved", "broken", "expired"
    """
    try:
        response = http.head(
            source.machine_readable_file_url,
            follow_redirects=False,
        )
        if response.status_code == 200:
            return "ok"
        if response.status_code in (301, 302, 307, 308):
            new_url = response.headers.get("location")
            if new_url:
                # Record the URL change
                session.add(
                    FacilityPriceSourceHistory(
                        facility_price_source_id=source.id,
                        previous_url=source.machine_readable_file_url,
                        new_url=new_url,
                        change_reason=f"redirect_{response.status_code}",
                        changed_at=datetime.now(UTC),
                    )
                )
                source.machine_readable_file_url = new_url
                source.last_seen_at = datetime.now(UTC)
                return "moved"
            return "broken"
        if response.status_code == 404:
            return "broken"
        if response.status_code == 403:
            return "expired"
        return "broken"
    except httpx.HTTPError:
        return "broken"


def attempt_recovery(
    session: Session,
    source: FacilityPriceSource,
    http: httpx.Client,
) -> bool:
    """Attempt to recover a broken source by following redirects and re-discovery.

    Returns True if recovery succeeded and source URL was updated.
    """
    # Step 1: Follow redirects with full GET
    try:
        response = http.get(
            source.machine_readable_file_url,
            follow_redirects=True,
        )
        final_url = str(response.url)
        if response.status_code == 200 and final_url != source.machine_readable_file_url:
            session.add(
                FacilityPriceSourceHistory(
                    facility_price_source_id=source.id,
                    previous_url=source.machine_readable_file_url,
                    new_url=final_url,
                    change_reason="redirect_recovery",
                    changed_at=datetime.now(UTC),
                )
            )
            source.machine_readable_file_url = final_url
            source.last_seen_at = datetime.now(UTC)
            session.flush()
            return True
    except httpx.HTTPError:
        pass

    # Step 2: Check system siblings for alternative URLs
    facility = session.get(Facility, source.facility_id)
    if not facility:
        return False

    # Look for other active sources for the same facility
    sibling_sources = session.scalars(
        select(FacilityPriceSource).where(
            FacilityPriceSource.facility_id == source.facility_id,
            FacilityPriceSource.active.is_(True),
            FacilityPriceSource.id != source.id,
        )
    ).all()

    for sibling in sibling_sources:
        try:
            response = http.head(sibling.machine_readable_file_url, follow_redirects=True)
            if response.status_code == 200:
                # Sibling is still alive; mark broken source as inactive
                source.active = False
                session.flush()
                return True
        except httpx.HTTPError:
            continue

    return False


def check_all_sources(
    session: Session,
    http: httpx.Client | None = None,
) -> dict[str, int]:
    """Check health of all active sources and attempt recovery for broken ones.

    Returns counts: {ok, moved, broken, recovered, expired}
    """
    owned_client = http is None
    client = http or httpx.Client(
        timeout=15,
        follow_redirects=False,
        headers={"User-Agent": "CareCompare-HPT-Research/1.0"},
    )

    counts = {"ok": 0, "moved": 0, "broken": 0, "recovered": 0, "expired": 0}
    sources = session.scalars(
        select(FacilityPriceSource).where(FacilityPriceSource.active.is_(True))
    ).all()

    for source in sources:
        status = check_source_health(session, source, client)
        if status == "ok":
            counts["ok"] += 1
        elif status == "moved":
            counts["moved"] += 1
        elif status == "expired":
            counts["expired"] += 1
        else:
            # Try recovery
            recovered = attempt_recovery(session, source, client)
            if recovered:
                counts["recovered"] += 1
            else:
                counts["broken"] += 1

    session.commit()
    if owned_client:
        client.close()
    return counts
