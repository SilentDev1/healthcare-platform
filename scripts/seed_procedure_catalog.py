from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Procedure,
    ProcedureAlias,
    ProcedureBundle,
    ProcedureBundleComponent,
    ProcedureCategory,
    ProcedureCodeSystem,
    session_factory,
)
from packages.identity import normalize_name

CATEGORIES = (
    ("imaging", "Imaging"),
    ("laboratory", "Laboratory"),
    ("preventive", "Preventive care"),
    ("emergency", "Emergency care"),
    ("maternity", "Maternity"),
    # NOTE: consumer categories are clinical service groupings, NOT care settings.
    # "inpatient-surgery" was removed (2026-08-16 taxonomy audit): it is a care SETTING,
    # not a consumer category, and had zero canonical procedures — major surgeries live
    # under their clinical category (e.g. Orthopedics) with setting tracked on the price
    # record. Do not re-add setting-based categories. ("outpatient-surgery" retains
    # members pending its own reviewed reclassification.)
    ("outpatient-surgery", "Outpatient surgery"),
    ("cardiology", "Cardiology"),
    ("orthopedics", "Orthopedics"),
    ("gastroenterology", "Gastroenterology"),
    ("ophthalmology", "Ophthalmology"),
    ("rehabilitation", "Rehabilitation"),
    ("other", "Other services"),
)

SERVICES = (
    ("mri-brain-without-contrast", "MRI brain without contrast", "imaging", "imaging", "brain MRI"),
    ("mri-knee-without-contrast", "MRI knee without contrast", "imaging", "imaging", "knee MRI"),
    (
        "mri-lumbar-spine-without-contrast",
        "MRI lower back without contrast",
        "imaging",
        "imaging",
        "lumbar MRI",
    ),
    ("ct-abdomen-pelvis", "CT scan of abdomen and pelvis", "imaging", "imaging", "abdominal CT"),
    ("ct-chest", "CT scan of the chest", "imaging", "imaging", "chest CT"),
    ("chest-x-ray", "Chest X-ray", "imaging", "imaging", "chest radiograph"),
    ("screening-mammogram", "Screening mammogram", "preventive", "imaging", "breast screening"),
    (
        "diagnostic-mammogram",
        "Diagnostic mammogram",
        "imaging",
        "imaging",
        "diagnostic breast imaging",
    ),
    ("abdominal-ultrasound", "Abdominal ultrasound", "imaging", "imaging", "abdomen sonogram"),
    ("pelvic-ultrasound", "Pelvic ultrasound", "imaging", "imaging", "pelvis sonogram"),
    ("colonoscopy", "Colonoscopy", "gastroenterology", "outpatient", "colon exam"),
    ("upper-endoscopy", "Upper endoscopy", "gastroenterology", "outpatient", "EGD"),
    ("cataract-surgery", "Cataract surgery", "ophthalmology", "outpatient", "cataract removal"),
    ("hernia-repair", "Hernia repair", "outpatient-surgery", "mixed", "hernia surgery"),
    (
        "gallbladder-removal",
        "Gallbladder removal",
        "outpatient-surgery",
        "mixed",
        "cholecystectomy",
    ),
    ("knee-replacement", "Knee replacement", "orthopedics", "mixed", "knee arthroplasty"),
    ("hip-replacement", "Hip replacement", "orthopedics", "mixed", "hip arthroplasty"),
    (
        "carpal-tunnel-release",
        "Carpal tunnel release",
        "orthopedics",
        "outpatient",
        "carpal tunnel surgery",
    ),
    (
        "rotator-cuff-repair",
        "Rotator cuff repair",
        "orthopedics",
        "outpatient",
        "shoulder tendon repair",
    ),
    ("vaginal-delivery", "Vaginal delivery", "maternity", "inpatient", "childbirth"),
    ("cesarean-delivery", "Cesarean delivery", "maternity", "inpatient", "C-section"),
    (
        "ed-visit-level-1",
        "Emergency department visit — level 1",
        "emergency",
        "emergency_department",
        "ED level 1",
    ),
    (
        "ed-visit-level-2",
        "Emergency department visit — level 2",
        "emergency",
        "emergency_department",
        "ED level 2",
    ),
    (
        "ed-visit-level-3",
        "Emergency department visit — level 3",
        "emergency",
        "emergency_department",
        "ED level 3",
    ),
    (
        "ed-visit-level-4",
        "Emergency department visit — level 4",
        "emergency",
        "emergency_department",
        "ED level 4",
    ),
    (
        "ed-visit-level-5",
        "Emergency department visit — level 5",
        "emergency",
        "emergency_department",
        "ED level 5",
    ),
    ("urgent-care-visit", "Urgent care visit", "emergency", "urgent_care", "walk-in care"),
    (
        "physical-therapy-evaluation",
        "Physical therapy evaluation",
        "rehabilitation",
        "office",
        "PT evaluation",
    ),
    ("complete-blood-count", "Complete blood count", "laboratory", "laboratory", "CBC"),
    (
        "comprehensive-metabolic-panel",
        "Comprehensive metabolic panel",
        "laboratory",
        "laboratory",
        "CMP",
    ),
    ("basic-metabolic-panel", "Basic metabolic panel", "laboratory", "laboratory", "BMP"),
    ("lipid-panel", "Cholesterol and lipid panel", "laboratory", "laboratory", "lipid test"),
    ("a1c-test", "Hemoglobin A1C test", "laboratory", "laboratory", "diabetes blood test"),
    ("thyroid-test", "Thyroid-stimulating hormone test", "laboratory", "laboratory", "TSH"),
    ("urinalysis", "Urinalysis", "laboratory", "laboratory", "urine test"),
    ("pregnancy-test", "Pregnancy test", "laboratory", "laboratory", "hCG test"),
    ("strep-test", "Strep throat test", "laboratory", "laboratory", "strep test"),
    ("covid-test", "COVID-19 diagnostic test", "laboratory", "laboratory", "coronavirus test"),
    (
        "surgical-pathology",
        "Surgical pathology examination",
        "laboratory",
        "laboratory",
        "tissue examination",
    ),
    ("pap-test", "Cervical cancer screening test", "preventive", "laboratory", "Pap test"),
    ("bone-density-scan", "Bone density scan", "imaging", "imaging", "DEXA"),
    ("echocardiogram", "Echocardiogram", "cardiology", "outpatient", "heart ultrasound"),
    ("cardiac-stress-test", "Cardiac stress test", "cardiology", "outpatient", "heart stress test"),
    ("electrocardiogram", "Electrocardiogram", "cardiology", "outpatient", "ECG EKG"),
    (
        "cardiac-catheterization",
        "Cardiac catheterization",
        "cardiology",
        "mixed",
        "heart catheterization",
    ),
    ("sleep-study", "Overnight sleep study", "other", "outpatient", "polysomnography"),
    ("allergy-testing", "Allergy testing", "other", "office", "allergy test"),
    ("flu-vaccine", "Flu vaccination", "preventive", "office", "influenza shot"),
    (
        "annual-wellness-visit",
        "Annual wellness visit",
        "preventive",
        "office",
        "preventive checkup",
    ),
    ("dialysis-session", "Dialysis treatment session", "other", "outpatient", "kidney dialysis"),
)

