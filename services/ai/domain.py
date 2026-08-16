"""Layer 1 domain lock: a cheap, deterministic scope classifier.

Carevero AI is a narrowly scoped healthcare price-discovery and Carevero-navigation
assistant, NOT a general chatbot and NOT a medical-advice service. This module runs
BEFORE any model or tool execution and decides one of three domains:

- CAREVERO       — a healthcare service / price / provider / navigation request we may help with
- MEDICAL_ADVICE — a diagnosis / treatment / medication / triage request we must refuse
- OUT_OF_SCOPE   — anything unrelated (general knowledge, coding, politics, prompt injection, ...)

Only CAREVERO requests are allowed to reach the deterministic resolver and, if still
unresolved, the LLM. OUT_OF_SCOPE and MEDICAL_ADVICE short-circuit to a fixed, localized
response with no LLM call. This is one of four defense layers (this classifier, the
system prompt, the structured-intent domain field, and the read-only tool allowlist);
even if a prompt-injection defeats the language layer, the model has no tool that can
act outside Carevero.

The classifier is intentionally conservative about NON-healthcare signals (high
precision) so genuine price questions are never refused, and relies on the deeper
layers for anything it cannot decide from surface text.
"""

# This module is intentionally dense with long regex alternations and CJK refusal
# strings that cannot be wrapped without harming readability; exempt line length here.
# ruff: noqa: E501
from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class DomainClass(StrEnum):
    CAREVERO = "carevero"
    MEDICAL_ADVICE = "medical_advice"
    OUT_OF_SCOPE = "out_of_scope"


# --- Localized responses (no LLM; identical policy in every supported language) ------------

_SCOPE_REFUSAL: dict[str, str] = {
    "en": (
        "I can help with healthcare services, published prices, provider locations, "
        "insurance-price information available in Carevero, and using Carevero."
    ),
    "es": (
        "Puedo ayudar con servicios de salud, precios publicados, ubicaciones de "
        "proveedores, información de precios de seguros disponible en Carevero y el uso "
        "de Carevero."
    ),
    "vi": (
        "Tôi có thể giúp về dịch vụ y tế, giá đã công bố, địa điểm nhà cung cấp, thông "
        "tin giá bảo hiểm có trong Carevero và cách sử dụng Carevero."
    ),
    "zh-CN": (
        "我可以帮助您了解 Carevero 中的医疗服务、公布价格、服务地点、保险价格信息，以及如何使用 Carevero。"
    ),
    "zh-TW": (
        "我可以協助您了解 Carevero 中的醫療服務、公布價格、服務地點、保險價格資訊，以及如何使用 Carevero。"
    ),
}

_MEDICAL_BOUNDARY: dict[str, str] = {
    "en": (
        "Carevero compares prices and shows where services are offered; it can't decide "
        "which service is medically right for you or give medical advice. Once you know "
        "the test or procedure you're looking for, I can help compare available published "
        "prices. For urgent or worsening symptoms, contact a clinician or emergency services."
    ),
    "es": (
        "Carevero compara precios y muestra dónde se ofrecen los servicios; no puede "
        "decidir qué servicio es médicamente adecuado para usted ni dar consejos médicos. "
        "Cuando sepa qué prueba o procedimiento busca, puedo ayudarle a comparar los "
        "precios publicados disponibles. Ante síntomas urgentes o que empeoran, contacte "
        "a un profesional clínico o a los servicios de emergencia."
    ),
    "vi": (
        "Carevero so sánh giá và cho biết nơi cung cấp dịch vụ; Carevero không thể quyết "
        "định dịch vụ nào phù hợp về mặt y tế cho bạn hay đưa ra lời khuyên y tế. Khi bạn "
        "biết xét nghiệm hoặc thủ thuật cần tìm, tôi có thể giúp so sánh các mức giá đã "
        "công bố. Nếu có triệu chứng khẩn cấp hoặc nặng hơn, hãy liên hệ bác sĩ hoặc dịch "
        "vụ cấp cứu."
    ),
    "zh-CN": (
        "Carevero 用于比较价格并显示服务的提供地点；它无法判断哪项服务在医学上适合您，也不提供医疗建议。"
        "当您知道要查找的检查或医疗项目后，我可以帮助比较可获取的公布价格。如有紧急或加重的症状，请联系临床医生或急救服务。"
    ),
    "zh-TW": (
        "Carevero 用於比較價格並顯示服務的提供地點；它無法判斷哪一項服務在醫療上適合您，也不提供醫療建議。"
        "當您知道要查找的檢查或醫療項目後，我可以協助比較可取得的公布價格。若有緊急或惡化的症狀，請聯絡臨床人員或緊急救護服務。"
    ),
}


