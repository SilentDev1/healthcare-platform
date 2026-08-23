# Healthcare Consumer Price-Shopping UX Research (2024–2026)

**Purpose:** Evidence base to inform the IA, homepage, search, comparison UX, and plain-language copy for a consumer healthcare price-transparency shopping tool (Carevero — "Know before you go: Search. Compare. Choose.").

**Prepared:** 2026-08 · Sources are cited inline with dates; full list at the bottom.

---

## Executive framing

The core consumer job-to-be-done is narrow and emotional: *"Where should I go for this specific service, and what will it actually cost ME?"* The evidence is consistent that (a) demand/intent is high but actual tool usage is very low, (b) the #1 killer is that raw transparency data (chargemasters, machine-readable files, negotiated-rate spreadsheets) is unusable by ordinary people, and (c) the tools that "work" (NH HealthCost, FAIR Health) succeed by collapsing complexity into a single personalized, plain-language, location-aware number with a range. The product opportunity is to be the usability/plain-language layer, not another data dump.

---

## 1. What consumers actually search for when price-shopping

- **Intent is high, action is low.** ~64% of Americans have *never* price-shopped for a healthcare service, yet **58% say they would be encouraged to shop** if they knew the price of a procedure beforehand (eMarketer, 2024–2025). This gap — high stated desire, low action — is the central design problem: the tool must remove friction, not just publish data.
- **Only <20% have ever looked up a price** before a hospital visit; usage skews young (29% of 18–29 vs 11% of 65+) (Gallup/West Health national survey, n=5,149, Nov 2023–Jan 2024).
- **Search is verbalized as natural-language questions and "near me," not codes.** Consumers type "how much does a colonoscopy cost," "MRI cost near me," "urgent care cost," "cheapest MRI near me." They do NOT search by CPT/DRG codes. Whole third-party businesses (BetterCare, CarePriceGuide, MedicalPriceCheck, CostKits) exist to intercept these exact queries, confirming durable volume.
- **What they shop for = routine, schedulable, high-variation services**: colonoscopies, mammograms, MRIs/CT/imaging, lab/bloodwork, childbirth, physician office visits, and expensive electives like joint replacement (Harvard/eMarketer). Price variation is enormous and is itself the motivator — e.g., colonoscopy cash prices span **$311–$10,353** across 143 hospitals; vaginal childbirth estimates ranged **$0–$55,221** at top hospitals; the same MRI runs **~$400–$800 at an outpatient center vs $2,500–$3,000 at a hospital**.

**Design takeaway:** Model search on Google-style natural language + "near me." Accept plain terms ("blood test," "knee MRI," "stomach scope"), map them silently to codes behind the scenes, and lead with the *range* because the price spread is the emotional hook.

---

## 2. Self-pay / uninsured vs insured — different needs

**Self-pay / uninsured (the underserved, highest-motivation segment):**
- Uninsured adults are far more cost-stressed: **82% say affording care is difficult** (vs 42% insured); **59% report problems paying** for care in the past year (vs 30% insured) (KFF, 2024). The uninsured share **grew in 2024** for the first time since 2019 (KFF/ACS).
- **The self-pay/"cash price" is frequently LOWER than the insured negotiated rate.** A 2024 study (via Forbes) found **half of U.S. hospitals set cash prices below their median negotiated insurance price** for common shoppable services. Cash discounts of **30–50% off chargemaster** are routinely available on request; example: chest X-ray $154 self-pay vs $304.50 with BCBS at Mayo Phoenix.
- Their need is simple and absolute: **one out-the-door cash number, comparable across nearby facilities**, plus the knowledge that asking for a cash/self-pay discount is legitimate. Federal rule requires hospitals to publish discounted cash prices — surface these prominently.

**Insured:**
- Their true cost depends on **plan design** (deductible met? coinsurance? in-network?), not the sticker price. A negotiated rate ≠ what they pay. They need a *personalized out-of-pocket* estimate, which requires plan/deductible inputs.
- The federal **Transparency in Coverage** rule (fully effective 2024) requires payers to offer personalized out-of-pocket estimator tools — but consumers rarely find or use them, leaving a discovery/UX gap.
- Insured shoppers respond to transparency when out-of-pocket exposure is real: NH data showed deductible-holding patients shifted toward lower-cost imaging and cut out-of-pocket spending ~5%.

