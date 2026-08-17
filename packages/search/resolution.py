from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum

import structlog
from sqlalchemy.orm import Session

from packages.identity import normalize_name
from packages.search.service import SearchResult, search

logger = structlog.get_logger(service="search_resolution")

_KNEE_SCAN_QUESTIONS = {
    "en": "Which knee scan is on your clinician's order?",
    "es": "¿Qué estudio de la rodilla figura en la orden de su profesional clínico?",
    "vi": "Phiếu chỉ định của bác sĩ ghi loại chụp đầu gối nào?",
    "zh-TW": "您的醫療人員檢查單上寫的是哪一種膝部掃描？",
    "zh-CN": "您的临床医生检查单上写的是哪一种膝部扫描？",
}
# Conservative consumer lead-in phrases stripped ONLY as a fallback when the raw
# query does not resolve — never changes an already-resolving query. Lets natural
# wording ("I need a blood test", "how much is an MRI knee") reach the same
# deterministic resolver as the bare term.
_LEAD_IN = re.compile(
    r"^\s*(?:"
    r"i\s+(?:need|want|require|am\s+looking\s+for)|"
    r"looking\s+for|"
    r"how\s+much\s+(?:is|are|does|for|to\s+get)|"
    r"what(?:'s|\s+is)\s+the\s+(?:cost|price)\s+(?:of|for)|"
    r"(?:the\s+)?(?:cost|price)\s+(?:of|for)|"
    r"get|find|show\s+me|need"
    r")\s+(?:an?\s+|some\s+|my\s+)?",
    re.I,
)


_MID_PHRASE = re.compile(r"\s+(?:for|of|in|on|to)\s+my\s+", re.I)


def _strip_lead_in(query: str) -> str:
    stripped = _LEAD_IN.sub("", query, count=1)
    stripped = _MID_PHRASE.sub(" ", stripped).strip()
    return stripped if len(stripped) >= 2 else query


# --- Deterministic self-pay / uninsured intent -----------------------------
# Recognizing payment context lets a natural consumer question ("I need a blood
# test without insurance") resolve to the SAME procedure/category as the bare
# term, and signals a preference for published cash / self-pay pricing. This is
# pure string logic — never an LLM, never medical.
_PAYMENT_PHRASES: tuple[str, ...] = (
    "without any insurance",
    "without insurance",
    "with no insurance",
    "no health insurance",
    "no insurance",
    "dont have insurance",
    "do not have insurance",
    "don't have insurance",
    "paying out of pocket",
    "pay out of pocket",
    "out of pocket",
    "out-of-pocket",
    "self pay",
    "self-pay",
    "paying cash",
    "pay cash",
    "cash price",
    "cash pay",
    "pay for myself",
    "pay myself",
    "private pay",
    "discounted cash",
    "if i pay cash",
)
_PAYMENT_PHRASES_SORTED: tuple[str, ...] = tuple(
    sorted(_PAYMENT_PHRASES, key=len, reverse=True)
)
# Single-token self-pay signals (checked whole-word).
_PAYMENT_TOKENS: frozenset[str] = frozenset(
    {"uninsured", "selfpay", "copay", "cash", "self"}
)
# Generic conversational / intent filler that is NEVER part of a canonical
# procedure or category name or alias. Deliberately conservative: no token here
# appears in any canonical label/alias (checked against the catalog — e.g. NOT
# "test", "care", "visit", "scan", "blood", "panel", "therapy", "physical").
_NOISE_TOKENS: frozenset[str] = frozenset(
    {
        "i", "we", "im", "id", "am", "need", "needing", "want", "wanting",
        "looking", "look", "for", "get", "getting", "got", "find", "finding",
        "a", "an", "the", "some", "any", "my", "me", "please", "help", "how",
        "much", "is", "are", "does", "do", "can", "could", "would", "where",
        "what", "whats", "which", "who", "to", "of", "on", "at", "and", "or",
        "near", "around", "cost", "costs", "price", "prices", "priced", "pricing",
        "compare", "comparison", "show", "list", "cheapest", "cheap", "affordable",
        "without", "with", "no", "not", "dont", "insurance", "pay", "paying",
        "paid", "out", "pocket", "private",
        # Generic provider-type suffixes — never part of a canonical procedure or
        # category NAME (the categories are "imaging"/"laboratory", not "imaging
        # center"); stripping them lets "find imaging centers" reach "imaging".
        "center", "centers", "centre", "centres", "clinic", "clinics", "facility",
        "facilities", "provider", "providers", "office", "offices", "place",
        "places", "location", "locations",
    }
) | _PAYMENT_TOKENS


