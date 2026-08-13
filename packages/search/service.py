import time
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher

import structlog
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityAlias,
    FacilityIdentifier,
    FacilityLocation,
    FacilityProcedurePriceSummary,
    Procedure,
    ProcedureAlias,
    ProcedureCategory,
    SearchDocument,
)
from packages.identity import normalize_name
from packages.search.categories import consumer_categories

logger = structlog.get_logger()

# Consumer-friendly search synonyms for procedure matching
SYNONYMS: dict[str, list[str]] = {
    "knee replacement": ["total knee arthroplasty", "knee arthroplasty"],
    "hip replacement": ["total hip arthroplasty", "hip arthroplasty"],
    "c-section": ["cesarean delivery", "cesarean section", "c section"],
    "childbirth": ["vaginal delivery", "natural delivery"],
    "heart ultrasound": ["echocardiogram", "echo"],
    "ekg": ["electrocardiogram", "ecg"],
    "ecg": ["electrocardiogram", "ekg"],
    "mri": ["magnetic resonance imaging"],
    "ct scan": ["computed tomography", "cat scan"],
    "cat scan": ["computed tomography", "ct scan"],
    "x-ray": ["radiograph", "x ray", "xray"],
    "dexa": ["bone density scan", "bone density"],
    "cbc": ["complete blood count"],
    "cmp": ["comprehensive metabolic panel"],
    "bmp": ["basic metabolic panel"],
    "tsh": ["thyroid stimulating hormone", "thyroid test"],
    "a1c": ["hemoglobin a1c", "hba1c", "diabetes blood test"],
    "pap smear": ["cervical cancer screening", "pap test"],
    "strep test": ["strep throat test", "rapid strep"],
    "flu shot": ["flu vaccination", "influenza vaccine", "flu vaccine"],
    "colonoscopy": ["colon exam", "colon screening"],
    "cholesterol test": ["lipid panel", "cholesterol panel"],
    "sleep study": ["polysomnography", "sleep test"],
    "pt evaluation": ["physical therapy evaluation", "physical therapy"],
    "er visit": ["emergency department visit", "emergency room visit", "ed visit"],
    "gallbladder surgery": ["cholecystectomy", "gallbladder removal"],
    "hernia surgery": ["hernia repair"],
    "cataract removal": ["cataract surgery"],
    "shoulder surgery": ["rotator cuff repair"],
    "carpal tunnel": ["carpal tunnel release", "carpal tunnel surgery"],
    "dialysis": ["dialysis session", "kidney dialysis", "dialysis treatment"],
    "allergy test": ["allergy testing"],
    "mammogram": ["screening mammogram", "diagnostic mammogram", "breast screening"],
    "ultrasound": ["sonogram", "ultrasonography"],
    "urine test": ["urinalysis"],
    "pregnancy test": ["hcg test"],
    "covid test": ["covid-19 test", "coronavirus test", "covid 19 test"],
    "annual physical": ["annual wellness visit", "preventive checkup", "yearly physical"],
    "stress test": ["cardiac stress test", "heart stress test"],
    "heart cath": ["cardiac catheterization", "heart catheterization"],
    # Reviewed multilingual terms resolve to the same canonical procedure documents.
    "mamografía": ["screening mammogram", "diagnostic mammogram"],
    "resonancia magnética": ["magnetic resonance imaging", "mri"],
    "tomografía computarizada": ["computed tomography", "ct scan"],
    "radiografía": ["x-ray", "radiograph"],
    "colonoscopia": ["colonoscopy"],
    "ecografía": ["ultrasound", "sonogram"],
    "análisis de sangre": ["blood test", "complete blood count"],
    "visita a urgencias": ["emergency department visit", "emergency room visit"],
    "parto": ["vaginal delivery", "cesarean delivery"],
    "chụp nhũ ảnh": ["screening mammogram", "diagnostic mammogram"],
    "chụp cộng hưởng từ": ["magnetic resonance imaging", "mri"],
    "chụp ct": ["computed tomography", "ct scan"],
    "chụp x-quang": ["x-ray", "radiograph"],
    "nội soi đại tràng": ["colonoscopy"],
    "siêu âm": ["ultrasound", "sonogram"],
    "xét nghiệm máu": ["blood test", "complete blood count"],
    "khám cấp cứu": ["emergency department visit", "emergency room visit"],
    "sinh con": ["vaginal delivery", "cesarean delivery"],
    "乳房攝影": ["screening mammogram", "diagnostic mammogram"],
    "磁振造影": ["magnetic resonance imaging", "mri"],
    "電腦斷層掃描": ["computed tomography", "ct scan"],
    "x光": ["x-ray", "radiograph"],
    "大腸鏡": ["colonoscopy"],
    "超音波": ["ultrasound", "sonogram"],
    "血液檢查": ["blood test", "complete blood count"],
    "急診就醫": ["emergency department visit", "emergency room visit"],
    "生產": ["vaginal delivery", "cesarean delivery"],
    "乳房摄影": ["screening mammogram", "diagnostic mammogram"],
    "磁共振成像": ["magnetic resonance imaging", "mri"],
    "ct扫描": ["computed tomography", "ct scan"],
    "x光检查": ["x-ray", "radiograph"],
    "结肠镜检查": ["colonoscopy"],
    "超声检查": ["ultrasound", "sonogram"],
    "血液检查": ["blood test", "complete blood count"],
    "急诊就医": ["emergency department visit", "emergency room visit"],
    "分娩": ["vaginal delivery", "cesarean delivery"],
}


