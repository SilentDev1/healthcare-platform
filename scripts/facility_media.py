"""Facility-media CLI: discover, ingest (pending), verify, reject, list, recheck.

State-neutral and reusable for any facility (NH today, MA/nationwide later).
Discovery/ingest NEVER auto-publish; ``verify`` is the explicit human step that
makes a reviewed, correctly-licensed, correct-building image public.

Examples (see docs/FACILITY_MEDIA_POLICY.md):
    python -m scripts.facility_media discover --ccn 300019 --query "Cheshire Medical Center"
    python -m scripts.facility_media ingest --ccn 300019 --query "Cheshire Medical Center"
    python -m scripts.facility_media list --ccn 300019
    python -m scripts.facility_media verify --media <uuid> --by hcao --primary
    python -m scripts.facility_media reject --media <uuid> --by hcao --notes "wrong building"
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.facility_media import (
    discover_wikimedia,
    download_and_validate,
    upsert_pending_media,
)
from packages.database import Facility, FacilityMedia, session_factory
from packages.image_validation import ImageValidationError

_UA = "Carevero-FacilityMedia/1.0 (healthcare price transparency)"


def _client() -> httpx.Client:
    return httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _UA})


def _resolve_facility(session: Session, *, ccn: str | None, facility_id: str | None) -> Facility:
    if facility_id:
        facility = session.get(Facility, uuid.UUID(facility_id))
    elif ccn:
        facility = session.scalar(select(Facility).where(Facility.cms_certification_number == ccn))
    else:
        raise SystemExit("provide --ccn or --facility")
    if facility is None:
        raise SystemExit("facility not found")
    return facility


def cmd_discover(args: argparse.Namespace) -> int:
    with session_factory() as session, _client() as http:
        facility = _resolve_facility(session, ccn=args.ccn, facility_id=args.facility)
        query = args.query or facility.display_name
        candidates = discover_wikimedia(http, query, limit=args.limit)
        print(f"{facility.display_name} — {len(candidates)} candidate(s) for {query!r}")
        for index, candidate in enumerate(candidates):
            flag = "FREE" if candidate.is_free else "non-free"
            print(
                f"  [{index}] {flag} {candidate.license_type or '?'} "
                f"{candidate.width}x{candidate.height} {candidate.title}\n"
                f"       {candidate.image_url}"
            )
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    with session_factory() as session, _client() as http:
        facility = _resolve_facility(session, ccn=args.ccn, facility_id=args.facility)
        query = args.query or facility.display_name
        candidates = [c for c in discover_wikimedia(http, query, limit=args.limit) if c.is_free]
        if not candidates:
            print("no free-licensed candidates found; nothing ingested")
            return 0
        ingested = 0
        for candidate in candidates:
            try:
                data, info = download_and_validate(http, candidate.image_url)
            except (httpx.HTTPError, ImageValidationError) as exc:
                print(f"  skip {candidate.title}: {exc}")
                continue
            media = upsert_pending_media(
                session,
                facility_id=facility.id,
                service_location_id=None,
                candidate=candidate,
                info=info,
                cdn_url=candidate.image_url,
                review_notes=f"discovered via query {query!r}",
            )
            ingested += 1
            print(
                f"  pending media {media.id} — {info.width}x{info.height} "
                f"{candidate.license_type} — {candidate.title}"
            )
            if args.first:
                break
        session.commit()
        print(f"ingested {ingested} pending candidate(s) for {facility.display_name}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    with session_factory() as session:
        facility = _resolve_facility(session, ccn=args.ccn, facility_id=args.facility)
        rows = session.scalars(
            select(FacilityMedia)
            .where(FacilityMedia.facility_id == facility.id)
            .order_by(FacilityMedia.verification_status, FacilityMedia.display_order)
        ).all()
        print(f"{facility.display_name} — {len(rows)} media row(s)")
        for media in rows:
            primary = " PRIMARY" if media.is_primary else ""
            print(
                f"  {media.id} [{media.verification_status}]{primary} "
                f"{media.license_type or '?'} {media.width}x{media.height}\n"
                f"       {media.cdn_url or media.storage_key}"
            )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    with session_factory() as session:
        media = session.get(FacilityMedia, uuid.UUID(args.media))
        if media is None:
            raise SystemExit("media not found")
        if not media.license_type and not args.force:
            raise SystemExit("refusing to verify media with no recorded license (use --force)")
        media.verification_status = "verified"
        media.verified_at = datetime.now(UTC)
        media.verified_by = args.by
        if args.notes:
            media.review_notes = args.notes
        if args.primary:
            for other in session.scalars(
                select(FacilityMedia).where(
                    FacilityMedia.facility_id == media.facility_id,
                    FacilityMedia.service_location_id.is_(media.service_location_id),
                )
            ):
                other.is_primary = other.id == media.id
        session.commit()
        print(f"verified {media.id} (primary={media.is_primary})")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    with session_factory() as session:
        media = session.get(FacilityMedia, uuid.UUID(args.media))
        if media is None:
            raise SystemExit("media not found")
        media.verification_status = "rejected"
        media.is_primary = False
        media.verified_by = args.by
        media.review_notes = args.notes or media.review_notes
        session.commit()
        print(f"rejected {media.id}")
    return 0


def cmd_recheck(args: argparse.Namespace) -> int:
    """Re-validate verified/pending remote assets; mark unreachable ones broken."""
    with session_factory() as session, _client() as http:
        rows = session.scalars(
            select(FacilityMedia).where(
                FacilityMedia.verification_status.in_(["verified", "pending"]),
                FacilityMedia.cdn_url.is_not(None),
            )
        ).all()
        broken = 0
        for media in rows:
            try:
                assert media.cdn_url is not None
                download_and_validate(http, media.cdn_url)
                media.last_checked_at = datetime.now(UTC)
            except (httpx.HTTPError, ImageValidationError, AssertionError) as exc:
                media.verification_status = "broken"
                media.is_primary = False
                media.last_checked_at = datetime.now(UTC)
                broken += 1
                print(f"  broken {media.id}: {exc}")
        session.commit()
        print(f"rechecked {len(rows)} row(s); {broken} marked broken")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carevero facility-media pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_target(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ccn", help="CMS certification number")
        p.add_argument("--facility", help="facility UUID")

    p_discover = sub.add_parser("discover")
    add_target(p_discover)
    p_discover.add_argument("--query")
    p_discover.add_argument("--limit", type=int, default=6)
    p_discover.set_defaults(func=cmd_discover)

    p_ingest = sub.add_parser("ingest")
    add_target(p_ingest)
    p_ingest.add_argument("--query")
    p_ingest.add_argument("--limit", type=int, default=6)
    p_ingest.add_argument(
        "--first", action="store_true", help="ingest only the first free candidate"
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_list = sub.add_parser("list")
    add_target(p_list)
    p_list.set_defaults(func=cmd_list)

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--media", required=True)
    p_verify.add_argument("--by", required=True)
    p_verify.add_argument("--primary", action="store_true")
    p_verify.add_argument("--notes")
    p_verify.add_argument("--force", action="store_true")
    p_verify.set_defaults(func=cmd_verify)

    p_reject = sub.add_parser("reject")
    p_reject.add_argument("--media", required=True)
    p_reject.add_argument("--by", required=True)
    p_reject.add_argument("--notes")
    p_reject.set_defaults(func=cmd_reject)

    p_recheck = sub.add_parser("recheck")
    p_recheck.set_defaults(func=cmd_recheck)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
