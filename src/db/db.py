import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base


def init_db(echo: bool = False) -> Session:
    db_file = "crypto_taxes.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    engine: Engine = create_engine(f"sqlite:///{db_file}", echo=echo)

    Base.metadata.create_all(engine)
    return sessionmaker(engine)()