@dataclass(frozen=True)
class SearchResult:
    entity_type: str
    entity_id: uuid.UUID
    title: str
    subtitle: str
    location: str | None
    score: float
    match_reason: str
    matched_term: str
    metadata: dict[str, object]


def rebuild_index(session: Session) -> int:
    session.execute(delete(SearchDocument))
    count = 0
    aliases_by_facility: dict[uuid.UUID, list[str]] = {}
    for alias in session.scalars(select(FacilityAlias).where(FacilityAlias.active.is_(True))):
        aliases_by_facility.setdefault(alias.facility_id, []).append(alias.alias_name)
    identifiers_by_facility: dict[uuid.UUID, list[str]] = {}
    priced_procedures_by_facility: dict[uuid.UUID, int] = {
        facility_id: procedure_count
        for facility_id, procedure_count in session.execute(
            select(
                FacilityProcedurePriceSummary.facility_id,
                func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id)),
            )
            .where(FacilityProcedurePriceSummary.publication_status == "publishable")
            .group_by(FacilityProcedurePriceSummary.facility_id)
        ).all()
    }
    for identifier in session.scalars(
        select(FacilityIdentifier).where(FacilityIdentifier.active.is_(True))
    ):
        if identifier.identifier_type in {"CMS_CCN", "NPI_ORGANIZATION"}:
            identifiers_by_facility.setdefault(identifier.facility_id, []).append(
                identifier.identifier_value
            )
    for facility in session.scalars(select(Facility).where(Facility.active.is_(True))):
        location = session.scalar(
            select(FacilityLocation).where(FacilityLocation.facility_id == facility.id)
        )
        terms = [
            facility.display_name,
            facility.legal_name,
            *aliases_by_facility.get(facility.id, []),
            *identifiers_by_facility.get(facility.id, []),
        ]
        if location:
            terms.extend([location.city, location.county or "", location.postal_code])
        session.add(
            SearchDocument(
                entity_type="facility",
                entity_id=facility.id,
                primary_text=facility.display_name,
                secondary_text=" · ".join(
                    filter(
                        None,
                        [
                            location.city if location else None,
                            location.state if location else None,
                            facility.facility_type,
                        ],
                    )
                ),
                normalized_text=normalize_name(" ".join(terms)),
                state=location.state if location else None,
                city=location.city if location else None,
                postal_code=location.postal_code if location else None,
                active=True,
                metadata_json={
                    "facility_type": facility.facility_type,
                    "aliases": aliases_by_facility.get(facility.id, []),
                    "publishable_procedure_count": priced_procedures_by_facility.get(
                        facility.id, 0
                    ),
                },
            )
        )
        count += 1
    aliases_by_procedure: dict[uuid.UUID, list[str]] = {}
    for procedure_alias in session.scalars(
        select(ProcedureAlias).where(ProcedureAlias.active.is_(True))
    ):
        aliases_by_procedure.setdefault(procedure_alias.procedure_id, []).append(
            procedure_alias.alias_name
        )
    categories = {item.id: item for item in session.scalars(select(ProcedureCategory))}
    priced_procedures = set(
        session.scalars(
            select(FacilityProcedurePriceSummary.procedure_id)
            .where(FacilityProcedurePriceSummary.publication_status == "publishable")
            .distinct()
        )
    )
    for procedure in session.scalars(select(Procedure).where(Procedure.active.is_(True))):
        category = categories[procedure.category_id]
        aliases = aliases_by_procedure.get(procedure.id, [])
        session.add(
            SearchDocument(
                entity_type="procedure",
                entity_id=procedure.id,
                primary_text=procedure.consumer_name,
                secondary_text=category.name,
                normalized_text=normalize_name(
                    " ".join(
                        [
                            procedure.consumer_name,
                            procedure.short_description,
                            category.name,
                            *aliases,
                        ]
                    )
                ),
                active=True,
                metadata_json={
                    "slug": procedure.slug,
                    "category": category.slug,
                    "service_setting": procedure.service_setting,
                    "aliases": aliases,
                    "prices_available": procedure.id in priced_procedures,
                },
            )
        )
        count += 1
    category_registry = consumer_categories()
    procedure_counts: dict[uuid.UUID, int] = {}
    for procedure in session.scalars(select(Procedure).where(Procedure.active.is_(True))):
        procedure_counts[procedure.category_id] = procedure_counts.get(procedure.category_id, 0) + 1
    for category in categories.values():
        consumer_category = category_registry.get(category.slug)
        label = consumer_category.label("en") if consumer_category else category.name
        labels = (
            list(dict.fromkeys([category.name, *consumer_category.labels.values()]))
            if consumer_category
            else [category.name]
        )
        aliases = list(consumer_category.aliases) if consumer_category else []
        session.add(
            SearchDocument(
                entity_type="procedure_category",
                entity_id=category.id,
                primary_text=label,
                secondary_text=category.description,
                normalized_text=normalize_name(
                    " ".join([category.name, category.description, *labels, *aliases])
                ),
                active=category.active,
                metadata_json={
                    "slug": category.slug,
                    "aliases": aliases,
                    "category_labels": labels,
                    "localized_labels": consumer_category.labels if consumer_category else {},
                    "procedure_count": procedure_counts.get(category.id, 0),
                    "navigation_only": True,
                },
            )
        )
        count += 1
    session.flush()
    return count


