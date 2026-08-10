"""Non-destructive HTTP smoke test for a deployed or local production stack."""

import argparse
import sys

import httpx


def require(client: httpx.Client, path: str, contains: str | None = None) -> str:
    response = client.get(path)
    response.raise_for_status()
    if contains and contains not in response.text:
        raise RuntimeError(f"{path} did not contain expected text: {contains}")
    return response.text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-url", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--facility-id", required=True)
    parser.add_argument("--missing-price-facility-id", required=True)
    parser.add_argument("--procedure", default="mri-brain-without-contrast")
    args = parser.parse_args()
    with httpx.Client(base_url=args.api_url, timeout=15, follow_redirects=True) as api:
        require(api, "/health", '"ok"')
        require(api, "/ready", '"ready"')
        require(api, "/api/v1/search?q=MRI")
        require(api, "/api/v1/facilities/map-data?state=NH")
        comparison = api.get(f"/api/v1/procedures/{args.procedure}/comparison?state=NH")
        comparison.raise_for_status()
        items = comparison.json()["items"]
        priced = [item for item in items if item["price_available"]][:2]
        if len(priced) < 2:
            raise RuntimeError("fewer than two priced locations available for compare smoke")
        compare_items = ",".join(
            f"{item['facility_id']}~{item['facility_location_id']}" for item in priced
        )
    with httpx.Client(base_url=args.web_url, timeout=20, follow_redirects=True) as web:
        require(web, "/", "Compare healthcare costs")
        require(web, f"/procedures/{args.procedure}/prices", "Published")
        require(web, f"/hospitals/{args.facility_id}", "Data sources")
        require(web, f"/hospitals/{args.missing_price_facility_id}", "not currently available")
        require(web, f"/compare?procedure={args.procedure}&items={compare_items}", "Compare")
        require(web, "/map", "Hospital map")
        require(web, "/privacy", "Privacy at Carevero")
        require(web, "/terms", "informational comparison tool")
    print("beta smoke: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"beta smoke: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
