from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import PayerEntity
from packages.search import SearchResult, search
from services.ai.schemas import CareSearchIntent, Locale, SortOption

_ZIP = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
_RADIUS = re.compile(
    r"\b(?:within|under|no more than|less than)?\s*(\d{1,3})\s*(?:mi|mile|miles)\b",
    re.I,
)
_CITY_STATE = re.compile(r"\b(?:near|in|around)\s+([A-Za-z .'-]{2,50}),?\s+([A-Z]{2})\b")
_PAYER_ALIASES = {
    "bcbs": ("blue cross", "blue shield", "bcbs", "anthem"),
    "aetna": ("aetna",),
    "cigna": ("cigna",),
    "tufts": ("tufts",),
}


def _clarification(candidate_names: list[str], query: str) -> tuple[bool, str | None]:
    lowered = query.lower()
    joined = " ".join(name.lower() for name in candidate_names)
    if (
        ("mammogram" in lowered or "mammography" in lowered)
        and "screening" not in lowered
        and "diagnostic" not in lowered
    ):
        return True, "Are you looking for a screening mammogram or a diagnostic mammogram?"
    if (
        re.search(r"\bmri\b|magnetic resonance", lowered)
        and "contrast" not in lowered
        and "with contrast" in joined
        and "without contrast" in joined
    ):
        return True, "Does your order say with contrast, without contrast, or are you not sure?"
    if re.search(r"\bct\b|cat scan|computed tomography", lowered):
        body_terms = ("head", "brain", "chest", "abdomen", "pelvis", "knee", "spine")
        if not any(term in lowered for term in body_terms):
            return True, "What body area is the CT scan for?"
    if ("childbirth" in lowered or "delivery" in lowered) and not any(
        term in lowered for term in ("vaginal", "cesarean", "c-section")
    ):
        return True, "Are you comparing vaginal delivery or cesarean delivery prices?"
    return False, None


def _procedure_candidates(session: Session, query: str) -> list[SearchResult]:
    direct = search(session, query, entity_type="procedure")[:8]
    if direct:
        return direct
    words = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    stop = {"i", "need", "a", "an", "the", "near", "in", "and", "have", "within", "miles"}
    useful = [word for word in words if word.lower() not in stop and not word.isdigit()]
    for width in range(min(4, len(useful)), 0, -1):
        for start in range(len(useful) - width + 1):
            phrase = " ".join(useful[start : start + width])
            matches = search(session, phrase, entity_type="procedure")[:8]
            if matches:
                return matches
    return []


def extract_intent(session: Session, query: str, locale: Locale) -> CareSearchIntent:
    """Conservative deterministic extraction; the model never creates canonical mappings."""
    zip_match = _ZIP.search(query)
    radius_match = _RADIUS.search(query)
    city_match = _CITY_STATE.search(query)
    procedure_results = _procedure_candidates(session, query)
    names = [result.title for result in procedure_results]
    clarification_needed, question = _clarification(names, query)
    candidate = procedure_results[0] if procedure_results else None
    if len(procedure_results) > 1 and procedure_results[0].score == procedure_results[1].score:
        clarification_needed = True
        question = question or "Which of these procedures matches your order?"

    payer = None
    payer_text = None
    lowered = query.lower()
    payer_rows = session.scalars(select(PayerEntity).where(PayerEntity.active.is_(True))).all()
    for row in payer_rows:
        terms = {row.slug.lower(), row.canonical_name.lower()}
        terms.update(_PAYER_ALIASES.get(row.slug.lower(), ()))
        matching = next((term for term in terms if term in lowered), None)
        if matching:
            payer, payer_text = row, matching
            break

    metadata = candidate.metadata if candidate else {}
    slug_value = metadata.get("slug")
    slug = str(slug_value) if isinstance(slug_value, str) else None
    confidence = min((candidate.score / 100), 1.0) if candidate else 0
    return CareSearchIntent(
        query_text=query,
        procedure_candidate_id=candidate.entity_id if candidate else None,
        procedure_slug=slug,
        procedure_name=candidate.title if candidate else None,
        procedure_confidence=confidence,
        procedure_clarification_needed=clarification_needed or candidate is None,
        clarification_question=question
        or ("What procedure are you looking for?" if not candidate else None),
        location_text=(
            city_match.group(0) if city_match else (zip_match.group(0) if zip_match else None)
        ),
        zip=zip_match.group(1) if zip_match else None,
        city=city_match.group(1).strip() if city_match else None,
        state=city_match.group(2).upper() if city_match else "NH",
        radius_miles=float(radius_match.group(1)) if radius_match else None,
        payer_text=payer_text,
        payer_id=payer.id if payer else None,
        payer_slug=payer.slug if payer else None,
        payer_name=payer.canonical_name if payer else None,
        sort=SortOption.DISTANCE if radius_match else SortOption.RELEVANCE,
        locale=locale,
    )
