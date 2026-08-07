from collectors.hospital_prices.projections import evaluate_pricing_health
from packages.database import session_factory


def main() -> None:
    with session_factory() as session:
        print(evaluate_pricing_health(session))


if __name__ == "__main__":
    main()
