"""Read-only audit of cash-price comparability across NH procedures (Phase 4.8).

Finds facility/procedure combinations whose published cash prices span multiple
service settings or billing components — the cases that previously produced
misleading min/max ranges (e.g. Cheshire MRI brain $175 professional vs $1,356
facility). Never mutates data.
"""

import json
from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from packages.database import (
    Facility,
    FacilityProcedurePriceObservation,
    Procedure,
    session_factory,
)

_COMPARABLE_SCOPES = {"global", "combined", "facility", "bundled"}


def main() -> None:
    with session_factory() as session:
        rows = session.execute(
            select(
                Facility.display_name,
                Procedure.slug,
                FacilityProcedurePriceObservation.service_setting,
                FacilityProcedurePriceObservation.included_component_scope,
                FacilityProcedurePriceObservation.amount,
            )
            .join(Facility, Facility.id == FacilityProcedurePriceObservation.facility_id)
            .join(
                Procedure,
                Procedure.id == FacilityProcedurePriceObservation.procedure_id,
            )
            .where(
                FacilityProcedurePriceObservation.price_type == "discounted_cash",
                FacilityProcedurePriceObservation.publication_status == "publishable",
            )
        ).all()

    combos: dict[tuple[str, str], dict[tuple[str, str], set[Decimal]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for hosp, slug, setting, scope, amount in rows:
        if amount is None:
            continue
        combos[(hosp, slug)][(setting, (scope or "unknown").lower())].add(Decimal(str(amount)))

    total = len(combos)
    clean = mixed_setting = mixed_component = partial_only = misleading_range = 0
    examples: list[dict[str, Any]] = []
    for (hosp, slug), groups in combos.items():
        scopes = {scope for _setting, scope in groups}
        settings = {setting for setting, _scope in groups}
        all_amounts = [amt for amts in groups.values() for amt in amts]
        lo, hi = min(all_amounts), max(all_amounts)
        has_comparable = bool(scopes & _COMPARABLE_SCOPES)
        is_mixed_component = len(scopes) > 1
        is_mixed_setting = len(settings) > 1
        wide_ratio = lo > 0 and hi / lo >= Decimal("3")
        if is_mixed_component:
            mixed_component += 1
        if is_mixed_setting:
            mixed_setting += 1
        if not has_comparable:
            partial_only += 1
        would_mislead = (is_mixed_component or is_mixed_setting) and wide_ratio
        if would_mislead:
            misleading_range += 1
            if len(examples) < 25:
                examples.append(
                    {
                        "hospital": hosp,
                        "procedure": slug,
                        "old_range": f"{lo}-{hi}",
                        "groups": {
                            f"{setting}/{scope}": sorted(str(a) for a in amts)
                            for (setting, scope), amts in groups.items()
                        },
                    }
                )
        if not is_mixed_component and not is_mixed_setting:
            clean += 1

    print(
        "PRICE_COMPARABILITY_AUDIT="
        + json.dumps(
            {
                "combinations_audited": total,
                "clean_single_setting_component": clean,
                "mixed_setting": mixed_setting,
                "mixed_component": mixed_component,
                "partial_component_only": partial_only,
                "previously_misleading_ranges": misleading_range,
            }
        )
    )
    for example in examples:
        print("EXAMPLE=" + json.dumps(example))


if __name__ == "__main__":
    main()
