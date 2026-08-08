"""Synthetic CMS 3.0 wide CSV fixture generator for benchmarking."""

import csv
import io
from decimal import Decimal
from pathlib import Path
from random import Random

DESCRIPTIONS = [
    "COMPREHENSIVE METABOLIC PANEL",
    "COMPLETE BLOOD COUNT WITH DIFFERENTIAL",
    "CHEST X-RAY 2 VIEWS",
    "CT HEAD/BRAIN WITHOUT CONTRAST",
    "MRI BRAIN WITHOUT CONTRAST",
    "URINALYSIS",
    "LIPID PANEL",
    "THYROID STIMULATING HORMONE",
    "HEMOGLOBIN A1C",
    "BASIC METABOLIC PANEL",
    "ELECTROCARDIOGRAM 12 LEAD",
    "PHYSICAL THERAPY EVALUATION",
    "OCCUPATIONAL THERAPY EVALUATION",
    "SPEECH THERAPY EVALUATION",
    "ULTRASOUND ABDOMEN COMPLETE",
    "COLONOSCOPY DIAGNOSTIC",
    "KNEE REPLACEMENT TOTAL",
    "HIP REPLACEMENT TOTAL",
    "APPENDECTOMY LAPAROSCOPIC",
    "CESAREAN DELIVERY",
    "VAGINAL DELIVERY",
    "CARDIAC CATHETERIZATION",
    "ECHOCARDIOGRAM TRANSTHORACIC",
    "PULMONARY FUNCTION TEST",
    "MAMMOGRAM SCREENING BILATERAL",
]

CPT_CODES = [
    "80053",
    "85025",
    "71046",
    "70450",
    "70551",
    "81001",
    "80061",
    "84443",
    "83036",
    "80048",
    "93000",
    "97161",
    "97165",
    "92523",
    "76700",
    "45378",
    "27447",
    "27130",
    "44970",
    "59510",
    "59400",
    "93451",
    "93306",
    "94010",
    "77067",
]

SETTINGS = ["inpatient", "outpatient", "both"]
BILLING_CLASSES = ["facility", "professional"]

PAYER_NAMES = [
    "Anthem Blue Cross",
    "UnitedHealthcare",
    "Cigna",
    "Aetna",
    "Harvard Pilgrim",
    "Tufts Health Plan",
    "Ambetter",
    "Humana",
    "Blue Cross Blue Shield",
    "Molina Healthcare",
    "Oscar Health",
    "WellCare",
    "Centene",
    "Kaiser Permanente",
    "Tricare",
]

PLAN_SUFFIXES = ["PPO", "HMO", "EPO", "POS", "HDHP"]


def generate_cms_wide_fixture(
    path: Path,
    rows: int = 10_000,
    payers: int = 10,
    plans_per_payer: int = 3,
    codes: int | None = None,
    seed: int = 42,
    *,
    include_anomalies: bool = True,
) -> Path:
    """Generate a deterministic CMS 3.0 wide CSV fixture.

    Returns the path to the generated file.
    """
    rng = Random(seed)
    codes = codes or len(CPT_CODES)
    used_payers = PAYER_NAMES[:payers]
    used_plans = PLAN_SUFFIXES[:plans_per_payer]

    # Build header
    base_columns = [
        "description",
        "code|1",
        "code|1|type",
        "setting",
        "billing_class",
        "standard_charge|gross",
        "standard_charge|discounted_cash",
        "standard_charge|min",
        "standard_charge|max",
    ]
    payer_columns: list[str] = []
    for payer_name in used_payers:
        for plan_name in used_plans:
            payer_columns.append(f"standard_charge|{payer_name}|{plan_name}|negotiated_dollar")

    header = base_columns + payer_columns

    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)

    anomaly_rows = set()
    if include_anomalies and rows >= 20:
        # Sprinkle in some known anomalies
        anomaly_rows = {rng.randint(0, rows - 1) for _ in range(min(rows // 50, 20))}

    for i in range(rows):
        desc_idx = i % len(DESCRIPTIONS)
        code_idx = i % codes
        description = DESCRIPTIONS[desc_idx]
        code = CPT_CODES[code_idx] if code_idx < len(CPT_CODES) else f"9{code_idx:04d}"
        setting = SETTINGS[rng.randint(0, len(SETTINGS) - 1)]
        billing_class = BILLING_CLASSES[rng.randint(0, len(BILLING_CLASSES) - 1)]

        gross = Decimal(rng.randint(100, 50000))
        cash = Decimal(rng.randint(50, int(gross)))
        minimum = Decimal(rng.randint(50, int(gross)))
        maximum = Decimal(rng.randint(int(minimum), int(gross) + 500))

        if i in anomaly_rows:
            anomaly_type = rng.choice(["cash_above_gross", "zero", "large"])
            if anomaly_type == "cash_above_gross":
                cash = gross + Decimal(rng.randint(100, 5000))
            elif anomaly_type == "zero":
                cash = Decimal(0)
            else:
                gross = Decimal(rng.randint(1_500_000, 5_000_000))

        base_values = [
            description,
            code,
            "CPT",
            setting,
            billing_class,
            str(gross),
            str(cash),
            str(minimum),
            str(maximum),
        ]

        payer_values: list[str] = []
        for _ in used_payers:
            for _ in used_plans:
                rate = Decimal(rng.randint(50, int(gross) + 200))
                payer_values.append(str(rate))

        writer.writerow(base_values + payer_values)

    path.write_text(buf.getvalue(), encoding="utf-8")
    return path
