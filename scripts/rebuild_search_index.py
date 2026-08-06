from packages.database import session_factory
from packages.search import rebuild_index


def main() -> None:
    with session_factory() as session:
        count = rebuild_index(session)
        session.commit()
        print(f"indexed={count}")


if __name__ == "__main__":
    main()