def detect_payment_context(query: str) -> str | None:
    """Return "self_pay" when the query expresses uninsured / cash-pay intent."""
    normalized = " ".join(query.casefold().split())
    if any(phrase in normalized for phrase in _PAYMENT_PHRASES):
        return "self_pay"
    tokens = set(re.split(r"[^\w]+", normalized))
    if tokens & _PAYMENT_TOKENS:
        return "self_pay"
    return None


def strip_consumer_noise(query: str) -> str:
    """Remove payment-context phrases and generic intent filler from anywhere in
    the query, leaving the resolvable procedure/category term. Never touches
    CJK (space-free) queries. Returns "" when nothing but noise remains."""
    normalized = " ".join(query.casefold().split())
    for phrase in _PAYMENT_PHRASES_SORTED:
        normalized = normalized.replace(phrase, " ")
    kept = [
        token
        for token in re.split(r"\s+", normalized)
        if token and token not in _NOISE_TOKENS
    ]
    return " ".join(kept).strip()


def _consumer_query_variants(query: str) -> list[str]:
    """Ordered, de-duplicated cleaned variants to retry resolution with when the
    raw query does not resolve. Most-specific transform first."""
    variants: list[str] = []
    seen = {query.casefold().strip()}
    for candidate in (_strip_lead_in(query), strip_consumer_noise(query)):
        key = candidate.casefold().strip()
        if candidate and len(candidate) >= 2 and key not in seen:
            seen.add(key)
            variants.append(candidate)
    return variants


_MEDICAL_BOUNDARY_PREFIX = {
    "en": "Carevero can compare prices once you know which imaging test was ordered. ",
    "es": "Carevero puede comparar precios cuando sepa qué estudio por imágenes se indicó. ",
    "vi": "Carevero có thể so sánh giá khi bạn biết loại chẩn đoán hình ảnh đã được chỉ định. ",
    "zh-TW": "確認醫囑中的影像檢查後，Carevero 才能比較價格。",
    "zh-CN": "确认医嘱中的影像检查后，Carevero 才能比较价格。",
}
_GENERIC_CLARIFICATION = {
    "en": "Which procedure matches your clinician's order?",
    "es": "¿Qué procedimiento coincide con la orden de su profesional clínico?",
    "vi": "Thủ thuật nào phù hợp với phiếu chỉ định của bác sĩ?",
    "zh-TW": "哪一項醫療項目符合您的醫療人員檢查單？",
    "zh-CN": "哪一个医疗项目符合您的临床医生检查单？",
}


class SearchIntentType(StrEnum):
    PROCEDURE = "procedure"
    CATEGORY = "category"
    FACILITY = "facility"
    LOCATION = "location"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SearchResolution:
    intent_type: SearchIntentType
    results: list[SearchResult]
    deterministic_match: bool
    clarification_needed: bool = False
    clarification_question: str | None = None
    ai_fallback_eligible: bool = False
    canonical_category_slug: str | None = None
    location_text: str | None = None
    payment_context: str | None = None


def _is_location_match(query: str, result: SearchResult) -> bool:
    normalized = normalize_name(query)
    return bool(
        result.entity_type == "facility"
        and result.location
        and normalized
        and normalized in normalize_name(result.location)
        and normalized not in normalize_name(result.title)
    )


def resolve_search(
    session: Session,
    query: str,
    *,
    state: str | None = None,
    city: str | None = None,
    postal_code: str | None = None,
    category: str | None = None,
    locale: str = "en",
) -> SearchResolution:
    """Resolve known intents and define the canonical-validation boundary for AI.

    Thin wrapper that attaches deterministic self-pay/uninsured payment context
    (which never changes WHICH results resolve — only signals a cash-price
    preference) to the core resolution.
    """
    resolution = _resolve_search_core(
        session,
        query,
        state=state,
        city=city,
        postal_code=postal_code,
        category=category,
        locale=locale,
    )
    payment_context = detect_payment_context(query)
    if payment_context and resolution.payment_context is None:
        resolution = replace(resolution, payment_context=payment_context)
    return resolution


