from sqlalchemy.orm import Session

from db.db import init_db


def main() -> None:
    _session: Session = init_db()


if __name__ == "__main__":
    main()
