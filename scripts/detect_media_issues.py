"""Read-only detector for facility/location image problems. FLAGS ONLY — never deletes.

Surfaces, for human review (per the media policy):
  * SAME_IMAGE_UNRELATED_ADDRESS  — one image used by facilities at DIFFERENT street addresses
    (a shared medical building = SAME address is legitimate and is reported separately).
  * SOURCE_CITY_MISMATCH          — the image's source URL / attribution names a NH city that is
    not the location's city (possible wrong-branch photo).
  * HOSPITAL_IMAGE_ON_NONHOSPITAL — a media row whose source_type/attribution reads as a hospital
    but is attached to a non-hospital facility.
  * SHARED_LOCATION_SPECIFIC_IMAGE — the same image is attached to multiple DISTINCT service
    locations (location-specific imagery should not be silently shared).
  * MISSING_ATTRIBUTION           — a CC-BY / CC-BY-SA license with no attribution_text.
  * BROKEN_IMAGE_URL              — remote image URL returns non-200 (only with --check-urls).

Exit is always 0 (flag-only); the report lists everything for review.

Run: python -m scripts.detect_media_issues [--check-urls]
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    FacilityLocation,
    FacilityMedia,
    LocationCapability,
    session_factory,
)
from scripts.detect_duplicate_locations import base_address

# NH city vocabulary for the source-city heuristic (lowercase).
_NH_CITIES = {
    "nashua", "manchester", "concord", "bedford", "derry", "dover", "salem", "portsmouth",
    "keene", "merrimack", "londonderry", "windham", "plaistow", "littleton", "belmont",
    "rochester", "exeter", "stratham", "hooksett", "gilford", "goffstown", "lebanon",
    "seabrook", "tilton", "alton", "epping", "claremont", "pelham", "amherst", "raymond",
    "somersworth", "durham", "lee", "hudson", "auburn", "grantham", "plymouth", "franklin",
    "laconia", "berlin", "lancaster", "colebrook", "woodsville", "peterborough", "wolfeboro",
    "north conway", "new london",
}
_TOKEN = re.compile(r"[a-z]+")
_CC_BY = ("cc-by", "cc by")


def _image_key(m: FacilityMedia) -> str | None:
    return m.checksum_sha256 or m.cdn_url or m.source_url


def find_issues(session: Session) -> dict[str, list[dict[str, object]]]:
    media = list(
        session.scalars(
            select(FacilityMedia).where(FacilityMedia.verification_status == "verified")
        )
    )
    # location + capability context per facility (primary/first active location)
    fac_ids = {m.facility_id for m in media}
    loc_by_fac: dict[object, FacilityLocation] = {}
    caps_by_fac: dict[object, set[str]] = {}
    for fid in fac_ids:
        loc = session.scalar(
            select(FacilityLocation)
            .where(FacilityLocation.facility_id == fid, FacilityLocation.active.is_(True))
            .order_by(FacilityLocation.created_at)
        )
        if loc is not None:
            loc_by_fac[fid] = loc
            caps_by_fac[fid] = set(
                session.scalars(
                    select(LocationCapability.capability).where(
                        LocationCapability.facility_location_id == loc.id
                    )
                )
            )

    issues: dict[str, list[dict[str, object]]] = {
        "SAME_IMAGE_UNRELATED_ADDRESS": [],
        "SHARED_BUILDING_SAME_ADDRESS": [],
        "SOURCE_CITY_MISMATCH": [],
        "HOSPITAL_IMAGE_ON_NONHOSPITAL": [],
        "SHARED_LOCATION_SPECIFIC_IMAGE": [],
        "MISSING_ATTRIBUTION": [],
        "BROKEN_IMAGE_URL": [],
    }

    # Group by image key to find reuse.
    by_key: dict[str, list[FacilityMedia]] = {}
    for m in media:
        k = _image_key(m)
        if k:
            by_key.setdefault(k, []).append(m)
    for key, group in by_key.items():
        addrs = {
            base_address(loc_by_fac[m.facility_id].address_line_1)
            for m in group
            if m.facility_id in loc_by_fac
        }
        cities = {
            (loc_by_fac[m.facility_id].city or "").upper()
            for m in group
            if m.facility_id in loc_by_fac
        }
        fac_set = {str(m.facility_id) for m in group}
        if len(fac_set) > 1:
            entry: dict[str, object] = {"image": key[:80], "facilities": sorted(fac_set), "addresses": sorted(addrs)}
            if len(addrs) > 1:
                issues["SAME_IMAGE_UNRELATED_ADDRESS"].append(entry)
            else:
                # Same street address, different orgs/suites = legitimate shared building.
                issues["SHARED_BUILDING_SAME_ADDRESS"].append({**entry, "cities": sorted(cities)})
        # location-specific image shared across distinct locations
        loc_ids = {str(m.service_location_id) for m in group if m.service_location_id is not None}
        if len(loc_ids) > 1:
            issues["SHARED_LOCATION_SPECIFIC_IMAGE"].append({"image": key[:80], "locations": sorted(loc_ids)})

    for m in media:
        loc = loc_by_fac.get(m.facility_id)
        text = " ".join(filter(None, [m.attribution_text, m.source_url, m.alt_text, m.copyright_owner])).lower()
        # source city mismatch
        if loc and loc.city:
            named = {c for c in _NH_CITIES if c in text}
            if named and loc.city.lower() not in named:
                issues["SOURCE_CITY_MISMATCH"].append(
                    {"facility": str(m.facility_id), "location_city": loc.city, "named_in_source": sorted(named)}
                )
        # hospital image on non-hospital
        caps = caps_by_fac.get(m.facility_id, set())
        is_hosp_fac = "hospital" in caps
        source_reads_hospital = m.source_type == "official_hospital" or "hospital" in text
        if source_reads_hospital and not is_hosp_fac:
            issues["HOSPITAL_IMAGE_ON_NONHOSPITAL"].append(
                {"facility": str(m.facility_id), "capabilities": sorted(caps), "source_type": m.source_type}
            )
        # missing attribution for CC-BY
        lic = (m.license_type or "").lower()
        if any(lic.startswith(p) or p in lic for p in _CC_BY) and not m.attribution_text:
            issues["MISSING_ATTRIBUTION"].append({"facility": str(m.facility_id), "license": m.license_type})

    return issues


def check_urls(media_urls: list[str]) -> list[str]:
    import httpx

    broken: list[str] = []
    with httpx.Client(timeout=15, follow_redirects=True) as http:
        for url in media_urls:
            try:
                r = http.head(url)
                if r.status_code >= 400:
                    r = http.get(url)  # some hosts reject HEAD
                if r.status_code >= 400:
                    broken.append(f"{url} -> {r.status_code}")
            except Exception as exc:  # noqa: BLE001
                broken.append(f"{url} -> {type(exc).__name__}")
    return broken


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-urls", action="store_true")
    args = parser.parse_args()
    with session_factory() as session:
        issues = find_issues(session)
        if args.check_urls:
            urls = [
                u
                for (u,) in session.execute(
                    select(FacilityMedia.cdn_url).where(
                        FacilityMedia.verification_status == "verified",
                        FacilityMedia.cdn_url.is_not(None),
                    )
                )
                if u
            ]
            issues["BROKEN_IMAGE_URL"] = [{"url": b} for b in check_urls(urls)]
    totals = {k: len(v) for k, v in issues.items()}
    print("MEDIA_ISSUES=" + json.dumps({"totals": totals, "issues": issues}, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
