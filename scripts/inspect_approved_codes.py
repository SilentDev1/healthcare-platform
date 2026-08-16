"""Read-only: dump approved crosswalk codes per procedure and test candidate codes.

Diagnostic for the false-negative audit — determines whether a candidate code the audit
surfaced is (a) genuinely absent from our approved crosswalk, or (b) present under a DIFFERENT
code_system label (CPT vs HCPCS Level-I share the same 5-digit numeric namespace), which would
mean the gap is a code-system normalization issue, not a missing mapping.

Run: python -m scripts.inspect_approved_codes --slugs complete-blood-count,ct-chest,...
     [--test-codes 85025,85027,72148,71250,66984,84443,64721]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from sqlalchemy import select

from packages.database import (
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    session_factory,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slugs", default="")
    parser.add_argument("--test-codes", default="")
    args = parser.parse_args()
    want = {s.strip() for s in args.slugs.split(",") if s.strip()}
    test_codes = {c.strip() for c in args.test_codes.split(",") if c.strip()}

    with session_factory() as session:
        procs = {
            p.id: p.slug
            for p in session.scalars(select(Procedure).where(Procedure.active.is_(True)))
        }
        by_proc: dict[str, list[str]] = defaultdict(list)
        all_codes_by_num: dict[str, set[str]] = defaultdict(set)  # numeric code -> {system}
        for mapping, system in session.execute(
            select(ProcedureCodeMapping, ProcedureCodeSystem).join(
                ProcedureCodeSystem, ProcedureCodeMapping.code_system_id == ProcedureCodeSystem.id
            )
        ).all():
            slug = procs.get(mapping.procedure_id)
            if slug is None:
                continue
            by_proc[slug].append(f"{system.code_system}:{mapping.code}:{mapping.mapping_status}")
            all_codes_by_num[mapping.code].add(system.code_system)

        out = {}
        for slug in sorted(want or by_proc):
            out[slug] = sorted(by_proc.get(slug, []))
        print("APPROVED_CODES=" + json.dumps(out, separators=(",", ":")))

        if test_codes:
            found = {
                code: sorted(all_codes_by_num.get(code, [])) for code in sorted(test_codes)
            }
            print("TEST_CODE_PRESENCE=" + json.dumps(found, separators=(",", ":")))


if __name__ == "__main__":
    main()
