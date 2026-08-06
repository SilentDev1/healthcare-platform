import statistics
import time

from packages.database import session_factory
from packages.search import search

QUERIES = ("Concord", "MRI", "knee replacement", "maternity", "03060", "Dartmouth")


def main() -> None:
    timings: list[float] = []
    with session_factory() as session:
        for _ in range(20):
            for query in QUERIES:
                started = time.perf_counter()
                search(session, query)
                timings.append((time.perf_counter() - started) * 1000)
    ordered = sorted(timings)
    p95 = ordered[int(len(ordered) * 0.95) - 1]
    print(
        f"queries={len(timings)} median_ms={statistics.median(timings):.2f} "
        f"p95_ms={p95:.2f} max_ms={max(timings):.2f}"
    )


if __name__ == "__main__":
    main()