def scope_refusal(locale: str) -> str:
    return _SCOPE_REFUSAL.get(locale, _SCOPE_REFUSAL["en"])


def medical_boundary(locale: str) -> str:
    return _MEDICAL_BOUNDARY.get(locale, _MEDICAL_BOUNDARY["en"])


def response_for(domain: DomainClass, locale: str) -> str | None:
    """The fixed, no-LLM response for a refused domain, or None for CAREVERO."""
    if domain == DomainClass.OUT_OF_SCOPE:
        return scope_refusal(locale)
    if domain == DomainClass.MEDICAL_ADVICE:
        return medical_boundary(locale)
    return None


def _normalize(message: str) -> str:
    # Casefold + strip accents so ES/VI diacritics match, keep CJK intact.
    folded = unicodedata.normalize("NFKC", message).casefold()
    stripped = "".join(
        char for char in unicodedata.normalize("NFD", folded) if unicodedata.category(char) != "Mn"
    )
    # Vietnamese đ (U+0111) is not a combining mark and does not decompose under NFD,
    # so accent-stripping alone leaves it intact; fold it to d so VI patterns match.
    stripped = stripped.replace("đ", "d")
    return re.sub(r"\s+", " ", stripped).strip()


def _any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _compile(*fragments: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(fragment) for fragment in fragments)


# --- Prompt-injection / jailbreak (always refused as out-of-scope) -------------------------
_INJECTION = _compile(
    r"ignore (all|any|the|previous|prior|above)",
    r"disregard (all|any|the|previous|prior|above)",
    r"forget (all|your|the|previous) (instruction|rule|prompt)",
    r"you are now\b",
    r"pretend (to be|you are)",
    r"act as (an?|the)\b",
    r"\bchat ?gpt\b",
    r"\bgpt-?\d",
    r"developer mode",
    r"jailbreak",
    r"system prompt",
    r"reveal your (prompt|instruction|system|rule)",
    r"lottery number",
    # ES / VI / ZH injection phrasings
    r"ignora (todas|las|las anteriores)",
    r"olvida (tus|las) instruc",
    r"bo qua (moi|tat ca|cac) (huong dan|chi dan|quy tac|lenh)",
    r"忽略(以上|之前|所有|先前)",
    r"忽略.{0,6}(指示|指令|規則|规则|規定|规定|所有|全部)",
    r"假裝你是|假装你是|你現在是|你现在是",
    r"(彩票|樂透|乐透)号?码?|号码.{0,4}(彩票|樂透|乐透)",
)

