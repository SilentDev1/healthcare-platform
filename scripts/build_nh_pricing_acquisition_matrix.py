"""Phase 1 — NH pricing-acquisition matrix (organization-first).

Reads the CURRENT production roster from the API (authority) and enumerates every
`price_available=false` NH service location, grouped by organization + capability.
Emits a resumable ledger (JSON) + a human-readable matrix (Markdown) + a coverage
dashboard that reconciles exactly to the production roster.

Read-only. No production data is modified. Uses curl via subprocess (the project
venv's Python rejects the Cloud Run cert otherwise).
"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

API = "https://carevero-beta-api-5qlgp7uxsa-uk.a.run.app"
STATE = "NH"
PAGE_SIZE = 60


def _get(path: str) -> dict[str, Any]:
    out = subprocess.run(
        ["curl", "-s", f"{API}{path}"], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def fetch_all() -> list[dict[str, Any]]:
    """Every NH directory item across all pages."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        data = _get(
            f"/api/v1/facilities/directory?state={STATE}&page={page}&page_size={PAGE_SIZE}"
        )
        items.extend(data["items"])
        if page * PAGE_SIZE >= data["total"]:
            break
        page += 1
    return items


def org_key(item: dict[str, Any]) -> str:
    return (item.get("organization_name") or item["display_name"]).strip()


def main() -> None:
    items = fetch_all()
    priced = [i for i in items if i.get("price_available")]
    unpriced = [i for i in items if not i.get("price_available")]

    # Group the unpriced locations by organization.
    by_org: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for i in unpriced:
        by_org[org_key(i)].append(i)

    # Coverage dashboard by capability (locations may hold multiple capabilities).
    cap_total: dict[str, int] = defaultdict(int)
    cap_priced: dict[str, int] = defaultdict(int)
    for i in items:
        for cap in i.get("capabilities", []) or ["(none)"]:
            cap_total[cap] += 1
            if i.get("price_available"):
                cap_priced[cap] += 1

    # --- Resumable ledger ---------------------------------------------------------
    ledger = {
        "generated_from": "production API (authority)",
        "state": STATE,
        "totals": {
            "total_locations": len(items),
            "priced": len(priced),
            "unpriced": len(unpriced),
        },
        "capability_coverage": {
            cap: {"priced": cap_priced[cap], "total": cap_total[cap]}
            for cap in sorted(cap_total)
        },
        "organizations": [],
    }
    for org in sorted(by_org, key=lambda o: (-len(by_org[o]), o)):
        locs = by_org[org]
        caps = sorted({c for loc in locs for c in loc.get("capabilities", [])})
        ledger["organizations"].append(
            {
                "organization": org,
                "organization_type": locs[0].get("organization_type"),
                "location_count": len(locs),
                "capabilities": caps,
                "locations": [
                    {
                        "id": loc["id"],
                        "name": loc["display_name"],
                        "city": loc.get("city"),
                        "capabilities": loc.get("capabilities", []),
                        "current_price_records": loc.get("published_procedure_count", 0),
                    }
                    for loc in sorted(locs, key=lambda x: x["display_name"])
                ],
                # Research disposition — filled in during Phases 2-14.
                "disposition": {
                    "reason_codes": ["NEEDS_MANUAL_REVIEW"],
                    "public_pricing_source": None,
                    "source_url": None,
                    "source_type": None,
                    "applicability": None,
                    "ingestion_status": "pending",
                    "mapping_status": "pending",
                    "qa_status": "pending",
                    "blocker": None,
                },
            }
        )

    Path("data").mkdir(exist_ok=True)
    Path("data/nh_pricing_acquisition_ledger.json").write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False)
    )

    # --- Human-readable matrix ----------------------------------------------------
    lines: list[str] = []
    lines.append("# NH Missing-Pricing Acquisition Matrix\n")
    lines.append(
        f"Source: production API (authority). Total **{len(items)}** locations · "
        f"**{len(priced)}** priced · **{len(unpriced)}** unpriced "
        f"({len(unpriced)} to investigate).\n"
    )
    lines.append("## Coverage by capability (priced / total)\n")
    lines.append("| Capability | Priced | Total |")
    lines.append("|---|---:|---:|")
    for cap in sorted(cap_total, key=lambda c: -cap_total[c]):
        lines.append(f"| {cap} | {cap_priced[cap]} | {cap_total[cap]} |")
    lines.append(
        "\n_Note: locations may hold multiple capabilities, so capability totals do "
        "NOT sum to unique locations._\n"
    )
    lines.append(
        f"## Unpriced organizations ({len(by_org)}), most locations first\n"
    )
    lines.append(
        "Organization-first: one verified public source may cover many locations. "
        "Each org gets a documented disposition before being declared unpriced.\n"
    )
    lines.append("| # | Organization | Type | Locs | Capabilities | Cities |")
    lines.append("|---:|---|---|---:|---|---|")
    for n, org in enumerate(
        sorted(by_org, key=lambda o: (-len(by_org[o]), o)), start=1
    ):
        locs = by_org[org]
        caps = ", ".join(sorted({c for loc in locs for c in loc.get("capabilities", [])}))
        cities = ", ".join(sorted({loc.get("city") or "?" for loc in locs}))
        lines.append(
            f"| {n} | {org} | {locs[0].get('organization_type') or '—'} | "
            f"{len(locs)} | {caps} | {cities[:80]} |"
        )
    lines.append(
        "\nFull per-location detail + research disposition: "
        "`data/nh_pricing_acquisition_ledger.json`.\n"
    )
    Path("docs").mkdir(exist_ok=True)
    Path("docs/NH_MISSING_PRICING_ACQUISITION.md").write_text("\n".join(lines))

    # --- Console dashboard --------------------------------------------------------
    print(f"TOTAL={len(items)} PRICED={len(priced)} UNPRICED={len(unpriced)}")
    print(f"UNPRICED_ORGS={len(by_org)}")
    print("Top orgs by unpriced locations:")
    for org in sorted(by_org, key=lambda o: -len(by_org[o]))[:15]:
        caps = ",".join(sorted({c for loc in by_org[org] for c in loc.get("capabilities", [])}))
        print(f"  {len(by_org[org]):2d}  {org}  [{caps}]")


if __name__ == "__main__":
    main()