**Design takeaway:** Treat self-pay/cash as a first-class, default-visible path (it serves the most motivated users and is the simplest number to show accurately). For insured users, offer an *optional* progressive step: "Have insurance? Add your plan/deductible for your personal estimate" — never gate the first useful answer behind an insurance form.

---

## 3. Why consumers ABANDON healthcare cost tools (top friction points)

Ranked by weight of evidence:

1. **Raw data is unusable.** The definitive 2024 JMIR mixed-methods study concluded the "poor usability and inconsistent formats of current price transparency information yielded **no evidence of usefulness for patients**." Chargemasters and machine-readable files are built for regulators/machines, not people (JMIR 2024; MedCity News 2025: hospitals "post dense spreadsheets meant for regulators").
2. **The number shown isn't the number they'll pay.** Gross charges exclude deductibles, copays, self-pay discounts, and financial assistance — "not a reflection of patient responsibility" (CMS FAQ). Users can't tell estimate from final bill, breeding distrust.
3. **You can't add up the pieces.** Insurers pay for *bundles*, so a procedure isn't the sum of line items; consumers can't reconstruct their real cost from a code list (Incidental Economist; AHA).
4. **Jargon wall.** CPT/DRG codes, "negotiated rate," "gross charge," "payer-specific" stop non-experts cold (see §4).
5. **No/false choice + trust in doctor.** Nearly half of metro areas have only 1–2 hospital systems; patients also value continuity with their doctor over price (Incidental Economist). Shopping only feels worth it for schedulable, high-variation services.
6. **Incompleteness/non-compliance.** HHS-OIG (2024): only **63 of 100** sampled hospitals fully followed the rule → tools return "no data," which trains users to give up.
7. **Effort > payoff.** Multi-step forms, required logins, insurance-first gating, and no local/"near me" results exceed the patience of a mobile user with a single question.

**Design takeaway:** Every abandonment cause maps to a design fix — plain language, personalized single number + honest range, "estimate not a bill" labeling, graceful empty-states, and near-me results with minimal input.

---

## 4. Medical terms that confuse patients → plain-language expected

| Confusing term (avoid as primary label) | What it actually means | Plain-language the consumer expects |
|---|---|---|
| **CPT / DRG / HCPCS code** | Billing code for a procedure | Never lead with it. Use "MRI of the knee," "colonoscopy." Keep code as secondary/tooltip detail |
| **CBC** (Complete Blood Count) | Common blood panel | "Basic blood test" / "blood count test" |
| **CMP / BMP** (Comp./Basic Metabolic Panel) | Blood chemistry panels | "Blood chemistry test (kidney, sugar, electrolytes)" |
| **Lipid panel** | Cholesterol test | "Cholesterol test" |
| **Gross charge / chargemaster** | Full list price nobody pays | "List price (before discounts)" — and note "you'll almost never pay this" |
| **Payer-specific negotiated charge/rate** | Insurer-negotiated price | "Your insurance's price" |
| **Discounted cash price / self-pay** | Price if you pay yourself | "Cash price" / "If you pay yourself" |
| **Out-of-pocket / coinsurance / deductible** | Your share | "What you'll pay" / "Your share" (with 1-line explainers) |
| **Diagnostic vs screening** | Changes coverage (esp. colonoscopy) | Explicit toggle + "screening is usually free; diagnostic may cost more" |
| **Facility fee / professional fee / global fee** | Billing scope | "Is the doctor's fee included?" — state scope plainly |

- The AMA now attaches **consumer-friendly descriptors to 11,000+ CPT codes** (and Spanish descriptors) precisely because the codes themselves are opaque (AMA, 2024) — use these descriptor strings, not the numeric codes, as your primary labels.
- **Scope ambiguity is a top trust-breaker:** consumers don't know if a quote includes facility + physician + anesthesia + pathology. Always state what's included/excluded.

