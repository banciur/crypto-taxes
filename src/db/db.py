from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base


def init_db() -> Session:
    engine: Engine = create_engine("sqlite:///:memory:", echo=True, connect_args={"check_same_thread": False})

    Base.metadata.create_all(engine)
    return sessionmaker(engine)()