CODE_SYSTEMS = (
    "CPT",
    "HCPCS",
    "MS_DRG",
    "APR_DRG",
    "ICD10PCS",
    "ICD10CM",
    "REV_CODE",
    "NDC",
    "LOCAL",
    "UNKNOWN",
)


@dataclass(frozen=True)
class SeedSummary:
    categories: int
    procedures: int
    aliases: int
    code_systems: int
    bundles: int


def seed_catalog(session: Session) -> SeedSummary:
    categories: dict[str, ProcedureCategory] = {}
    for order, (slug, name) in enumerate(CATEGORIES):
        item = session.scalar(select(ProcedureCategory).where(ProcedureCategory.slug == slug))
        if item is None:
            item = ProcedureCategory(
                slug=slug,
                name=name,
                description=f"Consumer services related to {name.lower()}.",
                sort_order=order,
            )
            session.add(item)
            session.flush()
        categories[slug] = item
    for code in CODE_SYSTEMS:
        if (
            session.scalar(
                select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == code)
            )
            is None
        ):
            session.add(
                ProcedureCodeSystem(
                    code_system=code,
                    display_name=code.replace("_", " "),
                    licensing_notes=(
                        "Codes and official descriptions are governed separately; "
                        "CPT content requires an appropriate AMA license."
                    )
                    if code == "CPT"
                    else "Verify source licensing before public display.",
                    public_display_allowed=code != "CPT",
                )
            )
    for slug, name, category, setting, alias in SERVICES:
        procedure = session.scalar(select(Procedure).where(Procedure.slug == slug))
        if procedure is None:
            procedure = Procedure(
                slug=slug,
                consumer_name=name,
                short_description=f"A consumer-friendly overview of {name.lower()}.",
                long_description=(
                    f"This page explains {name.lower()} in plain language. A bill may include "
                    "multiple facility, professional, laboratory, imaging, or medication services."
                ),
                category_id=categories[category].id,
                service_setting=setting,
                complexity="varies",
                shoppable=setting != "emergency_department",
            )
            session.add(procedure)
            session.flush()
        normalized = normalize_name(alias)
        if (
            session.scalar(
                select(ProcedureAlias).where(
                    ProcedureAlias.procedure_id == procedure.id,
                    ProcedureAlias.normalized_alias == normalized,
                )
            )
            is None
        ):
            session.add(
                ProcedureAlias(
                    procedure_id=procedure.id,
                    alias_name=alias,
                    normalized_alias=normalized,
                    alias_type="consumer_synonym",
                )
            )
    # Extra reviewed consumer aliases (everyday wording -> a single canonical
    # procedure). Deliberately specific: category-level terms like "blood work" or
    # "childbirth" resolve to their category/clarification, not captured here.
    reviewed_aliases: dict[str, tuple[str, ...]] = {
        "cesarean-delivery": ("cesarean", "cesarean section"),
        "urgent-care-visit": ("urgent care", "walk in clinic"),
        "physical-therapy-evaluation": ("physical therapy", "physical therapist"),
        # Natural word-order variants for common imaging (both "knee MRI" and "MRI knee").
        "mri-knee-without-contrast": ("mri knee", "mri of knee", "mri of my knee"),
        "mri-brain-without-contrast": ("mri brain", "brain mri", "mri of head", "head mri"),
        "mri-lumbar-spine-without-contrast": ("mri back", "back mri", "lumbar mri"),
        "mri-shoulder-without-contrast": ("mri shoulder", "shoulder mri"),
        "ct-head-without-contrast": ("ct head", "head ct", "ct of head"),
        "ct-chest": ("ct chest", "chest ct", "ct of chest"),
        "ct-abdomen-pelvis": ("ct abdomen", "abdominal ct", "ct abdomen pelvis"),
    }
    for slug, extra_aliases in reviewed_aliases.items():
        procedure = session.scalar(select(Procedure).where(Procedure.slug == slug))
        if procedure is None:
            continue
        for alias in extra_aliases:
            normalized = normalize_name(alias)
            if (
                session.scalar(
                    select(ProcedureAlias).where(
                        ProcedureAlias.procedure_id == procedure.id,
                        ProcedureAlias.normalized_alias == normalized,
                    )
                )
                is None
            ):
                session.add(
                    ProcedureAlias(
                        procedure_id=procedure.id,
                        alias_name=alias,
                        normalized_alias=normalized,
                        alias_type="consumer_synonym",
                    )
                )
    bundles = (
        (
            "maternity-care-episode",
            "Maternity care episode",
            "maternity_episode",
            "inpatient",
            "vaginal-delivery",
        ),
        (
            "joint-replacement-episode",
            "Joint replacement episode",
            "surgery_episode",
            "inpatient",
            "knee-replacement",
        ),
        (
            "diagnostic-imaging-workup",
            "Diagnostic imaging workup",
            "diagnostic_workup",
            "imaging",
            "ct-abdomen-pelvis",
        ),
    )
    for slug, name, bundle_type, setting, procedure_slug in bundles:
        bundle = session.scalar(select(ProcedureBundle).where(ProcedureBundle.slug == slug))
        if bundle is None:
            bundle = ProcedureBundle(
                slug=slug,
                consumer_name=name,
                description=f"Illustrative components for a {name.lower()}; not a price estimate.",
                bundle_type=bundle_type,
                service_setting=setting,
            )
            session.add(bundle)
            session.flush()
        procedure = session.scalar(select(Procedure).where(Procedure.slug == procedure_slug))
        if (
            procedure
            and session.scalar(
                select(ProcedureBundleComponent.id).where(
                    ProcedureBundleComponent.procedure_bundle_id == bundle.id,
                    ProcedureBundleComponent.procedure_id == procedure.id,
                )
            )
            is None
        ):
            session.add(
                ProcedureBundleComponent(
                    procedure_bundle_id=bundle.id,
                    procedure_id=procedure.id,
                    component_name=procedure.consumer_name,
                    required=True,
                    quantity_min=1,
                    quantity_max=1,
                    notes="Other services may be billed separately.",
                )
            )
    return SeedSummary(
        len(CATEGORIES), len(SERVICES), len(SERVICES), len(CODE_SYSTEMS), len(bundles)
    )


def main() -> None:
    with session_factory() as session:
        summary = seed_catalog(session)
        session.commit()
        print(summary)


if __name__ == "__main__":
    main()