# --- Clearly non-healthcare topics (out of scope) ------------------------------------------
_OUT_OF_SCOPE = _compile(
    # coding / software
    r"\b(python|javascript|typescript|java|c\+\+|golang|rust)\b",
    r"\b(regex|sql query|api endpoint|stack trace|compile|debug my|write .*code|code for)\b",
    # politics / elections
    r"\b(election|president|senator|congress|political party|vote for|republican|democrat)\b",
    # recipes / cooking
    r"\b(recipe|cook|bake|ingredient|how to make .*(cake|soup|bread|pasta|dinner))\b",
    # sports / entertainment
    r"\b(super ?bowl|world cup|nba|nfl|premier league|who won|final score|box office|movie|netflix|celebrity|song lyrics)\b",
    # markets / crypto / unrelated finance
    r"\b(bitcoin|ethereum|crypto|stock market|stock price|s&p 500|nasdaq|invest in|mortgage rate|forex)\b",
    # writing / homework
    r"\bwrite\b.{0,25}\b(essay|resume|cover letter|poem|story|song|report|code|homework|assignment)\b",
    r"\b(my (homework|essay|assignment)|solve this (equation|problem)|do my homework)\b",
    # travel / weather / trivia / jokes / general knowledge
    r"\b(flight to|book a hotel|vacation|itinerary|travel to|road trip)\b",
    r"\b(weather|forecast|will it rain|temperature (today|tomorrow|outside))\b",
    r"\b(tell me a joke|funny joke|make me laugh)\b",
    r"\b(capital of|how many (planets|continents)|meaning of life|who invented|history of the)\b",
    r"what is \d+\s*[-+x*/]\s*\d+",
    # ES
    r"\b(receta|cocinar|el clima|pron[oó]stico|chiste|ensayo|c[oó]digo|f[uú]tbol|qui[eé]n gan[oó]|bitcoin|acciones)\b",
    r"\bqu[eé] tiempo (hara|hace|habra|va a hacer)\b",
    # VI (accent-stripped)
    r"\b(cong thuc nau|nau an|thoi tiet|du bao thoi tiet|ke chuyen cuoi|bai luan|viet code|bong da|ai (da )?thang|dau tu chung khoan)\b",
    # ZH (simplified + traditional)
    r"(食譜|食谱|做饭|天氣|天气|天氣預報|天气预报|講個笑話|讲个笑话|笑话|作文|寫程式|写代码|足球|誰贏|谁赢|比特幣|比特币|股票)",
)

# --- Medical advice / diagnosis / treatment / triage (refused, healthcare but out of scope)
# These ask the assistant to decide what care a person NEEDS, not to price a known service.
_MEDICAL_ADVICE = _compile(
    r"\bwhat (disease|condition|illness) (do i|might i|could i)\b",
    r"\bdo i have (a|an|the)?\b.*\b(cancer|tumou?r|infection|disease|condition|covid|flu|std)\b",
    r"\bis (this|it|that|my)\b.*\b(cancer|tumou?r|serious|malignant|infected|broken|dangerous)\b",
    r"\b(diagnos)\w*\b",
    r"\bwhat (medication|medicine|drug|antibiotic|dose|dosage) (should|do|can) i\b",
    r"\bshould i (take|use|stop|start)\b.*\b(medication|medicine|drug|antibiotic|pill|dose)\b",
    r"\bprescri\w*\b",
    r"\bdo i need (a |an |to get )?(surgery|an operation|a scan|an mri|a ct|an x-?ray|a biopsy|stitches|antibiotics)\b",
    r"\bwhat (scan|test|procedure|imaging|exam) (should|do) i (get|need|have)\b",
    r"\bwhich (scan|test|procedure) (should|do) i (get|need)\b",
    r"\bshould i (go to|visit) (the )?(er|emergency|urgent care|hospital|doctor)\b",
    r"\b(er|emergency room) or urgent care\b",
    r"\burgent care or (the )?(er|emergency)\b",
    r"\bhow (do i|to) (treat|cure|heal|get rid of)\b",
    r"\b(treatment|cure) for (my|this|a)\b",
    r"\bis it (safe|ok|okay) (to|for me)\b.*\b(take|stop|skip|delay)\b",
    r"\bshould i be worried (about|that)\b",
    # symptom described AND asking what to do
    r"\b(my|i have|i've got|i feel)\b.*\b(pain|swollen|swelling|fever|rash|lump|bleeding|dizzy|chest pain|shortness of breath|numb)\b.*\b(what|should|do i|need)\b",
    r"\bwhat('s| is) wrong with (me|my)\b",
    # ES
    r"\bqu[eé] (enfermedad|medicamento|medicina) (tengo|debo|necesito)\b",
    r"\bnecesito (una |un )?(cirug[ií]a|operaci[oó]n|resonancia|tomograf[ií]a|radiograf[ií]a|biopsia)\b",
    r"\bqu[eé] (estudio|prueba|examen) (debo|necesito) (hacerme|tener)\b",
    r"\b(debo|deber[ií]a) ir a (la sala de )?(emergencias|urgencias)\b",
    r"\btengo\b.*\b(dolor|fiebre|hinchaz[oó]n|sangrado)\b.*\b(qu[eé]|debo|necesito)\b",
    # VI (accent-stripped)
    r"\btoi bi benh gi\b",
    r"\btoi co (bi )?(ung thu|benh|nhiem trung)\b",
    r"\btoi (co )?can (phau thuat|mo|chup (mri|ct|x-quang)|xet nghiem|sinh thiet)\b",
    r"\btoi nen di (cap cuu|phong cap cuu|kham cap cuu|benh vien)\b",
    r"\bnen uong thuoc gi\b",
    # ZH
    r"我(得了|有|患了).{0,6}(癌|腫瘤|肿瘤|病|感染)",
    r"我(需要|要不要|該不該|该不该).{0,6}(手術|手术|開刀|开刀|做(mri|ct|核磁|檢查|检查|化驗|化验)|生檢|活檢|活检)",
    r"我(應該|应该|該|该)(去|不去).{0,4}(急診|急诊|看醫生|看医生|醫院|医院)",
    r"(該|该|应该|應該)(吃|服用)(什麼|什么)藥|(该|該)(吃|服)什么药",
    r"(這|这|我的).{0,8}(正常嗎|正常吗|嚴重嗎|严重吗|是癌症嗎|是癌症吗)",
)

