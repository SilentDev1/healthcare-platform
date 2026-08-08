"""Review parser gaps: inspect ParserReview records and unlinked raw files."""

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import hospital_price_settings
from collectors.hospital_prices.parsers import inspect_format
from packages.database import ParserReview, SourceFile, session_factory


def review_parser_gaps(session: Session) -> dict[str, object]:
    """Inspect ParserReview records and unlinked raw files for format coverage."""
    reviews = session.scalars(select(ParserReview).order_by(ParserReview.created_at)).all()

    results: list[dict[str, object]] = []
    for review in reviews:
        source = session.get(SourceFile, review.source_file_id)
        results.append(
            {
                "review_id": str(review.id),
                "source_file_id": str(review.source_file_id),
                "source_url": source.source_url if source else None,
                "detected_format": review.detected_format,
                "status": review.status,
                "reason": review.reason,
                "detected_headers": review.detected_headers,
                "bounded_sample_count": len(review.bounded_sample) if review.bounded_sample else 0,
            }
        )

    # Scan raw directory for unlinked files
    raw_dir = hospital_price_settings.hospital_price_raw_dir
    unlinked: list[dict[str, object]] = []
    if raw_dir.exists():
        for uuid_dir in sorted(raw_dir.iterdir()):
            if not uuid_dir.is_dir():
                continue
            for date_dir in sorted(uuid_dir.iterdir()):
                if not date_dir.is_dir():
                    continue
                for file_path in sorted(date_dir.iterdir()):
                    if file_path.name.startswith(".") or file_path.name == "metadata.json":
                        continue
                    # Check if this file path is referenced by any SourceFile
                    linked = session.scalar(
                        select(func.count(SourceFile.id)).where(
                            SourceFile.storage_path == str(file_path)
                        )
                    )
                    if not linked:
                        match_info = None
                        try:
                            match, headers, sample = inspect_format(file_path)
                            match_info = {
                                "parser_name": match.parser_name if match else None,
                                "confidence": match.confidence if match else None,
                                "detected_format": match.detected_format if match else None,
                                "headers": headers[:20],
                                "sample_count": len(sample),
                            }
                        except Exception as exc:
                            match_info = {"error": f"{type(exc).__name__}: {exc}"}
                        unlinked.append(
                            {
                                "path": str(file_path),
                                "size_bytes": file_path.stat().st_size,
                                "format_inspection": match_info,
                            }
                        )

    summary = {
        "parser_reviews": len(results),
        "unsupported_pending": sum(
            1 for r in results if r["status"] == "unsupported_pending_review"
        ),
        "unsupported_deferred": sum(1 for r in results if r["status"] == "unsupported_deferred"),
        "unlinked_raw_files": len(unlinked),
        "reviews": results,
        "unlinked_files": unlinked[:50],
    }
    return summary


def main() -> None:
    with session_factory() as session:
        summary = review_parser_gaps(session)

    print("\n=== Parser Gap Review ===")
    print(f"  Parser reviews: {summary['parser_reviews']}")
    print(f"  Unsupported pending: {summary['unsupported_pending']}")
    print(f"  Unsupported deferred: {summary['unsupported_deferred']}")
    print(f"  Unlinked raw files: {summary['unlinked_raw_files']}")
    print("\n  Full report:")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