**Design takeaway:** Plain-language noun labels first; codes and technical terms demoted to tooltips/"details." Add a one-line "what's included / not included" on every price. Provide a screening-vs-diagnostic toggle where it changes cost/coverage.

---

## 5. Mobile price-search behavior

- **88% of "near me" searches happen on mobile**, and **~46% of all Google searches have local intent** (2024–2026 mobile/local search stats). Healthcare price-shopping is overwhelmingly a mobile, location-first, one-question moment.
- Mobile users want: geolocation ("near me") by default, a single clear number + range above the fold, minimal typing, tap-to-call/tap-to-directions, and no login wall. High-variation, high-stakes queries (MRI, ER vs urgent care) are frequently searched on the phone in the moment of need.
- Younger users (most likely to price-shop) are mobile-native; the tool's first-run experience must be flawless on a phone.

**Design takeaway:** Design mobile-first. Geolocate on load, show one headline price + range + distance per facility, keep inputs to search-term + location, and make "call" and "directions" one tap. Defer insurance/plan inputs to an optional expander.

---

## 6. Competitive review — what the best tools do well / poorly

**New Hampshire HealthCost (state program) — the gold standard for consumer effect.**
- *Does well:* State-run, trusted, plain, gives a *personalized, insurance-aware, location-specific* estimate for schedulable services. It produced real, measured behavior change: imaging prices fell 1–2%, imaging spending fell ~3%, out-of-pocket for imaging fell ~5%; credited with ~$7.9M consumer + $36M insurer savings over 5 years.
- *Poorly / lessons:* Modest overall usage; impact concentrated in a few truly shoppable services (imaging). Being right about the number matters more than breadth. Hospitals later "stumbled" on feeding accurate data (NH Bulletin 2021) — data freshness is fragile.

**FAIR Health Consumer (fairhealthconsumer.org) — best consumer education/UX pattern.**
- *Does well:* Free, consumer-facing; **percentile sliders (20th–90th) show the price *range* on the results page** — a strong pattern for conveying variation honestly. Broadest claims database (52B+ records). Strong plain-language glossary, insurance-basics content, shoppable-services guidance, decision aids, mobile app. Publicly reports that consumers mostly come to understand *out-of-pocket costs and coverage* — validating that the real question is "what will I pay," not "what's the list price."
- *Poorly:* Estimates are regional/claims-based benchmarks, not specific facility prices you can book — less actionable for "which building do I go to."

**Turquoise Health — best facility-specific data + booking direction.**
- *Does well:* Deepest hospital-specific negotiated-rate data; consumer view compares prices near you; "Clear Rates" personalized estimates refreshed monthly; powers real tools (e.g., NYC price-comparison tool). Moving toward "predictable pricing, no surprises."
- *Poorly:* Rooted in complex transparency data; risk of overwhelming lay users without heavy plain-language framing; strongest business is B2B, so consumer polish varies.

**Healthcare Bluebook — "Fair Price" benchmarking.**
- *Does well:* Simple "Fair Price" concept + green/yellow/red "fair-value" signal is an excellent consumer mental model (is this a good deal?). Claims-based across thousands of shoppable procedures.
- *Poorly:* Primarily employer/TPA-distributed (behind a benefits login), not open consumer web; benchmark ≠ your exact bookable price.

**Typical hospital / payer estimators.**
- *Does well:* Payer tools (mandated 2024) can be personalized to your plan/deductible — the most accurate out-of-pocket path when used.
- *Poorly:* Hard to find, login-gated, single-provider (no comparison), jargon-heavy, often incomplete/non-compliant (OIG: 63/100). No cross-facility comparison = defeats the shopping purpose.

**Patterns to adopt:** single personalized number + honest range (FAIR Health sliders), a "good deal?" fair-value signal (Bluebook), facility-specific + location-aware results (Turquoise/NH), trusted plain framing (NH). **Patterns to avoid:** code-first search, chargemaster/spreadsheet dumps, insurance-login gating before any answer, single-provider-only results, unlabeled estimates that read like final bills.

