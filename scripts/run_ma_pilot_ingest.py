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
import argparse
import json
import time

from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from packages.database import session_factory
from scripts.download_all_nh_sources import download_all_sources
from scripts.import_all_nh import import_all_sources

STATE = "MA"


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded MA hospital-price ingestion (download+import+rebuild)")
    parser.add_argument("--only-ccns", default="", help="comma-separated CCNs to bound the wave (large MRFs solo)")
    parser.add_argument("--no-rebuild", action="store_true", help="import only; defer summary rebuild to a final pass")
    parser.add_argument("--rebuild-only", action="store_true", help="only rebuild summaries (no download/import)")
    args = parser.parse_args()
    only = {c.strip() for c in args.only_ccns.split(",") if c.strip()} or None

    results: dict[str, object] = {"state": STATE, "only_ccns": sorted(only) if only else "all"}
    with session_factory() as session:
        if args.rebuild_only:
            t0 = time.perf_counter()
            projection = rebuild_price_summaries(session)
            health = evaluate_pricing_health(session)
            session.commit()
            results["rebuild"] = {
                "observations": projection["observations"],
                "summaries": projection["summaries"],
                "average_health": health["average_pricing_health"],
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
            print("MA_PILOT_INGEST=" + json.dumps(results, indent=2, default=str))
            return

        t0 = time.perf_counter()
        try:
            download = download_all_sources(session, STATE, only_ccns=only)
            session.commit()
            results["download"] = {**download, "elapsed_sec": round(time.perf_counter() - t0, 2)}
        except Exception as exc:  # fail-forward: report, keep going to import what did land
            results["download"] = {"error": str(exc)}

        t0 = time.perf_counter()
        try:
            imported = import_all_sources(session, STATE, only_ccns=only, rebuild=not args.no_rebuild)
            session.commit()
            results["import"] = {**imported, "elapsed_sec": round(time.perf_counter() - t0, 2)}
        except Exception as exc:
            results["import"] = {"error": str(exc)}

    print("MA_PILOT_INGEST=" + json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
