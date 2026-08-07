import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import InsurancePlanEntity, PayerAlias, PayerEntity

PAYER_SEED = (
    (
        "anthem-blue-cross-blue-shield",
        "Anthem Blue Cross and Blue Shield",
        ("Anthem", "Anthem BCBS", "BCBS Anthem"),
    ),
    ("harvard-pilgrim", "Harvard Pilgrim Health Care", ("Harvard Pilgrim", "HPHC")),
    ("unitedhealthcare", "UnitedHealthcare", ("United Healthcare", "UHC")),
    ("cigna", "Cigna", ("Cigna Healthcare",)),
    ("aetna", "Aetna", ("Aetna Health",)),
    ("ambetter", "Ambetter", ("Ambetter Health",)),
    ("tufts-health-plan", "Tufts Health Plan", ("Tufts",)),
    ("medicare", "Medicare", ("CMS Medicare",)),
    ("medicaid", "Medicaid", ("NH Medicaid",)),
    ("self-pay-cash", "Self-pay / cash", ("Self Pay", "Cash", "Uninsured")),
    ("other-unknown", "Other / unknown", ("Other", "Unknown")),
)


def normalize_payer_name(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\b(inc|llc|corp|corporation|company)\b", "", text).strip()


@dataclass(frozen=True)
class PayerMatch:
    payer_id: object | None
    method: str
    confidence: float


def seed_payers(session: Session) -> int:
    inserted = 0
    for slug, canonical, aliases in PAYER_SEED:
        payer = session.scalar(select(PayerEntity).where(PayerEntity.slug == slug))
        if payer is None:
            payer = PayerEntity(slug=slug, canonical_name=canonical)
            session.add(payer)
            session.flush()
            inserted += 1
        for alias in (canonical, *aliases):
            normalized = normalize_payer_name(alias)
            if (
                session.scalar(
                    select(PayerAlias.id).where(PayerAlias.normalized_alias == normalized)
                )
                is None
            ):
                session.add(
                    PayerAlias(
                        payer_entity_id=payer.id,
                        source_alias=alias,
                        normalized_alias=normalized,
                        confidence_score=1,
                    )
                )
    session.flush()
    return inserted


def match_payer(session: Session, source_name: str | None) -> PayerMatch:
    if not source_name or not source_name.strip():
        return PayerMatch(None, "blank", 0)
    normalized = normalize_payer_name(source_name)
    alias = session.scalar(
        select(PayerAlias).where(
            PayerAlias.normalized_alias == normalized, PayerAlias.active.is_(True)
        )
    )
    return (
        PayerMatch(alias.payer_entity_id, "exact_alias", 1)
        if alias
        else PayerMatch(None, "unknown", 0)
    )


def match_or_create_plan(
    session: Session, payer_id: object | None, source_plan: str | None
) -> object | None:
    if payer_id is None or not source_plan or not source_plan.strip():
        return None
    normalized = normalize_payer_name(source_plan)
    plan = session.scalar(
        select(InsurancePlanEntity).where(
            InsurancePlanEntity.payer_entity_id == payer_id,
            InsurancePlanEntity.normalized_name == normalized,
        )
    )
    if plan:
        return plan.id
    plan = InsurancePlanEntity(
        payer_entity_id=payer_id, canonical_name=source_plan.strip(), normalized_name=normalized
    )
    session.add(plan)
    session.flush()
    return plan.id
