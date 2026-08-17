# Consumer Healthcare Search Demand Research (NH / Carevero)

Date: 2026-08-17. Purpose: ground Carevero's product/search priorities in real consumer
demand rather than intuition. Scope constraint: Carevero helps consumers **FIND, UNDERSTAND,
and COMPARE** providers, services, and defensible pricing — never diagnosis/treatment/triage.

## Sources

- Peterson-KFF Health System Tracker — price transparency & variation in U.S. health services.
- CMS Hospital Price Transparency (70 CMS-defined shoppable services; ≥300 total).
- eMarketer — "Most consumers aren't price shopping for healthcare services" (64% never shop;
  58% would be encouraged if they knew costs beforehand).
- MDsave / MedicalPriceCheck / Cura4U — colonoscopy, CT, MRI self-pay ranges and search volume
  (colonoscopy ≈ 17,500 monthly "how much does a colonoscopy cost" searches).
- justlabs.health / labtestinsight / eMarketer (Function Health $298M) — DTC self-pay lab demand;
  Quest/LabCorp DTC (questhealth.com, Labcorp OnDemand); CBC ~$25–50, CMP ~$40–90; DTC 20–40%
  below walk-in cash.

## Top demand themes → Carevero support status

| # | Consumer intent | Example wording | Carevero support today | Gap / action |
|---|---|---|---|---|
| 1 | High-cost imaging price shopping (huge variation: MRI 11–22×) | "cheap MRI", "MRI cost", "CT scan price" | **Strong** — provider-neutral comparison live; Derry $325 US ranks cheapest of 26 | Keep; surface range + "what's included" |
| 2 | Colonoscopy cost (very high search volume) | "how much does a colonoscopy cost", "colonoscopy price" | **Strong** — procedure page + hospital cash/negotiated | Add plain-language range context |
| 3 | Mammogram (top shopped, preventive) | "mammogram cost", "who offers mammograms" | **Good** — capability + imaging category | Confirm priced coverage; screening vs diagnostic clarity |
| 4 | Self-pay / uninsured **labs** (fast-growing DTC) | "blood test without insurance", "CBC cash price", "blood work" | **Now strong** — P0 fix: Laboratory category + `payment_context=self_pay`; Quest DTC verified/staged | Finish Quest/LabCorp publish (DTC model); self-pay UI affordance |
| 5 | Provider near me / by city/ZIP | "labs near Nashua", "urgent care near Manchester", "hospital near me" | **Good** — city/ZIP resolution + distance in comparison | Add ZIP/near-me sort affordance in directory |
| 6 | Generic category discovery | "blood work", "imaging", "physical therapy" | **Now strong** — category resolution → members | Keep; ensure clarification not "no match" |
| 7 | Understand price types | "what is discounted cash price", "negotiated rate", "does this include the doctor" | **Partial** — deterministic help text exists | Add component/scope tooltips (cash vs negotiated, facility vs professional) |
| 8 | Urgent care / ER cost | "urgent care cost", "ER price" | **Partial** — capability/location; no visit-price canonical | Canonical gap: urgent-care visit (documented) |
| 9 | Common labs beyond the 50 catalog | "vitamin d test", "psa test", "a1c" | **Gap** — not in canonical catalog | Canonical-gap candidates (documented; not force-mapped) |
| 10 | "My doctor ordered X" (compare, not advise) | "doctor ordered an MRI", "I need an MRI for my knee" | **Safe-handled** — imaging clarification, never advises | Keep the pre-LLM medical boundary |

## Key behavioral facts that shape the product

- **Most people don't shop, but would if cost were visible.** → Carevero's core value is making
  the compare step effortless and trustworthy; reduce friction and jargon, not add features.
- **Self-pay/uninsured is a distinct, growing journey.** → A clear "paying without insurance?"
  path that prioritizes published cash/self-pay data (never claims personalized out-of-pocket).
- **Price variation is enormous and counter-intuitive.** → Show source-grounded ranges/context
  and only rank **directly comparable** prices (never mix DTC/facility/professional components).
- **DTC labs ≠ walk-in facility billing.** → Represent Quest/LabCorp DTC as org/product-level
  bundled prices (test + required physician fee), not fake per-location prices.

## Explicitly out of scope (never build)

Symptom checker, diagnosis, treatment/medication recommender, medical triage ("ER vs urgent care"
for *my symptoms*), "best doctor for your disease", AI health coach. These are medical advice and
are refused pre-LLM by the deterministic gate.