---

## 7. The 8–12 highest-demand shoppable services to prioritize

These recur across CMS's shoppable list, FAIR Health, Harvard/eMarketer shopping data, and third-party cost-lookup sites. Prioritize these for launch (high search volume × high price variation × schedulable):

1. **MRI** (by body part: knee, brain, back/spine) — huge variation ($400 vs $3,000), top mobile "near me" query.
2. **CT scan** — same hospital-vs-outpatient variation dynamic.
3. **X-ray / ultrasound** — high-frequency, low-cost, easy first wins.
4. **Colonoscopy** (screening vs diagnostic) — #1 most-shopped; $311–$10,353 spread; coverage nuance.
5. **Mammogram** (screening) — top-shopped preventive service.
6. **Blood tests / lab panels** (CBC, CMP/BMP, lipid, A1c) — extremely high volume, name-not-code problem acute.
7. **Urgent care visit** — high mobile "cost near me" intent; ER-vs-urgent-care decision.
8. **Primary care / office visit** — frequent, self-pay relevant.
9. **Joint replacement — knee & hip** — high-cost elective, big savings from shopping.
10. **Physical therapy** — recurring, per-visit cost matters.
11. **Childbirth / vaginal & C-section delivery** — most-shopped, extreme variation ($0–$55,221).
12. **Endoscopy / minor outpatient surgery** (e.g., hernia repair, tonsillectomy, vasectomy, cataract) — classic schedulable electives.

**Design takeaway:** Build the homepage and browse IA around these ~12 as tappable "popular services," each with a plain name, an icon, a typical price range, and a screening/diagnostic toggle where relevant.

---

## Top actionable implications for the product (evidence-backed design directives)

1. **Lead with one personalized number + an honest range, not a data table.** The single biggest differentiator of tools that changed behavior (NH HealthCost, FAIR Health sliders) vs those that didn't (chargemaster dumps). *(JMIR 2024; NH studies)*
2. **Search by plain-language service name and "near me," never by CPT/DRG.** Map natural language → codes silently. Accept "blood test," "knee scan," "stomach camera." *(AMA consumer descriptors 2024; local-search stats)*
3. **Make self-pay / cash price a default, first-class result.** Half of hospitals' cash prices beat insured rates; the uninsured are the most motivated segment. Tell users a cash/self-pay discount is their right to ask for. *(Forbes/KFF 2024)*
4. **Make insurance optional and progressive — never a gate.** Show a useful answer first; offer "Add your plan/deductible for your exact out-of-pocket." Insurance-login gating is a top abandonment cause. *(Transparency in Coverage 2024; abandonment evidence)*
5. **Label every price honestly: "Estimate, not a final bill" + what's included/excluded.** Scope ambiguity (facility vs physician vs anesthesia) is a core trust-breaker. *(CMS FAQ; AHA)*
6. **Add a "good deal?" fair-value signal.** A green/yellow/red or "below/at/above typical" cue gives lay users an instant verdict (Bluebook pattern). *(Healthcare Bluebook)*
7. **Design mobile-first with geolocation on load.** 88% of near-me search is mobile; show headline price + range + distance per facility, with tap-to-call and tap-to-directions. *(local/mobile search stats)*
8. **Provide a screening-vs-diagnostic toggle** wherever it changes cost/coverage (colonoscopy, mammogram, imaging) and explain the difference in one line. *(coverage nuance; consumer confusion)*
9. **Ship a built-in plain-language glossary / inline tooltips** for negotiated rate, gross charge, cash price, deductible, coinsurance, out-of-pocket. Demote codes and jargon to "details." *(FAIR Health glossary; health-literacy evidence)*
10. **Launch around the ~12 highest-demand services** as tappable "popular services" cards with plain names, icons, and typical ranges — don't make users know what to type. *(CMS shoppable list; Harvard/eMarketer)*
11. **Handle empty/incomplete data gracefully.** Non-compliance means "no result" is common (OIG 63/100); show nearby alternatives, ranges, or "call for a quote" rather than a dead end. *(HHS-OIG 2024)*
12. **Emphasize facility type as the savings lever.** The dominant, teachable pattern: independent/outpatient centers are far cheaper than hospital outpatient departments for identical imaging/labs. Surface facility type prominently in comparison. *(MRI $400 vs $2,500 evidence; NIHCR)*

