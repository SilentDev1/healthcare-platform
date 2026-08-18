from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Procedure, ProcedureCodeMapping, ProcedureCodeSystem, session_factory

MAPPINGS = (
    # --- Imaging (original 10 + alternatives) ---
    ("mri-brain-without-contrast", "CPT", "70551"),
    ("mri-knee-without-contrast", "CPT", "73721"),
    ("mri-lumbar-spine-without-contrast", "CPT", "72148"),
    ("ct-abdomen-pelvis", "CPT", "74176"),
    ("ct-abdomen-pelvis", "CPT", "74177"),  # with contrast
    ("ct-abdomen-pelvis", "CPT", "74178"),  # without then with contrast
    ("ct-chest", "CPT", "71250"),
    ("chest-x-ray", "CPT", "71046"),
    ("chest-x-ray", "CPT", "71045"),  # single view
    ("screening-mammogram", "CPT", "77067"),
    ("diagnostic-mammogram", "CPT", "77066"),
    ("abdominal-ultrasound", "CPT", "76700"),
    ("pelvic-ultrasound", "CPT", "76856"),
    ("bone-density-scan", "CPT", "77080"),
    # --- Gastroenterology (original 2 + alternatives) ---
    ("colonoscopy", "CPT", "45378"),
    ("colonoscopy", "CPT", "45380"),  # with biopsy
    ("colonoscopy", "CPT", "45385"),  # with polyp removal
    ("upper-endoscopy", "CPT", "43235"),
    # --- Labs (original 2 + new) ---
    ("complete-blood-count", "CPT", "85025"),
    ("comprehensive-metabolic-panel", "CPT", "80053"),
    ("basic-metabolic-panel", "CPT", "80048"),
    ("lipid-panel", "CPT", "80061"),
    ("a1c-test", "CPT", "83036"),
    ("vitamin-d-test", "CPT", "82306"),
    ("thyroid-test", "CPT", "84443"),
    ("urinalysis", "CPT", "81001"),
    ("pregnancy-test", "CPT", "81025"),
    ("strep-test", "CPT", "87880"),
    ("covid-test", "CPT", "87635"),
    ("surgical-pathology", "CPT", "88305"),
    ("pap-test", "CPT", "88175"),
    # --- Cardiology (+ alternatives) ---
    ("echocardiogram", "CPT", "93306"),
    ("echocardiogram", "CPT", "93303"),  # transthoracic limited
    ("echocardiogram", "CPT", "93307"),  # 2D only
    ("cardiac-stress-test", "CPT", "93015"),
    ("cardiac-stress-test", "CPT", "93017"),  # tracing only
    ("cardiac-stress-test", "CPT", "93018"),  # interpretation only
    ("electrocardiogram", "CPT", "93000"),
    ("electrocardiogram", "CPT", "93005"),  # tracing only
    ("electrocardiogram", "CPT", "93010"),  # interpretation only
    ("cardiac-catheterization", "CPT", "93458"),
    # --- Surgery ---
    ("cataract-surgery", "CPT", "66984"),
    ("hernia-repair", "CPT", "49505"),
    ("gallbladder-removal", "CPT", "47562"),
    ("knee-replacement", "CPT", "27447"),
    ("hip-replacement", "CPT", "27130"),
    ("carpal-tunnel-release", "CPT", "64721"),
    ("rotator-cuff-repair", "CPT", "29827"),
    # --- Maternity (reviewed 2026-08-15; evidence in docs/PROCEDURE_MAPPING_COVERAGE_AUDIT.md) ---
    # Verified against source-data descriptions + MS-DRG definitions. Only the
    # WITHOUT-sterilization/D&C DRG severity split and the delivery CPTs are mapped;
    # sterilization/D&C bundles, vaginal-with-O.R. (768) and VBAC codes are excluded
    # as distinct services/components. Retired 774/775 and 765/766 are kept (still
    # present at ~2 hospitals on older MRFs).
    # Vaginal delivery (facility DRG severity split + delivery CPTs):
    ("vaginal-delivery", "MS_DRG", "807"),  # w/o sterilization/D&C, w/o CC/MCC
    ("vaginal-delivery", "MS_DRG", "806"),  # w/o sterilization/D&C, w/ CC
    ("vaginal-delivery", "MS_DRG", "805"),  # w/o sterilization/D&C, w/ MCC
    ("vaginal-delivery", "MS_DRG", "775"),  # retired: w/o complicating dx
    ("vaginal-delivery", "MS_DRG", "774"),  # retired: w/ complicating dx
    ("vaginal-delivery", "CPT", "59400"),  # routine OB care incl vaginal delivery
    ("vaginal-delivery", "CPT", "59409"),  # vaginal delivery only
    ("vaginal-delivery", "CPT", "59410"),  # vaginal delivery incl postpartum
    # Cesarean delivery (facility DRG severity split + delivery CPTs). NOTE: MS-DRG
    # 767 is "Vaginal delivery w/ sterilization/D&C" (NOT cesarean) — it was
    # previously mis-registered here; removed (a bundled-sterilization service).
    ("cesarean-delivery", "MS_DRG", "788"),  # w/o sterilization, w/o CC/MCC
    ("cesarean-delivery", "MS_DRG", "787"),  # w/o sterilization, w/ CC
    ("cesarean-delivery", "MS_DRG", "786"),  # w/o sterilization, w/ MCC
    ("cesarean-delivery", "MS_DRG", "766"),  # retired: w/o CC/MCC
    ("cesarean-delivery", "MS_DRG", "765"),  # retired: w/ CC/MCC
    ("cesarean-delivery", "CPT", "59510"),  # routine OB care incl cesarean
    ("cesarean-delivery", "CPT", "59514"),  # cesarean delivery only
    ("cesarean-delivery", "CPT", "59515"),  # cesarean delivery incl postpartum
    # MS-DRG 469/470 represent major hip *or* knee replacement and cannot be
    # deterministically assigned to either consumer procedure from the code alone.
    # --- Revenue codes ---
    ("chest-x-ray", "REV_CODE", "0324"),  # diagnostic radiology
    ("complete-blood-count", "REV_CODE", "0300"),  # laboratory
    # --- Emergency department ---
    ("ed-visit-level-1", "CPT", "99281"),
    ("ed-visit-level-2", "CPT", "99282"),
    ("ed-visit-level-3", "CPT", "99283"),
    ("ed-visit-level-4", "CPT", "99284"),
    ("ed-visit-level-5", "CPT", "99285"),
    # --- Office / other ---
    ("urgent-care-visit", "CPT", "99213"),
    ("physical-therapy-evaluation", "CPT", "97161"),
    ("sleep-study", "CPT", "95810"),
    ("allergy-testing", "CPT", "95004"),
    ("flu-vaccine", "CPT", "90686"),
    ("annual-wellness-visit", "HCPCS", "G0438"),
    ("dialysis-session", "CPT", "90935"),
)