def search(
    session: Session,
    query: str,
    entity_type: str | None = None,
    state: str | None = None,
    city: str | None = None,
    postal_code: str | None = None,
    category: str | None = None,
    locale: str = "en",
) -> list[SearchResult]:
    started = time.perf_counter()
    canonical_normalized = normalize_name(query)
    normalized = canonical_normalized or " ".join(query.casefold().split())
    query_lower = query.lower().strip()
    synonym_targets = SYNONYMS.get(query_lower, [])
    if not synonym_targets:
        for syn_key, syn_values in SYNONYMS.items():
            if query_lower in syn_key or syn_key in query_lower:
                synonym_targets = syn_values
                break
    statement = select(SearchDocument).where(SearchDocument.active.is_(True))
    if entity_type:
        statement = statement.where(SearchDocument.entity_type == entity_type)
    if state:
        statement = statement.where(SearchDocument.state == state.upper())
    if city:
        statement = statement.where(SearchDocument.city.ilike(city))
    if postal_code:
        statement = statement.where(SearchDocument.postal_code == postal_code)
    if session.bind and session.bind.dialect.name == "postgresql" and canonical_normalized:
        searchable_terms = [normalized, *(normalize_name(term) for term in synonym_targets)]
        statement = statement.where(
            or_(
                *(SearchDocument.normalized_text.ilike(f"%{term}%") for term in searchable_terms),
                func.similarity(SearchDocument.normalized_text, normalized) >= 0.15,
                func.to_tsvector("english", SearchDocument.normalized_text).op("@@")(
                    func.plainto_tsquery("english", normalized)
                ),
            )
        )
    documents = session.scalars(statement).all()
    results: list[SearchResult] = []
    for document in documents:
        if category and document.metadata_json.get("category") != category:
            continue
        primary = normalize_name(document.primary_text)
        words = document.normalized_text.split()
        reason, score = "", 0.0
        aliases_value = document.metadata_json.get("aliases", [])
        aliases = aliases_value if isinstance(aliases_value, list) else []
        category_labels_value = document.metadata_json.get("category_labels", [])
        category_labels = category_labels_value if isinstance(category_labels_value, list) else []
        normalized_category_labels = [
            normalize_name(str(item)) or " ".join(str(item).casefold().split())
            for item in category_labels
        ]
        if (
            document.entity_type == "procedure_category"
            and normalized in normalized_category_labels
        ):
            reason, score = "exact_category", 90.0
        elif document.entity_type == "procedure_category" and normalized in [
            normalize_name(str(item)) or " ".join(str(item).casefold().split()) for item in aliases
        ]:
            reason, score = "reviewed_category_alias", 88.0
        elif (
            document.entity_type == "procedure_category"
            and len(normalized) >= 3
            and any(label.startswith(normalized) for label in normalized_category_labels)
        ):
            reason, score = "category_partial", 70.0
        elif normalized == primary:
            reason, score = "exact_primary", 100.0
        elif normalized in [normalize_name(str(item)) for item in aliases]:
            reason, score = "exact_alias", 95.0
        elif normalized and normalized in document.normalized_text:
            reason, score = (
                "prefix_or_phrase",
                80.0 if any(word.startswith(normalized) for word in words) else 75.0,
            )
        elif len(normalized) >= 4:
            ratio = max(
                (SequenceMatcher(None, normalized, word).ratio() for word in words), default=0
            )
            if ratio >= 0.78:
                reason, score = "conservative_typo", round(ratio * 70, 2)
        if score:
            location = (
                " · ".join(filter(None, [document.city, document.state, document.postal_code]))
                or None
            )
            title = document.primary_text
            if document.entity_type == "procedure_category":
                localized = document.metadata_json.get("localized_labels", {})
                if isinstance(localized, dict):
                    candidate_title = localized.get(locale)
                    if isinstance(candidate_title, str):
                        title = candidate_title
            results.append(
                SearchResult(
                    document.entity_type,
                    document.entity_id,
                    title,
                    document.secondary_text,
                    location,
                    score,
                    reason,
                    query,
                    document.metadata_json,
                )
            )
    # Synonym expansion: check if query matches a synonym and add results for expanded terms
    if synonym_targets:
        seen_ids = {(r.entity_type, r.entity_id) for r in results}
        for synonym_term in synonym_targets:
            syn_normalized = normalize_name(synonym_term)
            for document in documents:
                key = (document.entity_type, document.entity_id)
                if key in seen_ids:
                    continue
                if syn_normalized in document.normalized_text:
                    seen_ids.add(key)
                    location = (
                        " · ".join(
                            filter(None, [document.city, document.state, document.postal_code])
                        )
                        or None
                    )
                    results.append(
                        SearchResult(
                            document.entity_type,
                            document.entity_id,
                            document.primary_text,
                            document.secondary_text,
                            location,
                            85.0,
                            "synonym_expansion",
                            query,
                            document.metadata_json,
                        )
                    )

    # Exact/alias/partial category matches expand to their canonical catalog
    # procedures. This is navigation only: no hospital-price rows are queried or
    # aggregated, and membership updates automatically when the catalog changes.
    matched_category_slugs = {
        str(result.metadata["slug"])
        for result in results
        if result.entity_type == "procedure_category"
        and result.match_reason in {"exact_category", "reviewed_category_alias", "category_partial"}
    }
    if matched_category_slugs and entity_type is None:
        results = [
            result
            for result in results
            if not (
                result.entity_type == "procedure"
                and result.metadata.get("category") in matched_category_slugs
            )
        ]
        seen_ids = {(result.entity_type, result.entity_id) for result in results}
        for document in documents:
            if (
                document.entity_type != "procedure"
                or document.metadata_json.get("category") not in matched_category_slugs
            ):
                continue
            key = (document.entity_type, document.entity_id)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            results.append(
                SearchResult(
                    document.entity_type,
                    document.entity_id,
                    document.primary_text,
                    document.secondary_text,
                    None,
                    60.0,
                    "category_member",
                    query,
                    document.metadata_json,
                )
            )

    results.sort(key=lambda item: (-item.score, item.title.lower(), str(item.entity_id)))
    logger.info(
        "search_completed",
        query_length=len(query),
        result_count=len(results),
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return results