# --- Positive healthcare-service signals (a hint the request is legitimately Carevero) ------
# Not required to be CAREVERO — CAREVERO is the default when nothing above matched — but used
# so a medical-sounding word alone (e.g. "MRI knee price") is never mistaken for advice.
_HEALTHCARE_HINT = _compile(
    r"\b(price|cost|how much|cheap|cheapest|compare|published|cash price|rate|estimate)\b",
    r"\b(mri|ct scan|x-?ray|ultrasound|mammogram|colonoscopy|blood work|lab test|cbc|panel)\b",
    r"\b(hospital|clinic|urgent care|lab|imaging center|provider|near me|near|zip|location)\b",
    r"\b(precio|cu[aá]nto cuesta|comparar|hospital|cl[ií]nica|laboratorio)\b",
    r"\b(gia|bao nhieu|so sanh|benh vien|phong kham|xet nghiem)\b",
    r"(價格|价格|多少錢|多少钱|比較|比较|醫院|医院|診所|诊所|檢驗|检验)",
)


def classify_domain(message: str) -> DomainClass:
    """Deterministically classify a user message into a scope domain.

    Order matters: injection and unambiguous non-healthcare topics are refused first,
    then medical-advice/diagnosis/triage, otherwise the request is treated as CAREVERO
    (the default) and passed to the deterministic resolver / LLM, which enforce scope
    again via the system prompt, the structured-intent domain field, and the tool allowlist.
    """
    text = _normalize(message)
    if not text:
        return DomainClass.OUT_OF_SCOPE
    if _any(_INJECTION, text) or _any(_OUT_OF_SCOPE, text):
        return DomainClass.OUT_OF_SCOPE
    if _any(_MEDICAL_ADVICE, text):
        return DomainClass.MEDICAL_ADVICE
    return DomainClass.CAREVERO


def has_healthcare_hint(message: str) -> bool:
    return _any(_HEALTHCARE_HINT, _normalize(message))
