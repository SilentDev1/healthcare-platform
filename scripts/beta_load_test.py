"""Small, non-destructive concurrent HTTP load check for private beta."""

import argparse
import asyncio
import statistics
import time

import httpx


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 25 or not 1 <= args.requests <= 500:
        raise SystemExit("safe limits: concurrency 1–25, requests 1–500")
    paths = [
        "/health",
        "/ready",
        "/api/v1/search?q=MRI",
        "/api/v1/facilities?state=NH&page_size=25",
        "/api/v1/procedures/mri-brain-without-contrast/comparison?state=NH",
    ]
    semaphore = asyncio.Semaphore(args.concurrency)
    durations: list[float] = []
    failures = 0
    async with httpx.AsyncClient(base_url=args.base_url, timeout=15) as client:

        async def hit(index: int) -> None:
            nonlocal failures
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(paths[index % len(paths)])
                    if response.status_code >= 400:
                        failures += 1
                except httpx.HTTPError:
                    failures += 1
                durations.append(time.perf_counter() - started)

        await asyncio.gather(*(hit(index) for index in range(args.requests)))
    ordered = sorted(durations)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    print(
        f"requests={len(durations)} failures={failures} "
        f"median_ms={statistics.median(durations) * 1000:.1f} p95_ms={p95 * 1000:.1f}"
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
