"""Fetch + cache the authoritative CMS Hospital General Information snapshot for a state.

READ-ONLY external fetch, no DB writes. Queries the CMS provider-data datastore API
(dataset ``xubh-q36u`` — Hospital General Information) filtered to one state, keeps the
identity/consumer-relevant fields, and writes ``data/<state>_cms_hospital_snapshot.json``
in the same shape the MA foundation used (``_meta`` + ``hospitals``). This is the
authoritative denominator anchor for a new Carevero market's Phase 1 foundation.

Generalized (not per-state hacked). Usage:
    python -m scripts.fetch_cms_hospital_snapshot --state NY
    python -m scripts.fetch_cms_hospital_snapshot --state NY --date 2026-08-23
"""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DATASET = "xubh-q36u"
BASE = f"https://data.cms.gov/provider-data/api/1/datastore/query/{DATASET}/0"
DATA = Path(__file__).resolve().parent.parent / "data"

# Identity + consumer-relevant fields (matches the MA snapshot schema exactly).
FIELDS = [
    "facility_id",
    "facility_name",
    "address",
    "citytown",
    "zip_code",
    "countyparish",
    "hospital_type",
    "hospital_ownership",
    "emergency_services",
    "telephone_number",
    "hospital_overall_rating",
]


def _fetch_page(state: str, limit: int, offset: int) -> dict:
    params = {
        "conditions[0][property]": "state",
        "conditions[0][value]": state,
        "conditions[0][operator]": "=",
        "limit": str(limit),
        "offset": str(offset),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "carevero-foundation/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:  # noqa: S310 (trusted gov API)
        return json.loads(resp.read().decode("utf-8"))


def fetch_state(state: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    limit = 500
    total = None
    while True:
        page = _fetch_page(state, limit, offset)
        if total is None:
            total = page.get("count")
        results = page.get("results") or []
        if not results:
            break
        for r in results:
            rows.append({k: (r.get(k) or "") for k in FIELDS})
        offset += len(results)
        if total is not None and offset >= total:
            break
        if len(results) < limit:
            break
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, help="Two-letter state code, e.g. NY")
    ap.add_argument("--date", default=None, help="Retrieval date stamp (YYYY-MM-DD); required for reproducibility")
    args = ap.parse_args()
    state = args.state.upper()
    if not args.date:
        print("ERROR: pass --date YYYY-MM-DD (Date.now is intentionally not used).", file=sys.stderr)
        return 2

    rows = fetch_state(state)
    rows.sort(key=lambda r: r["facility_id"])
    out = {
        "_meta": {
            "source": "CMS Hospital General Information",
            "dataset_id": DATASET,
            "endpoint": f"https://data.cms.gov/provider-data/api/1/datastore/query/{DATASET}/0 (conditions: state={state})",
            "retrieval_date": args.date,
            "state": state,
            "row_count": len(rows),
            "fields": FIELDS,
            "note": (
                f"Authoritative CMS Medicare-certified hospital list for {state}. Cached offline so "
                "foundation verification is reproducible. hospital_type distinguishes Acute Care / "
                "Critical Access / Psychiatric / Childrens; reconcile against the state DOH before "
                "treating any record as part of the consumer denominator."
            ),
        },
        "hospitals": rows,
    }
    path = DATA / f"{state.lower()}_cms_hospital_snapshot.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")

    from collections import Counter

    types = Counter(r["hospital_type"] for r in rows)
    own = Counter(r["hospital_ownership"] for r in rows)
    print(f"Wrote {path} — {len(rows)} rows for {state}")
    print("hospital_type distribution:")
    for t, n in types.most_common():
        print(f"  {n:4d}  {t}")
    print("ownership distribution:")
    for o, n in own.most_common():
        print(f"  {n:4d}  {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
