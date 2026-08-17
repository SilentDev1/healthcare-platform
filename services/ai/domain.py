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
    # Price-fabrication attempts — Carevero only ever shows verified published
    # prices; asking it to invent/fake/change a price is an injection, refused
    # before any LLM/formatter runs (defense-in-depth with the grounding guard,
    # which independently prevents any AI-authored price).
    r"\b(invent|fabricate|make up|made.?up|fake|falsify|lie about)\b"
    r".{0,30}\b(price|prices|cost|costs|rate|rates|amount|quote)\b",
    r"\b(pretend|make up|invent)\b.{0,25}\bthe (price|cost|rate)\b.{0,15}\bis\b",
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
# These ask the assistant to decide what care a person NEEDS, interpret a result, or triage
# symptoms — NOT to price/find a KNOWN service. The patterns key on advice-seeking structure,
# symptoms, and results, so plain price/find/compare/near queries stay allowed.
_SYMPTOM = (
    r"(pain|hurts?|aching|ache|swollen|swelling|fever|rash|lump|bleeding|bleed|dizzy|dizziness|"
    r"numb|numbness|tingl|cough|sore throat|blurry vision|short(ness)? of breath|chest pain|"
    r"headache|migraine|cramps?|nausea|nauseous|vomit|confus|weak|fatigue|tired|mole|cyst|nodule|"
    r"infection|sick|breathing|ringing in|my ears|urine|pee|urinat|burning|jaundice|yellow skin|"
    r"heartburn|teething|fell|fall|collapsed|unconscious|not responding|can'?t get up|limp|"
    r"swallowed|anxious|panic|depress|suicid|numbness|blood sugar|blood pressure|chest feels)"
)
_MEDICAL_ADVICE = _compile(
    # --- diagnosis-seeking ---
    r"\bwhat (disease|condition|illness) (do i|might i|could i)\b",
    r"\bdo i have (a|an|the)?\b.*\b(cancer\w*|tumou?r|infection|disease|condition|covid|flu|std|diabetes)\b",
    r"\bis (this|it|that|my)\b.{0,30}\b(cancer\w*|tumou?r|serious|malignant|infected|broken|dangerous|normal|bad|concerning)\b",
    r"\b(diagnos)\w*\b",
    r"\bwhat('s| is) wrong with (me|my|him|her|them|my (child|baby|son|daughter|mother|father))\b",
    r"\bwhat('s| is) (causing|going on with)\b",
    r"\bwhat (could|might) (be causing|cause|it be|that be|this be)\b",
    r"\b(could|does|do) (this|it|that|these|my symptoms?) (be|sound like|mean|indicate|point to)\b",
    r"\bwhat (condition|illness|disease) (causes|has|would cause)\b",
    r"\bshould i (be )?worr(y|ied)\b",
    # symptom described AND seeking interpretation/action
    _SYMPTOM + r".{0,40}\b(what|why|is it|is that|could|should i|do i|is this|what's)\b",
    r"\b(what|why|is it|is that|could|should i|do i)\b.{0,40}" + _SYMPTOM,
    # --- test / scan selection (based on symptoms, not a known order) ---
    r"\bwhat (scan|test|imaging|lab|x-?ray|exam|bloodwork|blood test|mri|ct) (should|do) i (get|need|have)\b",
    r"\bwhich (scan|test|imaging|lab|procedure|exam) (is right|should i|do i|would|for)\b",
    r"\b(what|which)\b.{0,20}\b(test|scan|imaging|lab|exam) (should|do) i (get|need)\b",
    r"\bshould i get (a |an |the )?(mri|ct|cat scan|x-?ray|ultrasound|scan|blood test|test|biopsy|imaging)\b",
    r"\bdo i need (a |an |to get )?(surgery|an? operation|a? ?scan|an? ?mri|a? ?ct|an? ?x-?ray|an? ?ultrasound|a? ?biopsy|stitches|antibiotics|a? ?test|bloodwork|imaging)\b",
    r"\b(mri|ct|cat scan|x-?ray|ultrasound|scan) or (a |an |the )?(mri|ct|cat scan|x-?ray|ultrasound|scan)\b",
    r"\bwhat (test|scan|imaging) (tells|shows|checks|detects)\b",
    # --- treatment ---
    r"\bhow (do|should|can) i (treat|cure|fix|heal|get rid of|manage|relieve|deal with)\b",
    r"\bwhat (can i (do|take)|should i do|treatment|cure|remedy) (to|for)\b",
    r"\bwhat (treatment|cure|remedy|medication|medicine) (do|should) i (need|get|take)\b",
    r"\b(treatment|cure|remedy) for (my|this|a|the)\b",
    r"\b(should i|do i need to) get (surgery|an operation)\b",
    r"\bdo i need (surgery|an operation)\b",
    # --- medication / dosage ---
    r"\bwhat (medication|medicine|drug|antibiotic|dose|dosage|painkiller) (should|do|can) i\b",
    r"\bshould i (take|use|stop|start|double|skip|increase|decrease)\b.{0,45}\b(medication|medicine|drug|antibiotic|pill|dose|insulin|ibuprofen|tylenol|acetaminophen|aspirin|advil|amoxicillin)\b",
    r"\bshould i take (ibuprofen|tylenol|acetaminophen|aspirin|advil|amoxicillin|antibiotics|this|any)\b",
    r"\bcan i take\b.{0,25}(ibuprofen|tylenol|acetaminophen|aspirin|advil|antibiotics?|medicine|medication|pills?)\b",
    r"\bhow (much|many) (tylenol|ibuprofen|aspirin|advil|acetaminophen|mg|ml|of|medicine|medication)\b",
    r"\bwhat('s| is)? ?(the )?(right |correct )?(dose|dosage)\b",
    r"\bprescri\w*\b",
    r"\bwhich (allergy )?(medicine|medication|pill|drug|antibiotic)\b",
    r"\bwhat (medicine|medication) (treats|for|should)\b",
    # --- result interpretation ---
    r"\bmy (a1c|hba1c|cholesterol|blood pressure|bp|mri|ct|ultrasound|lab|labs|pathology|thyroid|heart rate|pulse|white blood cell|wbc|glucose|blood sugar|result|test|scan|biopsy|report|ekg|ecg|x-?ray)\b.{0,30}\b(is|was|says|show|shows|showed|found|mentions|came back|reads|of|at)\b",
    r"\bwhat does (my|this|the) (result|mri|ct|lab|scan|report|reading|number|a1c|test)\b.{0,20}\bmean\b",
    r"\binterpret (my|the|these|this)\b",
    r"\bis (that|this|my \w+) (bad|normal|high|low|dangerous|serious|concerning|ok|okay)\b",
    # --- triage (symptom-based ER/urgent-care/wait decisions) ---
    r"\bshould i (go to|visit|call)\b.{0,20}\b(er|emergency|urgent care|hospital|doctor|911|ambulance)\b",
    r"\b(er|emergency room|emergency department|emergency) or (a |an |the )?(urgent care)\b",
    r"\burgent care or (a |an |the )?(er|emergency)\b",
    r"\bdo i need (emergency|urgent) (care|help|room|attention)\b",
    r"\bis (this|it|that|my \w+) (an? )?(emergency|urgent|serious enough)\b",
    r"\b(can|should) (this|it|i) wait\b",
    r"\bis it safe to wait\b",
    r"\b(call|do i (need to )?call) (911|an ambulance|the doctor)\b",
    r"\bbad enough (for|to go to) (the )?(er|emergency|hospital)\b",
    r"\bdo i need to (go to|call|see)\b.{0,20}(er|emergency|doctor|hospital|911)\b",
    # --- cost must never drive medical necessity ---
    r"\b(cheaper|cheap).{0,25}(instead of|than the|option|good enough|is fine|works)\b.{0,20}(mri|ct|scan|test|x-?ray|procedure)?",
    r"\bskip the (expensive|mri|ct|scan|test|procedure)\b",
    r"\bdo i (really|actually) need (that|the|this) (expensive |mri|ct|scan|test|procedure)",
    r"\b(good enough|instead of)\b.{0,20}(mri|ct|scan|test|x-?ray)\b.{0,20}(my doctor|ordered|instead)",
    r"\bchoose the cheaper (procedure|test|scan|option)\b",
    r"\b(avoid|skip)\b.{0,15}(the |that |expensive )?(mri|ct|scan|test|procedure)\b",
    r"\bworth (the cost|it)\b.{0,15}(mri|ct|scan|test|treatment|procedure)?",
    # --- special populations / mental-health crisis ---
    r"\b(don't|do not|dont) want to (live|be alive|be here)\b",
    r"\bsuicid\w*\b",
    r"\b(kill myself|end my life|hurt myself)\b",
    r"\bpanic attack\b",
    r"\b(depress|anxiety|mental health)\w*\b.{0,25}\b(what|should|treatment|help|do)\b",
    r"\bswallowed (something|a |an )\b",
    r"\bis it safe (to|for me to) (exercise|drive|fly|travel|lift)\b",
    r"\b(pregnant|pregnancy)\b.{0,30}\b(cramp|bleed|pain|normal|safe|medication|medicine|symptom)\b",
    r"\bwhich (medications?|medicines?) (are|is) safe\b",
    # --- prompt injection into medical advice ---
    r"\bpretend (you're|you are|to be|that you are) (a |an )?(doctor|physician|nurse|md)\b",
    r"\broleplay as (a |an )?(doctor|physician|nurse|er|md)\b",
    r"\bas (a |an )?(medical (expert|professional)|doctor|physician|nurse|md)\b.{0,30}\b(diagnos|treat|recommend|what|should|medication|test)\b",
    r"\bfor (educational|academic|research) purposes\b.{0,40}\b(medication|medicine|diagnos|treatment|dose|what.{0,5}take)\b",
    r"\byou decide (what|which|whether)\b.{0,25}\b(test|scan|treatment|medication|i need|i should)\b",
    r"\b(just )?tell me (whether|if) i need (a |an |the )?(mri|ct|scan|test|surgery|antibiotics|to)\b",
    r"\bdiagnose me\b",
    r"\bignore\b.{0,25}(rules|instructions)\b.{0,25}(diagnos|medical|tell me what)\b",
    r"\banswer only with (the )?diagnosis\b",
    # --- supplemental (harder edge cases) ---
    r"\bwhat causes (it|this|that)\b",
    r"\bwhat do you think i have\b",
    r"\byour (medical|professional|expert) opinion\b",
    r"\bwhat('s| is) your (medical|professional) opinion\b",
    r"\bis (that|this|it) (a )?(problem|bad|normal|serious|concerning|jaundice|an infection|a heart attack|a stroke)\b",
    r"\bwhat (test|scan|imaging|lab|exam) (confirms|detects|diagnoses|checks for|for)\b",
    r"\bwhich (test|scan|imaging|exam|lab) (detects|confirms|shows|checks|diagnoses|for)\b",
    r"\bdo i need\b.{0,30}\b(surgery|an operation|physical therapy|endoscopy|colonoscopy|mammogram|biopsy|procedure|the er|to come in|to go in)\b",
    r"\bwhat does\b.{0,40}\bmean for (me|my)\b",
    r"\bshould i start (taking )?(a |an |the )?(statin|medication|medicine|antibiotic|insulin|blood thinner|supplement)\b",
    r"\bcan\b.{0,20}\btake\b.{0,25}(ibuprofen|tylenol|acetaminophen|aspirin|advil|antibiotics?|melatonin|statin|medicine|medication|pills?)\b",
    r"\bwhat('s| is)?\s?(a |the )?safe (dose|dosage|amount) of\b",
    r"\bis\b.{0,30}\ban? (emergency|urgent)\b",
    r"\b(can|should)\b.{0,30}\bwait (until|till|til|another|a few|a couple|a day|a week|morning|tomorrow|monday)\b",
    r"\bdo i need (to go to |to see |the |to )?(er|emergency|a doctor|911|urgent care|come in)\b",
    r"\b(mri|ct|scan|test|biopsy|colonoscopy|procedure|x-?ray) is (expensive|too expensive|costly)\b",
    r"\bcan i (just )?get (a |an )?(ultrasound|x-?ray|ct|mri|scan|test)\b.{0,15}instead\b",
    r"\bdo i (really|actually) ?(need|have to get) (this|that|the) (colonoscopy|endoscopy|mammogram|biopsy|procedure|screening|surgery|scan|test|mri|ct)\b",
    r"\b(avoid|skip)\b.{0,15}(the |that )?(biopsy|colonoscopy|endoscopy|surgery|screening|mammogram|mri|ct|scan|test|procedure)\b",
    r"\bas (my|your) (doctor|physician|nurse|md)\b",
    r"\byou('re| are) (a |an |my )?(er |emergency )?(nurse|doctor|physician|md)\b",
    r"\bfor (a |my )?(school|homework|class|assignment) (project|assignment)?\b",
    r"\bwhat (medicine|medication) (treats|for|should|cures)\b",
    r"\bcures my\b",
    # --- ES ---
    r"\bqu[eé] (enfermedad|medicamento|medicina) (tengo|debo|necesito)\b",
    r"\bnecesito (una |un )?(cirug[ií]a|operaci[oó]n|resonancia|tomograf[ií]a|radiograf[ií]a|biopsia)\b",
    r"\bqu[eé] (estudio|prueba|examen|escaner|resonancia|tomograf[ií]a) (debo|necesito|me hago|hacer)\b",
    r"\bme duele\b.{0,30}\b(qu[eé]|necesito|estudio|debo)\b",
    r"\b(debo|deber[ií]a) ir a (la sala de )?(emergencias|urgencias)\b",
    r"\btengo\b.{0,25}\b(dolor|fiebre|hinchaz[oó]n|sangrado|tos)\b.{0,25}\b(qu[eé]|debo|necesito|es)\b",
    r"\bmi (a1c|colesterol|presi[oó]n|resultado|an[aá]lisis)\b.{0,20}\bes (malo|normal|grave|alto)\b",
    r"\bfinge que eres (m[eé]dico|doctor)\b",
    r"\bqu[eé] (medicina|medicamento) (tomo|debo tomar)\b",
    r"\bqu[eé] me pasa\b",
    r"\bes seguro esperar\b",
    r"\b(radiograf[ií]a|resonancia|tomograf[ií]a) o (una |un )?(radiograf[ií]a|resonancia|tomograf[ií]a)\b",
    # --- VI (accent-stripped) ---
    r"\btoi bi benh gi\b",
    r"\btoi co (bi )?(ung thu|benh|nhiem trung)\b",
    r"\btoi (co )?can (phau thuat|mo|chup (mri|ct|x-quang)|xet nghiem|sinh thiet)\b",
    r"\bnen di (cap cuu|phong cap cuu|kham cap cuu|benh vien)\b",
    r"\b(toi )?(nen|can) (uong|dung) thuoc gi\b",
    r"\b(can|nen) chup gi\b",
    r"\b(dau|benh|sot|dau dau|dau lung|dau nguc|dau bung|kho tho|chong mat|buon non|chay mau|ho|te|sung)\b.{0,30}\b(chup gi|xet nghiem gi|nen lam gi|can gi|bi gi|di cap cuu|nen di dau|di dau|di kham o dau|kham o dau|lam sao|lam gi|the nao|co sao khong|co nguy hiem|nen gap bac si|nen di kham|di benh vien|di bac si|co nghiem trong)\b",
    # symptom + where-should-I-go triage (mirror of EN _SYMPTOM + "should i / where")
    r"\b(dau nguc|kho tho|dau tim|dau bung du doi|chay mau|ngat xiu|bat tinh|te liet|noi ban|dot quy)\b.{0,30}\b(nen|can|phai|di dau|di cap cuu|lam gi|lam sao)\b",
    r"\b(toi|em|con|be|me|bo)\b.{0,20}\b(dau nguc|kho tho|dau tim|ngat xiu|bat tinh|te liet|dot quy)\b",
    r"\bbi gi( vay| the| khong)?\b",
    r"\b(gia vo|dong vai)\b.{0,15}\bbac si\b",
    r"\ba1c.{0,25}(co (cao|xau) khong|co sao khong|cao khong)\b",
    r"\b(sot|dau|benh)\b.{0,20}(co )?can di cap cuu\b",
    r"\bnen di cap cuu khong\b",
    r"\bnen di (dau|kham o dau|benh vien nao)\b.{0,20}\b(dau|benh|sot|kho tho|nguc|tim|trieu chung)\b",
    r"\b(trieu chung|benh|dau|sot|kho tho)\b.{0,20}\bnghia la (gi|benh gi)\b",
    # --- ZH ---
    r"我(得了|有|患了).{0,6}(癌|腫瘤|肿瘤|病|感染)",
    r"我(需要|要不要|該不該|该不该).{0,6}(手術|手术|開刀|开刀|做(mri|ct|核磁|檢查|检查|化驗|化验)|生檢|活檢|活检)",
    r"(應該|应该|該|该|要)做(什麼|什么).{0,4}(檢查|检查|掃描|扫描|化驗|化验|test)",
    r"(應該|应该|該|该).{0,6}(急診|急诊|看醫生|看医生|叫救護車|叫救护车)",
    r"(該|该|应该|應該|要).{0,3}(吃|服|服用)(什麼|什么)(藥|药)",
    r"(這|这|我的).{0,10}(正常嗎|正常吗|嚴重嗎|严重吗|是癌症嗎|是癌症吗|要緊嗎|要紧吗|怎麼辦|怎么办)",
    # "is this (very) serious / cancer / a problem?" — 是不是 / 很 qualifiers, no 嗎 particle needed
    r"(這|这|我這|我这|我的|它|那).{0,6}(是不是|會不會|会不会|有沒有|有没有|很|太|挺).{0,4}(嚴重|严重|癌|腫瘤|肿瘤|問題|问题|毛病|危險|危险|要命)",
    r"是不是.{0,6}(很|太)?(嚴重|严重|癌症|癌|生病|有問題|有问题|不正常|要緊|要紧)",
    r"(嚴重|严重|危險|危险|癌症|要不要緊|要不要紧)(嗎|吗|不|呢)",
    r"假(裝|装)你是(醫生|医生|醫師|医师)",
    r"我.{0,6}(疼|痛|不舒服|發燒|发烧|頭暈|头晕).{0,10}(怎麼辦|怎么办|什麼病|什么病|要不要|該|该)",
    r"我的?(a1c|血壓|血压|膽固醇|胆固醇|化驗|化验|報告|报告).{0,10}(正常|嚴重|严重|高|低|怎樣|怎样)",
    r"(發燒|发烧|發熱|发热|咳嗽|頭痛|头痛|胸痛|腰痛|肚子痛).{0,10}(要|需要|該|该|要不要).{0,4}(去|到)?.{0,2}(急診|急诊|醫院|医院|看醫生|看医生)",
    r"(要|需要|要不要|該不該|该不该).{0,4}(去|到).{0,2}(急診|急诊)",
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
