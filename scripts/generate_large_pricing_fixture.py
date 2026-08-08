"""CLI wrapper for generating large CMS 3.0 wide CSV fixtures."""

import argparse
from pathlib import Path

from collectors.hospital_prices.fixture_generator import generate_cms_wide_fixture


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic CMS 3.0 wide CSV fixture")
    parser.add_argument("--rows", type=int, default=100_000, help="Number of rows")
    parser.add_argument("--payers", type=int, default=10, help="Number of payers")
    parser.add_argument("--plans-per-payer", type=int, default=3, help="Plans per payer")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/generated/large_fixture.csv"),
        help="Output file path",
    )
    args = parser.parse_args()

    path = generate_cms_wide_fixture(
        args.output,
        rows=args.rows,
        payers=args.payers,
        plans_per_payer=args.plans_per_payer,
        seed=args.seed,
    )
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Generated {args.rows} rows -> {path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