---

## Sources

- eMarketer — "Most consumers aren't price shopping for healthcare services" and "Cost of healthcare will drive more consumers to become price-conscious" (2024–2025). https://www.emarketer.com/content/most-consumers-aren-t-price-shopping-healthcare-services
- Gallup / West Health — "Public Awareness and Use of Price Transparency: Report From a National Survey," n=5,149, Nov 2023–Jan 2024. https://pmc.ncbi.nlm.nih.gov/articles/PMC11671781/
- JMIR (2024) — "Usability of Health Care Price Transparency Data in the United States: Mixed Methods Study." https://www.jmir.org/2024/1/e50629/
- KFF — "Americans' Challenges with Health Care Costs" (2024) and Uninsured research (2024). https://www.kff.org/health-costs/americans-challenges-with-health-care-costs/ · https://www.kff.org/topic/uninsured/
- Forbes / Ge Bai (Apr 2024) — "Why Are Cash Prices Lower Than Health Insurance Negotiated Prices?" https://www.forbes.com/sites/gebai/2024/04/21/why-are-cash-prices-lower-than-health-insurance-negotiated-prices/
- The Incidental Economist — "The Promise and Problems of Hospital Price Transparency." https://theincidentaleconomist.com/wordpress/promise-probs-hosp-price-transp/
- MedCity News (Aug 2025) — "Healthcare Price Transparency is Not Enough." https://medcitynews.com/2025/08/healthcare-price-transparency-is-not-enough/
- HHS-OIG (2024) compliance finding (63/100 hospitals) — via AHA / Incidental Economist coverage.
- CMS — Hospital Price Transparency FAQs (gross charge, negotiated rate, cash price definitions). https://www.cms.gov/files/document/hospital-price-transparency-frequently-asked-questions.pdf
- CMS 70 shoppable services list — via Becker's Hospital Review / RevSpring. https://www.beckershospitalreview.com/finance/the-70-cms-mandated-services-hospitals-must-post-online-next-year/
- AMA (2024) — CPT 2024 consumer-friendly descriptors (11,000+ codes; Spanish descriptors). https://www.ama-assn.org/practice-management/cpt/349-ways-cpt-codes-set-prepares-physicians-practicing-2024
- New Hampshire HealthCost impact — Health Affairs / CHCF "Moving Markets" / NH Bulletin (2021). https://www.chcf.org/wp-content/uploads/2017/12/PDF-MovingMarketsNewHampshire.pdf
- FAIR Health Consumer — percentile sliders, glossary, decision aids, analytics on out-of-pocket interest (2024). https://www.fairhealth.org/article/recent-enhancements-to-fair-health-consumer · https://www.prnewswire.com/news-releases/fair-health-consumer-website-analytics-reveal-consumers-interest-in-better-understanding-out-of-pocket-costs-and-coverage-302045476.html
- Turquoise Health — consumer/patients pages, Clear Rates. https://turquoise.health/patients
- Healthcare Bluebook — Fair Price benchmarking (via MD Clarity comparison). https://www.mdclarity.com/alternatives/turquoise-health
- Harvard Gazette — "Colonoscopies and mammograms top list of most-shopped health care services." https://news.harvard.edu/gazette/story/newsplus/colonoscopies-and-mammograms-top-list-of-most-shopped-health-care-services/
- Mobile/local search statistics (2026) — 88% of "near me" searches on mobile; ~46% local intent. https://thestacc.com/blog/mobile-search-statistics/
- NIHCR — hospital outpatient prices vs community settings for identical services. https://www.nihcr.org/analysis/improving-care-delivery/prevention-improving-health/hospital-outpatient-prices/
- Colonoscopy/MRI price-range data — MedicalPriceCheck / BetterCare (2026). https://medicalpricecheck.com/research/colonoscopy-cost/