# Reviewed mis-registrations to de-approve (kept as rows for provenance, status
# "superseded" so they no longer produce mappings). Deleting them would break the
# FK from any PriceRecordProcedureMapping.source_code_mapping_id that referenced them.
SUPERSEDED: tuple[tuple[str, str, str], ...] = (
    # MS-DRG 767 is "Vaginal delivery w/ sterilization/D&C" (confirmed by source-data
    # descriptions), never a cesarean; it was mis-registered under cesarean-delivery.
    ("cesarean-delivery", "MS_DRG", "767"),
)


def seed_price_mappings(session: Session) -> int:
    inserted = 0
    for slug, system_name, code in SUPERSEDED:
        procedure = session.scalar(select(Procedure).where(Procedure.slug == slug))
        system = session.scalar(
            select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == system_name)
        )
        if procedure and system:
            for pcm in session.scalars(
                select(ProcedureCodeMapping).where(
                    ProcedureCodeMapping.procedure_id == procedure.id,
                    ProcedureCodeMapping.code_system_id == system.id,
                    ProcedureCodeMapping.code == code,
                    ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]),
                )
            ):
                pcm.mapping_status = "superseded"
    for slug, system_name, code in MAPPINGS:
        procedure = session.scalar(select(Procedure).where(Procedure.slug == slug))
        system = session.scalar(
            select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == system_name)
        )
        if (
            procedure
            and system
            and session.scalar(
                select(ProcedureCodeMapping.id).where(
                    ProcedureCodeMapping.procedure_id == procedure.id,
                    ProcedureCodeMapping.code_system_id == system.id,
                    ProcedureCodeMapping.code == code,
                )
            )
            is None
        ):
            session.add(
                ProcedureCodeMapping(
                    procedure_id=procedure.id,
                    code_system_id=system.id,
                    code=code,
                    mapping_status="approved",
                    version="Phase 4 reviewed starter mapping",
                )
            )
            inserted += 1
    session.flush()
    return inserted


def main() -> None:
    with session_factory() as session:
        inserted = seed_price_mappings(session)
        session.commit()
        print(f"approved_mappings_inserted={inserted}")


if __name__ == "__main__":
    main()
