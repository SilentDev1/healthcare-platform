from packages.data_health import evaluate_data_health
from packages.database import session_factory


def main() -> None:
    with session_factory() as session:
        summary = evaluate_data_health(session)
        session.commit()
        print(summary)


if __name__ == "__main__":
    main()
