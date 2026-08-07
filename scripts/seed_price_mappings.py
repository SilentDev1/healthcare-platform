from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Procedure, ProcedureCodeMapping, ProcedureCodeSystem, session_factory

MAPPINGS = (
    ("mri-brain-without-contrast", "CPT", "70551"),
    ("mri-knee-without-contrast", "CPT", "73721"),
    ("mri-lumbar-spine-without-contrast", "CPT", "72148"),
    ("ct-abdomen-pelvis", "CPT", "74176"),
    ("ct-chest", "CPT", "71250"),
    ("chest-x-ray", "CPT", "71046"),
    ("screening-mammogram", "CPT", "77067"),
    ("diagnostic-mammogram", "CPT", "77066"),
    ("abdominal-ultrasound", "CPT", "76700"),
    ("pelvic-ultrasound", "CPT", "76856"),
    ("colonoscopy", "CPT", "45378"),
    ("upper-endoscopy", "CPT", "43235"),
    ("complete-blood-count", "CPT", "85025"),
    ("comprehensive-metabolic-panel", "CPT", "80053"),
)


def seed_price_mappings(session: Session) -> int:
    inserted = 0
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
