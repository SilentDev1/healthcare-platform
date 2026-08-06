import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Facility, FacilityAlias, FacilityIdentifier, FacilityLocation
from packages.identity.normalization import (
    normalize_address,
    normalize_identifier,
    normalize_name,
    normalize_phone,
)


@dataclass(frozen=True)
class IdentityInput:
    name: str
    address: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    phone: str = ""
    identifiers: dict[str, str] | None = None


@dataclass(frozen=True)
class MatchResult:
    facility_id: uuid.UUID | None
    method: str
    score: float
    reason: str
    exact: bool


def match_facility(session: Session, supplied: IdentityInput) -> MatchResult:
    identifiers = supplied.identifiers or {}
    for identifier_type in ("CMS_CCN", "NPI_ORGANIZATION", "INTERNAL_SOURCE_ID"):
        value = identifiers.get(identifier_type)
        if not value:
            continue
        normalized = normalize_identifier(identifier_type, value)
        matches = session.scalars(
            select(FacilityIdentifier).where(
                FacilityIdentifier.identifier_type == identifier_type,
                FacilityIdentifier.normalized_value == normalized,
                FacilityIdentifier.active.is_(True),
            )
        ).all()
        if len(matches) == 1:
            return MatchResult(
                matches[0].facility_id,
                f"exact_{identifier_type.lower()}",
                1.0,
                f"Exact {identifier_type} match",
                True,
            )
    normalized_name = normalize_name(supplied.name)
    candidates = [
        facility.id
        for facility in session.scalars(select(Facility).where(Facility.active.is_(True)))
        if normalize_name(facility.legal_name) == normalized_name
    ]
    alias_ids = session.scalars(
        select(FacilityAlias.facility_id).where(
            FacilityAlias.normalized_alias == normalized_name,
            FacilityAlias.active.is_(True),
        )
    ).all()
    candidates = list(dict.fromkeys([*candidates, *alias_ids]))
    if supplied.address and candidates:
        for facility_id in candidates:
            location = session.scalar(
                select(FacilityLocation).where(FacilityLocation.facility_id == facility_id)
            )
            if location and normalize_address(location.address_line_1) == normalize_address(
                supplied.address
            ):
                return MatchResult(
                    facility_id,
                    "exact_name_address",
                    0.95,
                    "Exact normalized legal/alias name and address",
                    True,
                )
    if supplied.phone and candidates:
        facilities = session.scalars(select(Facility).where(Facility.id.in_(candidates))).all()
        exact_phone = [
            item
            for item in facilities
            if normalize_phone(item.phone or "") == normalize_phone(supplied.phone)
        ]
        if len(exact_phone) == 1:
            return MatchResult(
                exact_phone[0].id,
                "exact_name_phone",
                0.9,
                "Exact normalized legal/alias name and phone",
                True,
            )
    if len(candidates) == 1:
        return MatchResult(
            candidates[0], "name_only", 0.55, "Name-only match requires human review", False
        )
    return MatchResult(
        None, "no_deterministic_match", 0.0, "No strong deterministic identity match", False
    )
