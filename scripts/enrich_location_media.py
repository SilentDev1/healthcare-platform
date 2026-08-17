"""Provider-neutral service-location image enrichment (discover -> VERIFY IDENTITY -> attach).

Reuses the Wikimedia Commons pipeline (collectors.facility_media.pipeline) for ANY service
location — hospital, lab, urgent care, ER, imaging, ASC, PT, rehab, chiropractic — not just
hospitals. Candidate discovery is kept STRICTLY separate from approval:

    DISCOVER free-licensed candidate
      -> VERIFY LOCATION IDENTITY (org/name token AND city token must appear in the candidate's
         Commons title/attribution; a bare name match is never enough)
      -> ATTACH as `verified` with full provenance, OR store as `pending` (never shown), OR skip.

A generic placeholder is better than the WRONG building: anything that does not pass strict
identity verification is NOT marked verified, so it never reaches consumers. No fuzzy/visual
matching is ever auto-approved. Only free licenses (CC0/PD/CC-BY/CC-BY-SA) pass the license gate.

Idempotent per (facility, checksum). Read-mostly: with --dry-run (default) it only reports.

Run in the read-only-capable job (needs Cloud SQL + Wikimedia egress):
    gcloud run jobs execute carevero-beta-price-audit --region=us-east4 \
        --args="^|^-m|scripts.enrich_location_media|--state|NH|--only-missing|--apply"
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import re
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.facility_media.pipeline import (
    USER_AGENT,
    MediaCandidate,
    discover_wikimedia,
)
from packages.database import (
    Facility,
    FacilityLocation,
    FacilityMedia,
    LocationCapability,
    Organization,
    session_factory,
)

# Only truly-generic connective/geographic words are stripped. Provider-type words
# (imaging, medical, therapy, ...) are KEPT as distinguishing tokens so a provider whose whole
# name is city + type (e.g. "Derry Imaging") can still verify, while a bare "<city> skyline"
# photo cannot (it lacks the type/brand token).
_STOPWORDS = {"the", "of", "and", "inc", "llc", "new", "hampshire", "nh", "at", "in"}
_TOKEN = re.compile(r"[a-z0-9]+")

# Tokens that signal the file is NOT a real photo of the operating facility (scanned documents,
# maps, records, proposed/other-facility material). Any hit disqualifies the candidate — this
# strengthens verification (a generic placeholder is better than a wrong/non-building image).
_DISQUALIFIERS = {
    "records", "record", "census", "report", "annual", "proposed", "construction", "military",
    "naval", "army", "transcript", "vital", "account", "map", "atlas", "seal", "logo", "coat",
    "arms", "document", "manuscript", "register", "directory", "almshouse", "asylum", "ruins",
    "historical", "demolished", "former", "postcard", "postcards", "engraving", "lithograph",
    "drawing", "sketch", "print", "publisher", "publishing", "tichnor", "vintage", "circa",
}


@dataclass(frozen=True)
class Target:
    facility_id: uuid.UUID
    service_location_id: uuid.UUID
    facility_name: str
    org_name: str | None
    city: str
    state: str
    capability: str


def _distinctive_tokens(*names: str | None) -> set[str]:
    toks: set[str] = set()
    for name in names:
        if not name:
            continue
        for t in _TOKEN.findall(name.lower()):
            if len(t) >= 4 and t not in _STOPWORDS:
                toks.add(t)
    return toks


def verify_identity(
    candidate: MediaCandidate, *, facility_name: str, org_name: str | None, city: str
) -> tuple[bool, str]:
    """STRICT: the candidate must reference BOTH a distinctive org/name token AND the city.

    Returns (verified, reason). This is what prevents attaching another branch, a same-name
    building in a different city, a corporate HQ, or a stock photo.
    """
    haystack = " ".join(
        filter(
            None,
            [candidate.title, candidate.attribution_text, candidate.copyright_owner],
        )
    ).lower()
    if not haystack:
        return False, "no_text_metadata"
    # WORD-BOUNDARY token matching (never substring): "derry" must not match inside
    # "londonderry", and generic prose must not partial-match a brand token.
    hay_tokens = set(_TOKEN.findall(haystack))
    disq = hay_tokens & _DISQUALIFIERS
    if disq:
        return False, f"disqualified:{'+'.join(sorted(disq))}"
    city_tok = city.lower().strip()
    city_parts = set(_TOKEN.findall(city_tok))
    if city_parts and not city_parts.issubset(hay_tokens):
        return False, "city_not_in_candidate"
    # The distinctive provider token must be something OTHER than the city itself, so a generic
    # "<city> skyline" photo can never verify as a specific provider's building.
    name_tokens = _distinctive_tokens(facility_name, org_name) - city_parts
    matched = [t for t in name_tokens if t in hay_tokens]
    if not matched:
        return False, "no_distinctive_name_token"
    return True, f"matched_city+{'+'.join(sorted(matched))}"


def _targets(session: Session, state: str, only_missing: bool, capability: str | None) -> list[Target]:
    rows = session.execute(
        select(Facility, FacilityLocation, Organization)
        .join(FacilityLocation, FacilityLocation.facility_id == Facility.id)
        .outerjoin(Organization, Organization.id == Facility.organization_id)
        .where(
            Facility.active.is_(True),
            FacilityLocation.active.is_(True),
            FacilityLocation.state == state.upper(),
        )
    ).all()
    targets: list[Target] = []
    seen: set[uuid.UUID] = set()
    for facility, location, org in rows:
        if facility.id in seen:
            continue
        caps = list(
            session.scalars(
                select(LocationCapability.capability).where(
                    LocationCapability.facility_location_id == location.id,
                    LocationCapability.active.is_(True),
                )
            )
        )
        cap = caps[0] if caps else "unknown"
        if capability and capability not in caps:
            continue
        if only_missing:
            has_verified = session.scalar(
                select(FacilityMedia.id).where(
                    FacilityMedia.facility_id == facility.id,
                    FacilityMedia.verification_status == "verified",
                )
            )
            if has_verified is not None:
                continue
        seen.add(facility.id)
        targets.append(
            Target(
                facility_id=facility.id,
                service_location_id=location.id,
                facility_name=facility.display_name,
                org_name=org.display_name if org else None,
                city=location.city or "",
                state=location.state or state.upper(),
                capability=cap,
            )
        )
    return targets


def _query_for(t: Target) -> str:
    # Facility display names already embed the city (e.g. "Quest Diagnostics — Nashua");
    # add state to disambiguate same-name buildings elsewhere.
    base = t.facility_name.replace("—", " ")
    return f"{base} {t.state}".strip()


def enrich(
    session: Session,
    *,
    state: str,
    only_missing: bool,
    capability: str | None,
    apply: bool,
    limit: int | None,
    http: httpx.Client | None = None,
) -> dict[str, object]:
    targets = _targets(session, state, only_missing, capability)
    if limit:
        targets = targets[:limit]
    counts = {"candidates_found": 0, "verified_attached": 0, "rejected_identity": 0, "no_free_candidate": 0}
    attached: list[dict[str, str]] = []
    rejected_samples: list[dict[str, str]] = []
    errors: list[str] = []
    owns_http = http is None
    if http is None:
        http = httpx.Client(timeout=25, headers={"User-Agent": USER_AGENT, "Api-User-Agent": USER_AGENT}, follow_redirects=True)
    try:
        for t in targets:
            try:
                candidates = discover_wikimedia(http, _query_for(t), limit=5)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{t.facility_name}: {type(exc).__name__}")
                continue
            free = [c for c in candidates if c.is_free]
            if not free:
                counts["no_free_candidate"] += 1
                continue
            counts["candidates_found"] += 1
            chosen = None
            for c in free:
                ok, reason = verify_identity(c, facility_name=t.facility_name, org_name=t.org_name, city=t.city)
                if ok:
                    chosen = (c, reason)
                    break
            if chosen is None:
                counts["rejected_identity"] += 1
                if len(rejected_samples) < 12:
                    rejected_samples.append({"facility": t.facility_name, "top_candidate": free[0].title})
                continue
            candidate, reason = chosen
            alt = f"Exterior of {t.facility_name} in {t.city}, {t.state}"
            if apply:
                existing = session.scalar(
                    select(FacilityMedia).where(
                        FacilityMedia.facility_id == t.facility_id,
                        FacilityMedia.cdn_url == candidate.image_url,
                    )
                )
                if existing is None:
                    session.add(
                        FacilityMedia(
                            facility_id=t.facility_id,
                            service_location_id=t.service_location_id,
                            media_type="photo",
                            source_url=candidate.description_url or candidate.image_url,
                            cdn_url=candidate.image_url,
                            source_type="wikimedia",
                            source_name="Wikimedia Commons",
                            license_type=candidate.license_type,
                            license_url=candidate.license_url,
                            attribution_text=candidate.attribution_text,
                            copyright_owner=candidate.copyright_owner,
                            verification_status="verified",
                            is_primary=True,
                            width=candidate.width,
                            height=candidate.height,
                            mime_type=candidate.mime_type,
                            alt_text=alt,
                            verified_by="enrich_location_media",
                            review_notes=f"strict-identity: {reason}",
                        )
                    )
            counts["verified_attached"] += 1
            attached.append(
                {"facility": t.facility_name, "capability": t.capability, "title": candidate.title, "reason": reason}
            )
        if apply:
            session.commit()
        else:
            session.rollback()
    finally:
        if owns_http:
            http.close()
    return {
        "targets": len(targets),
        "applied": apply,
        **counts,
        "attached": attached,
        "rejected_samples": rejected_samples,
        "errors": errors,
    }


def _title_from_urls(*urls: str | None) -> str:
    """Reconstruct a Commons file title from a stored source/cdn URL for re-verification."""
    import os
    import urllib.parse

    for url in urls:
        if not url:
            continue
        name = urllib.parse.unquote(os.path.basename(url.split("?")[0]))
        if name:
            return name.replace("_", " ")
    return ""


def purge_unverifiable(session: Session, *, state: str, apply: bool) -> dict[str, object]:
    """Re-verify every enrich-attached media row against the CURRENT strict rule; remove failures.

    Self-healing: if the verification is tightened, previously-attached rows that no longer pass
    are deleted (a generic placeholder is better than a wrong building). Only touches rows this
    tool attached (verified_by='enrich_location_media').
    """
    rows = list(
        session.scalars(
            select(FacilityMedia).where(FacilityMedia.verified_by == "enrich_location_media")
        )
    )
    removed: list[dict[str, str]] = []
    kept = 0
    for m in rows:
        facility = session.get(Facility, m.facility_id)
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == m.facility_id,
                FacilityLocation.active.is_(True),
            )
        )
        org = session.get(Organization, facility.organization_id) if facility and facility.organization_id else None
        title = _title_from_urls(m.source_url, m.cdn_url)
        pseudo = MediaCandidate(
            title=title, image_url=m.cdn_url or "", description_url=m.source_url or "",
            license_type=m.license_type, license_url=m.license_url,
            attribution_text=m.attribution_text, copyright_owner=m.copyright_owner,
            width=m.width, height=m.height, mime_type=m.mime_type, is_free=True,
        )
        ok, reason = verify_identity(
            pseudo,
            facility_name=facility.display_name if facility else "",
            org_name=org.display_name if org else None,
            city=location.city if location else "",
        )
        if ok:
            kept += 1
        else:
            removed.append({"facility": facility.display_name if facility else str(m.facility_id), "title": title[:70], "reason": reason})
            if apply:
                session.delete(m)
    if apply:
        session.commit()
    else:
        session.rollback()
    return {"applied": apply, "reviewed": len(rows), "kept": kept, "removed": len(removed), "removed_detail": removed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    parser.add_argument("--only-missing", action="store_true", help="skip facilities that already have verified media")
    parser.add_argument("--capability", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--purge", action="store_true", help="re-verify existing enriched media, remove failures")
    args = parser.parse_args()
    if args.purge:
        with session_factory() as session:
            result = purge_unverifiable(session, state=args.state, apply=args.apply)
        print("LOCATION_MEDIA_PURGE=" + json.dumps(result, default=str, separators=(",", ":")))
        return
    with session_factory() as session:
        result = enrich(
            session,
            state=args.state,
            only_missing=args.only_missing,
            capability=args.capability,
            apply=args.apply,
            limit=args.limit,
        )
    print("LOCATION_MEDIA_ENRICH=" + json.dumps(result, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