def _resolve_search_core(
    session: Session,
    query: str,
    *,
    state: str | None = None,
    city: str | None = None,
    postal_code: str | None = None,
    category: str | None = None,
    locale: str = "en",
) -> SearchResolution:
    effective_query = query
    location_text = None
    location_match = re.fullmatch(r"(.+?)\s+(?:near|in)\s+([A-Za-z .'-]{2,80})", query, re.I)
    if location_match:
        proposed_location = location_match.group(2).strip()
        location_results = search(session, proposed_location, entity_type="facility", locale=locale)
        if any(_is_location_match(proposed_location, item) for item in location_results):
            effective_query = location_match.group(1).strip()
            location_text = proposed_location
    normalized = normalize_name(effective_query)
    medical_scan_question = "what scan" in normalized and any(
        term in normalized for term in ("hurt", "hurts", "pain", "need")
    )
    ambiguous_knee_scan = "knee" in normalized and "scan" in normalized
    if medical_scan_question or ambiguous_knee_scan:
        candidates = [
            item
            for item in search(session, "knee", entity_type="procedure", locale=locale)
            if item.metadata.get("category") == "imaging"
        ]
        prefix = _MEDICAL_BOUNDARY_PREFIX.get(locale, _MEDICAL_BOUNDARY_PREFIX["en"])
        question = _KNEE_SCAN_QUESTIONS.get(locale, _KNEE_SCAN_QUESTIONS["en"])
        resolution = SearchResolution(
            intent_type=SearchIntentType.AMBIGUOUS,
            results=candidates,
            deterministic_match=False,
            clarification_needed=True,
            clarification_question=f"{prefix if medical_scan_question else ''}{question}",
        )
        _record(resolution)
        return resolution

    results = search(
        session,
        effective_query,
        state=state,
        city=city,
        postal_code=postal_code,
        category=category,
        locale=locale,
    )
    category_match = next(
        (
            item
            for item in results
            if item.entity_type == "procedure_category"
            and item.match_reason
            in {"exact_category", "reviewed_category_alias", "category_partial"}
        ),
        None,
    )
    if category_match:
        resolution = SearchResolution(
            SearchIntentType.CATEGORY,
            results,
            True,
            canonical_category_slug=str(category_match.metadata["slug"]),
            location_text=location_text,
        )
        _record(resolution)
        return resolution
    if any(
        item.entity_type == "procedure" and item.match_reason in {"exact_primary", "exact_alias"}
        for item in results
    ):
        resolution = SearchResolution(SearchIntentType.PROCEDURE, results, True)
        _record(resolution)
        return resolution
    synonym_candidates = [
        item
        for item in results
        if item.entity_type == "procedure" and item.match_reason == "synonym_expansion"
    ]
    if len(synonym_candidates) == 1:
        resolution = SearchResolution(SearchIntentType.PROCEDURE, synonym_candidates, True)
        _record(resolution)
        return resolution
    if synonym_candidates:
        resolution = SearchResolution(
            SearchIntentType.AMBIGUOUS,
            synonym_candidates,
            False,
            clarification_needed=True,
            clarification_question=_GENERIC_CLARIFICATION.get(locale, _GENERIC_CLARIFICATION["en"]),
            ai_fallback_eligible=True,
        )
        _record(resolution)
        return resolution
    if any(_is_location_match(query, item) for item in results):
        resolution = SearchResolution(SearchIntentType.LOCATION, results, True)
        _record(resolution)
        return resolution
    if any(item.entity_type == "facility" for item in results):
        resolution = SearchResolution(SearchIntentType.FACILITY, results, True)
        _record(resolution)
        return resolution
    # Deterministic phrase/prefix/typo procedure matches that reached here without
    # hitting a more specific intent above (e.g. "CT scan" -> both CT procedures,
    # "mammogram" -> screening + diagnostic) must still render as procedure results
    # rather than collapsing to "0 results". Multi-candidate is expected — the
    # consumer chooses, exactly like the plain catalog search. Ambiguous scans and
    # multi-candidate synonyms were already resolved above, so this branch can never
    # override a clarification. No LLM involved.
    if any(item.entity_type == "procedure" for item in results):
        resolution = SearchResolution(SearchIntentType.PROCEDURE, results, True)
        _record(resolution)
        return resolution
    # Fallback: a natural sentence ("I need a blood test without insurance") did not
    # resolve — retry with consumer lead-in phrases AND self-pay/uninsured/intent
    # filler removed, accepting only a confident (non-unknown) deterministic result.
    # This never overrides an already-resolving query (the raw query was tried above).
    for variant in _consumer_query_variants(query):
        retry = resolve_search(
            session,
            variant,
            state=state,
            city=city,
            postal_code=postal_code,
            category=category,
            locale=locale,
        )
        if retry.intent_type != SearchIntentType.UNKNOWN:
            return retry
    resolution = SearchResolution(
        SearchIntentType.UNKNOWN,
        [],
        False,
        ai_fallback_eligible=True,
    )
    _record(resolution)
    return resolution


def _record(resolution: SearchResolution) -> None:
    """Privacy-conscious metadata only; never log the query text."""
    logger.info(
        "search_resolved",
        intent_type=resolution.intent_type,
        deterministic_match=resolution.deterministic_match,
        clarification_needed=resolution.clarification_needed,
        ai_fallback_eligible=resolution.ai_fallback_eligible,
        result_count=len(resolution.results),
        category_resolution=resolution.canonical_category_slug is not None,
    )
