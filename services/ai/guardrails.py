# Regex-dense guardrail module; long alternations are clearer unwrapped.
# ruff: noqa: E501
from __future__ import annotations

import re

from services.ai.schemas import CareveroAIContext

_MONEY = re.compile(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)")
_MILES = re.compile(r"\b([0-9]+(?:\.\d+)?)\s+miles?\b", re.I)
_PROHIBITED = re.compile(
    r"\b(?:definitely\s+)?(?:in[- ]network|covered|accepts? your insurance|best hospital)\b",
    re.I,
)


def validate_grounded_output(text: str, context: CareveroAIContext) -> bool:
    """Reject factual provider prose that contains values absent from the fact package."""
    allowed_money: set[str] = set()
    allowed_miles: set[str] = set()
    for item in context.facilities:
        for value in (
            item.comparable_cash_price,
            item.selected_insurance_price_min,
            item.selected_insurance_price_max,
            item.savings_difference,
        ):
            if value is not None:
                allowed_money.add(f"{value:,.2f}")
                allowed_money.add(f"{value:,.0f}")
        if item.distance_miles is not None:
            allowed_miles.add(str(item.distance_miles))
    found_money = {match.replace(",", "") for match in _MONEY.findall(text)}
    normalized_allowed_money = {value.replace(",", "") for value in allowed_money}
    if not found_money.issubset(normalized_allowed_money):
        return False
    if not set(_MILES.findall(text)).issubset(allowed_miles):
        return False
    if _PROHIBITED.search(text) is not None:
        return False
    return not contains_medical_advice(text)


# Post-generation medical-safety validator (for any generated PROSE path, e.g. grounded
# explanations). The LLM is never the sole safety mechanism: even after the input
# classifier passes, generated output that gives INDIVIDUALIZED medical guidance —
# a diagnosis, a symptom-based test/treatment/medication recommendation, a triage
# decision, or a personal result interpretation — is discarded and replaced with the
# deterministic Carevero response. Neutral service identification ("a colonoscopy is an
# examination of the colon") is allowed; second-person directives are not.
_MEDICAL_ADVICE_OUTPUT = re.compile(
    r"\byou (probably |likely |may |might |could )?have\b.{0,40}\b(cancer|tumou?r|infection|"
    r"a fracture|appendicitis|a condition|a disease|diabetes|covid|the flu|a heart attack|a stroke)\b"
    r"|\byou (should|need to|must|ought to|may want to) (get|have|schedule|order|book)\b.{0,30}"
    r"\b(an? )?(mri|ct|cat scan|x-?ray|ultrasound|scan|blood test|biopsy|colonoscopy|endoscopy|"
    r"surgery|an operation|imaging|a test)\b"
    r"|\byou (should|need to|must|ought to) (take|start|stop|increase|decrease|double)\b.{0,25}"
    r"\b(medication|medicine|antibiotics?|ibuprofen|tylenol|acetaminophen|aspirin|insulin|a statin|a pill)\b"
    r"|\b(i|we) (recommend|suggest|advise)\b.{0,30}\b(you )?(get|take|see a|go to|start|stop|an? mri|surgery|medication)\b"
    r"|\byou (should|need to|must) (go to|visit)\b.{0,15}\b(the )?(er|emergency room|emergency department|urgent care|hospital)\b"
    r"|\b(this|that|your) (is likely|is probably|indicates|suggests|means you have|points to)\b.{0,30}"
    r"\b(cancer|infection|a fracture|serious|a condition|a disease)\b"
    r"|\byour (a1c|cholesterol|blood pressure|result|lab|mri|ct|scan|reading|level)s?\b.{0,25}"
    r"\b(is|are|means?|indicates?)\b.{0,20}\b(high|low|dangerous|concerning|abnormal|normal|fine|bad)\b"
    r"|\byou (don't|do not) need (that|the|this|an? )\b.{0,20}\b(test|mri|ct|scan|procedure|surgery)\b"
    r"|\b(go to|choose) urgent care\b.{0,20}\b(instead of|rather than)\b.{0,10}\b(the )?er\b"
    r"|\byour symptoms (are not|aren't|don't (sound|seem)) serious\b",
    re.I,
)


def contains_medical_advice(text: str) -> bool:
    """True if generated prose contains disallowed individualized medical guidance."""
    return _MEDICAL_ADVICE_OUTPUT.search(text) is not None
