"""Bounded MA hospital-price ingestion (download → import → summaries) — NO auto-discovery.

Runs only the download + import steps for ``--state MA``. Because ``download_all_sources`` and
``import_all_sources`` act on facilities that already have a registered ``FacilityPriceSource``,
seeding sources for only the pilot CCNs (via scripts.seed_ma_price_sources --only-ccns) keeps this
strictly bounded to the pilot set. The auto-discovery web crawl in ``pipeline_full`` is deliberately
skipped so the pilot cannot silently expand to unseeded hospitals.

``import_all_sources`` seeds the shared national ProcedureCodeMapping catalog and rebuilds price
summaries; ``rebuild_price_summaries`` preserves NH hospital + NH provider-published summaries (the
patched behaviour), so NH is never damaged. Verify NH invariants with scripts.phase_4_7_safety after.

Run: python -m scripts.run_ma_pilot_ingest
"""

from __future__ import annotations

# ruff: noqa: E501
import json
import time

from packages.database import session_factory
from scripts.download_all_nh_sources import download_all_sources
from scripts.import_all_nh import import_all_sources

STATE = "MA"


def main() -> None:
    results: dict[str, object] = {"state": STATE}
    with session_factory() as session:
        t0 = time.perf_counter()
        try:
            download = download_all_sources(session, STATE)
            session.commit()
            results["download"] = {**download, "elapsed_sec": round(time.perf_counter() - t0, 2)}
        except Exception as exc:  # fail-forward: report, keep going to import what did land
            results["download"] = {"error": str(exc)}

        t0 = time.perf_counter()
        try:
            imported = import_all_sources(session, STATE)
            session.commit()
            results["import"] = {**imported, "elapsed_sec": round(time.perf_counter() - t0, 2)}
        except Exception as exc:
            results["import"] = {"error": str(exc)}

    print("MA_PILOT_INGEST=" + json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
